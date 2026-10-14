"""Bounded request bodies (review finding 5): reading stops as soon as the bound would be exceeded.

The ASGI receive channel below counts every chunk the application pulls, so the tests prove how much was read, not
only which status was returned. Bodies are synthetic.
"""
import asyncio
import json
import unittest

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from trustlens_backend.cases import MAX_JSON_BODY, TOO_LARGE, is_too_large, read_bounded, read_json_object

CHUNK = 16 * 1024


def counting_request(chunks, headers=()):
    """A Starlette Request over an ASGI receive that yields `chunks` (an iterator, possibly endless) one at a time."""
    pulled = {"chunks": 0, "bytes": 0}
    iterator = iter(chunks)

    async def receive():
        try:
            chunk = next(iterator)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        pulled["chunks"] += 1
        pulled["bytes"] += len(chunk)
        return {"type": "http.request", "body": chunk, "more_body": True}
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [(k.encode(), v.encode()) for k, v in headers],
             "query_string": b""}
    return Request(scope, receive), pulled


def endless(chunk=b"x" * CHUNK):
    while True:
        yield chunk


def run(coroutine):
    return asyncio.run(coroutine)


class ReadBoundedTests(unittest.TestCase):
    def test_an_endless_chunked_body_is_cut_off_at_the_bound(self):
        request, pulled = counting_request(endless())
        self.assertIsNone(run(read_bounded(request, MAX_JSON_BODY)))
        self.assertEqual(pulled["chunks"], MAX_JSON_BODY // CHUNK + 1)        # one chunk past the bound, then stop
        self.assertLessEqual(pulled["bytes"], MAX_JSON_BODY + CHUNK)

    def test_a_misleading_content_length_does_not_widen_the_bound(self):
        request, pulled = counting_request(endless(), headers=[("content-length", "10")])
        self.assertIsNone(run(read_bounded(request, MAX_JSON_BODY)))
        self.assertEqual(pulled["chunks"], MAX_JSON_BODY // CHUNK + 1)

    def test_a_declared_oversize_or_malformed_length_is_refused_without_reading(self):
        for declared in (str(MAX_JSON_BODY + 1), "abc", "-5", "1e9"):
            request, pulled = counting_request(endless(), headers=[("content-length", declared)])
            with self.subTest(declared=declared):
                self.assertIsNone(run(read_bounded(request, MAX_JSON_BODY)))
                self.assertEqual(pulled["chunks"], 0)

    def test_exact_boundary_is_accepted_and_one_byte_more_is_not(self):
        exact = [b"y" * CHUNK] * (MAX_JSON_BODY // CHUNK)
        request, _ = counting_request(exact)
        self.assertEqual(len(run(read_bounded(request, MAX_JSON_BODY))), MAX_JSON_BODY)
        request, _ = counting_request(exact + [b"y"])
        self.assertIsNone(run(read_bounded(request, MAX_JSON_BODY)))

    def test_buffered_bytes_never_exceed_the_bound(self):
        request, _ = counting_request([b"z" * (MAX_JSON_BODY - 3), b"zzzz"])
        self.assertIsNone(run(read_bounded(request, MAX_JSON_BODY)))          # crossing chunk refused, not appended


def boundary_json(size):
    """A JSON object of exactly `size` bytes."""
    skeleton = json.dumps({"pad": ""}, separators=(",", ":")).encode()
    return json.dumps({"pad": "p" * (size - len(skeleton))}, separators=(",", ":")).encode()


class JsonObjectOverHttpTests(unittest.TestCase):
    """Through Starlette's real request stream, with chunked transfer (no Content-Length) from the test client."""

    def setUp(self):
        app = FastAPI()

        @app.post("/echo")
        async def echo(request: Request):
            body, problems = await read_json_object(request)
            if is_too_large(problems):
                return JSONResponse({"too_large": True}, status_code=413)
            if problems:
                return JSONResponse({"problems": problems}, status_code=400)
            return JSONResponse({"keys": sorted(body)})
        self.client = TestClient(app)

    def post_chunked(self, payload, chunk=CHUNK):
        def stream():
            for i in range(0, len(payload), chunk):
                yield payload[i:i + chunk]
        return self.client.post("/echo", content=stream(), headers={"Content-Type": "application/json"})

    def test_chunked_oversize_is_refused(self):
        response = self.post_chunked(boundary_json(MAX_JSON_BODY + 1))
        self.assertEqual(response.status_code, 413)

    def test_chunked_exact_boundary_and_small_bodies_are_accepted(self):
        self.assertEqual(self.post_chunked(boundary_json(MAX_JSON_BODY)).json(), {"keys": ["pad"]})
        self.assertEqual(self.post_chunked(b'{"relationship_to_content":"SENT"}').json(), {"keys": ["relationship_to_content"]})
        self.assertEqual(self.client.post("/echo", json={}).json(), {"keys": []})

    def test_invalid_json_keeps_its_accepted_error_shape(self):
        for raw, code in ((b"{not json", "MALFORMED"), (b"[1,2]", "MALFORMED"), (b"\xff\xfe", "MALFORMED")):
            with self.subTest(raw=raw):
                response = self.post_chunked(raw)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["problems"][0]["code"], code)
                self.assertNotIn("not json", response.text)                    # values never echoed
        self.assertEqual(self.client.post("/echo", content=b"{}", headers={"Content-Type": "text/plain"}).status_code, 400)
        self.assertEqual(TOO_LARGE["code"], "TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
