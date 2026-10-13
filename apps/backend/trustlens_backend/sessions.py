"""Server-side, opaque, bounded OIDC transactions and browser sessions held in this process.

The accepted physical contract (DATA-001-WP2) has no session table, so the S2 local profile keeps sessions in memory:
a restart ends every session (fail closed) and the backend must run as a single process. Only SHA-256 digests of
the opaque browser values are used as keys, so the store never holds a usable cookie value.
"""
import base64
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field


class CapacityExceeded(RuntimeError):
    pass


def new_secret() -> str:
    """256-bit CSPRNG value, URL-safe."""
    return secrets.token_urlsafe(32)


_TOKEN_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
MAX_TOKEN_LENGTH = 128


def is_token(value, max_length: int = MAX_TOKEN_LENGTH) -> bool:
    """True only for the URL-safe ASCII shape this module issues (state, nonce, binding, session, CSRF values).

    Every request- or provider-controlled value is checked with this before hashing or constant-time comparison, so
    malformed input (wrong type, non-ASCII, oversize) is a plain rejection, never an exception.
    """
    return isinstance(value, str) and 0 < len(value) <= max_length and all(c in _TOKEN_ALPHABET for c in value)


def tokens_equal(presented, expected: str) -> bool:
    """Constant-time equality for two well-formed tokens (ASCII bytes); anything malformed is simply unequal."""
    return is_token(presented) and is_token(expected) and hmac.compare_digest(presented.encode("ascii"), expected.encode("ascii"))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pkce_verifier() -> str:
    """RFC 7636 code verifier: 64 characters from the unreserved set (384 bits of CSPRNG entropy)."""
    return secrets.token_urlsafe(48)


def pkce_challenge(verifier: str) -> str:
    """S256 code challenge."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class Transaction:
    state: str
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)
    browser_binding: str = field(repr=False)
    created: float


@dataclass
class Session:
    principal_reference_id: str
    csrf_token: str = field(repr=False)
    created: float
    last_seen: float
    id_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False, default=None)


class TransactionStore:
    """One-time login transactions keyed by state; a state is consumed by the first callback that presents it."""

    def __init__(self, lifetime: int, capacity: int, clock=time.monotonic):
        self._lifetime, self._capacity, self._clock = lifetime, capacity, clock
        self._items: dict[str, Transaction] = {}
        self._lock = threading.Lock()

    def _sweep(self, now):
        for key in [k for k, t in self._items.items() if now - t.created >= self._lifetime]:
            del self._items[key]

    def begin(self) -> tuple[Transaction, str]:
        """New transaction plus the opaque browser-binding value for the transaction cookie."""
        binding = new_secret()
        with self._lock:
            now = self._clock()
            self._sweep(now)
            if len(self._items) >= self._capacity:
                raise CapacityExceeded("too many pending sign-ins")
            tx = Transaction(state=new_secret(), nonce=new_secret(), code_verifier=pkce_verifier(),
                             browser_binding=digest(binding), created=now)
            self._items[digest(tx.state)] = tx
        return tx, binding

    def consume(self, state: str, binding: str | None) -> Transaction | None:
        """Atomically remove and return the transaction if the state is known, unexpired and bound to this browser."""
        if not is_token(state) or not is_token(binding):
            return None
        with self._lock:
            now = self._clock()
            tx = self._items.pop(digest(state), None)
            self._sweep(now)
        if tx is None or now - tx.created >= self._lifetime:
            return None
        if not hmac.compare_digest(tx.browser_binding.encode("ascii"), digest(binding).encode("ascii")):
            return None
        return tx

    def __len__(self):
        return len(self._items)


class SessionStore:
    def __init__(self, idle: int, absolute: int, capacity: int, clock=time.monotonic):
        self._idle, self._absolute, self._capacity, self._clock = idle, absolute, capacity, clock
        self._items: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _expired(self, s: Session, now) -> bool:
        return now - s.last_seen >= self._idle or now - s.created >= self._absolute

    def _sweep(self, now):
        for key in [k for k, s in self._items.items() if self._expired(s, now)]:
            del self._items[key]

    def create(self, principal_reference_id: str, id_token: str, refresh_token: str | None, replaces: str | None = None) -> str:
        """Always a fresh identifier (rotation on sign-in); any presented earlier session is invalidated."""
        session_id = new_secret()
        with self._lock:
            now = self._clock()
            if replaces:
                self._items.pop(digest(replaces), None)
            self._sweep(now)
            if len(self._items) >= self._capacity:
                raise CapacityExceeded("session capacity reached")
            self._items[digest(session_id)] = Session(principal_reference_id, new_secret(), now, now, id_token, refresh_token)
        return session_id

    def get(self, session_id: str | None) -> Session | None:
        if not is_token(session_id):
            return None
        with self._lock:
            now = self._clock()
            key = digest(session_id)
            s = self._items.get(key)
            if s is None:
                return None
            if self._expired(s, now):
                del self._items[key]
                return None
            s.last_seen = now
            return s

    def invalidate(self, session_id: str | None) -> Session | None:
        if not is_token(session_id):
            return None
        with self._lock:
            return self._items.pop(digest(session_id), None)

    def invalidate_principal(self, principal_reference_id: str) -> int:
        with self._lock:
            keys = [k for k, s in self._items.items() if s.principal_reference_id == principal_reference_id]
            for k in keys:
                del self._items[k]
        return len(keys)

    def __len__(self):
        return len(self._items)
