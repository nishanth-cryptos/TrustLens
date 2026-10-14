"""Bounded local admission control (NFR-016 / RATE_LIMITED) for the single-process S2 development profile.

Token buckets held in memory:
- Sign-in (/auth/login, /auth/callback): 10 requests per connection class, refilling at 10 per minute. This also
  bounds how fast unauthenticated callers can append AUTHENTICATION_FAILED audit events.
- State-changing API requests (POST/PUT/PATCH/DELETE under /api/): 20 per signed-in principal (or per connection
  class when there is no valid session), refilling at 30 per minute.
- At most 10 000 tracked keys; least-recently-used keys are evicted.

Unauthenticated identity is the connection class of the ASGI peer, never a request header. The supported launcher
(trustlens_backend.serve) disables proxy-header processing, so the peer is the real TCP peer on the loopback listener.
As defence in depth, every loopback peer shares one bucket and every other peer shares another. A spoofed or rotated
X-Forwarded-For therefore cannot mint fresh buckets, even if proxy headers were re-enabled by mistake.

Refused requests get 429 RATE_LIMITED with Retry-After. These are local-development values, not production admission
control: they are per process, reset on restart, and assume a single loopback-only process with no reverse proxy.
"""
import ipaddress
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response

AUTH_PATHS = {"/auth/login", "/auth/callback"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class BucketProfile:
    capacity: int
    refill_per_second: float

    def __post_init__(self):
        if self.capacity < 1 or not self.refill_per_second > 0:
            raise ValueError("a bucket needs a positive capacity and refill rate")


SIGN_IN = BucketProfile(capacity=10, refill_per_second=10 / 60)
API_WRITE = BucketProfile(capacity=20, refill_per_second=30 / 60)


class TokenBuckets:
    def __init__(self, profile: BucketProfile, max_keys: int = 10_000, clock=time.monotonic):
        self._profile, self._max_keys, self._clock = profile, max_keys, clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def take(self, key: str) -> tuple[bool, int]:
        """(allowed, retry_after_seconds)."""
        with self._lock:
            now = self._clock()
            tokens, updated = self._buckets.pop(key, (float(self._profile.capacity), now))
            tokens = min(self._profile.capacity, tokens + (now - updated) * self._profile.refill_per_second)
            allowed = tokens >= 1
            if allowed:
                tokens -= 1
            self._buckets[key] = (tokens, now)
            while len(self._buckets) > self._max_keys:
                self._buckets.popitem(last=False)
        return allowed, 0 if allowed else max(1, math.ceil((1 - tokens) / self._profile.refill_per_second))


class Admission:
    def __init__(self, sign_in: BucketProfile = SIGN_IN, api_write: BucketProfile = API_WRITE, clock=time.monotonic):
        self.sign_in = TokenBuckets(sign_in, clock=clock)
        self.api_write = TokenBuckets(api_write, clock=clock)


def connection_class(request: Request) -> str:
    """'loopback' or 'other' from the ASGI peer (scope['client']); headers are never consulted."""
    client = request.scope.get("client")
    try:
        return "loopback" if client and ipaddress.ip_address(client[0]).is_loopback else "other"
    except ValueError:
        return "other"


async def admission_middleware(request: Request, call_next):
    from .auth import _runtime, api_error          # local import: auth imports nothing from here
    admission: Admission | None = getattr(request.app.state, "admission", None)
    if admission is None:
        return await call_next(request)
    client = connection_class(request)
    path = request.url.path
    if path in AUTH_PATHS:
        allowed, retry = admission.sign_in.take(f"addr:{client}")
        if not allowed:
            return Response("Too many sign-in attempts. Please wait and try again.", status_code=429, media_type="text/plain",
                            headers={"Retry-After": str(retry), "Cache-Control": "no-store"})
    elif request.method in UNSAFE_METHODS and path.startswith("/api/"):
        runtime = _runtime(request)
        session = runtime.sessions.get(request.cookies.get(runtime.session_cookie)) if runtime else None
        key = f"principal:{session.principal_reference_id}" if session else f"addr:{client}"
        allowed, retry = admission.api_write.take(key)
        if not allowed:
            return api_error(request, "RATE_LIMITED", retry_after=retry)
    return await call_next(request)
