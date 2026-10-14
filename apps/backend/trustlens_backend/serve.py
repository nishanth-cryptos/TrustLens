"""The one supported way to run the S2 backend: single process, loopback only, no proxy-header processing.

The approved local profile has no reverse proxy, so no X-Forwarded-For / X-Real-IP / Forwarded header is trusted:
proxy_headers is off and no forwarder address is trusted, whatever FORWARDED_ALLOW_IPS says. The client address the
application sees is then the TCP peer. This is not a configuration for running behind a reverse proxy.

    PYTHONPATH=apps/backend apps/backend/.venv/bin/python -m trustlens_backend.serve
"""
import uvicorn

SERVER_OPTIONS = {
    "host": "127.0.0.1",
    "port": 8000,
    "proxy_headers": False,          # never rewrite the client address from request headers
    "forwarded_allow_ips": [],       # and trust no forwarder (overrides the FORWARDED_ALLOW_IPS environment default)
    "workers": 1,                    # S2 sessions and admission buckets are in memory
    "reload": False,
    "access_log": False,
}


def config(app="trustlens_backend.main:app", **overrides) -> uvicorn.Config:
    for unsafe in ("proxy_headers", "forwarded_allow_ips", "workers", "reload"):
        if unsafe in overrides and overrides[unsafe] != SERVER_OPTIONS[unsafe]:
            raise ValueError(f"{unsafe} is fixed by the local loopback profile")
    return uvicorn.Config(app, **{**SERVER_OPTIONS, **overrides})


def main() -> None:
    uvicorn.Server(config()).run()


if __name__ == "__main__":
    main()
