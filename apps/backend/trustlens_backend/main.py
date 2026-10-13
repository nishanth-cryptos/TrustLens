"""S1 loopback-only foundation. No protected API or startup database mutation."""
from uuid import uuid4

from fastapi import FastAPI

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


@app.middleware("http")
async def request_identity(request, call_next):
    response = await call_next(request)
    response.headers["X-Request-Id"] = str(uuid4())
    return response


@app.get("/health/live")
def liveness():
    return {"status": "OK"}


@app.get("/health/ready")
def readiness():
    # The accepted internal probe has HTTP 200 + categorical status. S2 dependencies
    # (identity, protected content/keys, knowledge and schema) are not configured.
    return {"status": "NOT_READY"}
