"""Schema capability detection: evidence intake and idempotency supersession need migration 0004 (candidate addendum
P9-S2-ADD-001). Against a 0003 database those features stay disabled (fail closed); nothing is created at runtime."""
import threading

_active: set[tuple] = set()
_lock = threading.Lock()


def evidence_schema_active(connection) -> bool:
    """True once the connected database has evidence_upload_intent (only a positive answer is cached)."""
    info = connection.info
    key = (info.host, info.port, info.dbname)
    if key in _active:
        return True
    with connection.cursor() as cur:
        cur.execute("SELECT to_regclass('trustlens.evidence_upload_intent') IS NOT NULL")
        active = bool(cur.fetchone()[0])
    if active:
        with _lock:
            _active.add(key)
    return active
