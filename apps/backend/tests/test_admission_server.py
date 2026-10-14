"""Admission control through a real Uvicorn server (review finding 4): forwarding headers cannot evade 429.

Each test starts an actual uvicorn.Server on a loopback socket and talks HTTP over TCP, so Uvicorn's own proxy-header
handling and the ASGI middleware stack are exercised, not only function calls.
"""
import asyncio
import os
import socket
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import uvicorn
from fastapi import FastAPI, Request

from trustlens_backend import serve
from trustlens_backend.admission import Admission, BucketProfile, admission_middleware, connection_class
from trustlens_backend.main import create_app

ROOT = Path(__file__).resolve().parents[3]
TIGHT = BucketProfile(capacity=3, refill_per_second=0.001)          # effectively no refill during a test


class LiveServer:
    def __init__(self, app, uvicorn_config=None):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(64)
        self.port = self.sock.getsockname()[1]
        cfg = uvicorn_config or serve.config(app, port=self.port, log_level="warning")
        self.server = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=lambda: asyncio.run(self.server.serve(sockets=[self.sock])), daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("server did not start")
            time.sleep(0.02)
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", trust_env=False, timeout=10)

    def close(self):
        self.client.close()
        self.server.should_exit = True
        self.thread.join(10)
        self.sock.close()


def spoof(i):
    return {"X-Forwarded-For": f"198.51.100.{i}", "X-Real-IP": f"203.0.113.{i}",
            "Forwarded": f"for=192.0.2.{i};proto=https", "X-Forwarded-Proto": "https"}


def probe_app():
    app = FastAPI()
    app.state.admission = Admission(TIGHT, TIGHT)
    app.middleware("http")(admission_middleware)

    @app.middleware("http")                      # outermost, as in the real app: errors carry a request id
    async def request_identity(request: Request, call_next):
        request.state.request_id = "probe"
        return await call_next(request)

    @app.get("/peer")
    async def peer(request: Request):
        return {"host": request.client.host, "class": connection_class(request)}

    @app.post("/api/v1/probe")
    async def probe():
        return {"admitted": True}
    return app


class SupportedLauncherTests(unittest.TestCase):
    def start(self, app, **kw):
        server = LiveServer(app, **kw)
        self.addCleanup(server.close)
        return server

    def trustlens_app(self):
        app = create_app(None, configure_from_environment=False)
        app.state.admission = Admission(TIGHT, TIGHT)
        return app

    def test_rotating_forwarding_headers_cannot_evade_the_sign_in_limit(self):
        server = self.start(self.trustlens_app())
        statuses = [server.client.get("/auth/login", headers=spoof(i), follow_redirects=False).status_code for i in range(6)]
        self.assertNotIn(429, statuses[:3])
        self.assertEqual(statuses[3:], [429, 429, 429])
        refused = server.client.get("/auth/callback", headers=spoof(99), follow_redirects=False)
        self.assertEqual(refused.status_code, 429)
        self.assertGreaterEqual(int(refused.headers["retry-after"]), 1)

    def test_rotating_forwarding_headers_cannot_evade_the_write_limit(self):
        server = self.start(self.trustlens_app())
        responses = [server.client.post("/api/v1/cases", json={}, headers=spoof(i)) for i in range(5)]
        self.assertNotIn(429, [r.status_code for r in responses[:3]])
        for r in responses[3:]:
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (429, "RATE_LIMITED"))
            self.assertIn("retry-after", r.headers)

    def test_the_supported_launcher_sees_the_real_peer(self):
        server = self.start(probe_app())
        for i in range(3):
            self.assertEqual(server.client.get("/peer", headers=spoof(i)).json(), {"host": "127.0.0.1", "class": "loopback"})

    def test_misconfigured_proxy_headers_still_cannot_mint_buckets(self):
        """Negative control + defence in depth: with proxy headers wrongly enabled the peer address IS spoofable (so
        per-address keys would be evaded), yet the connection-class identity keeps every spoofed address in one bucket."""
        app = probe_app()
        server = self.start(app, uvicorn_config=uvicorn.Config(app, proxy_headers=True, forwarded_allow_ips="*",
                                                               log_level="warning"))
        seen = [server.client.get("/peer", headers={"X-Forwarded-For": f"198.51.100.{i}"}).json() for i in (1, 2)]
        self.assertEqual([x["host"] for x in seen], ["198.51.100.1", "198.51.100.2"])     # the old key was spoofable
        self.assertEqual({x["class"] for x in seen}, {"other"})
        for prefix in ("198.51.100.", "127.0.0."):            # six different spoofed addresses per family
            with self.subTest(prefix=prefix):
                statuses = [server.client.post("/api/v1/probe", headers={"X-Forwarded-For": f"{prefix}{i}"}).status_code
                            for i in range(10, 16)]
                self.assertEqual(statuses, [200, 200, 200, 429, 429, 429])     # one bucket of 3, not six fresh ones


class LaunchConfigurationTests(unittest.TestCase):
    def test_make_backend_run_uses_the_supported_launcher(self):
        makefile = (ROOT / "Makefile").read_text()
        recipe = makefile[makefile.index("\nbackend-run:"):makefile.index("\ndatabase-check:")]
        self.assertIn("-m trustlens_backend.serve", recipe)
        self.assertNotIn("uvicorn", recipe.replace("trustlens_backend.serve", ""))
        self.assertNotIn("--proxy-headers", makefile)
        self.assertNotIn("--forwarded-allow-ips", makefile)

    def test_proxy_settings_are_fixed_and_ignore_the_environment(self):
        with patch.dict(os.environ, {"FORWARDED_ALLOW_IPS": "*"}):
            cfg = serve.config(FastAPI())
        self.assertEqual((cfg.proxy_headers, cfg.forwarded_allow_ips, cfg.host, cfg.workers), (False, [], "127.0.0.1", 1))
        for unsafe in ({"proxy_headers": True}, {"forwarded_allow_ips": "*"}, {"workers": 2}, {"reload": True}):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                serve.config(FastAPI(), **unsafe)


if __name__ == "__main__":
    unittest.main()
