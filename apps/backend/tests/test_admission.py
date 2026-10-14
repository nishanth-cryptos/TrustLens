"""Bounded local admission control (approved T09 local-development values): token buckets, 429 RATE_LIMITED."""
import unittest

from test_auth import APP, AuthTestCase
from trustlens_backend.admission import API_WRITE, SIGN_IN, Admission, BucketProfile, TokenBuckets


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class TokenBucketTests(unittest.TestCase):
    def test_approved_values(self):
        self.assertEqual((SIGN_IN.capacity, SIGN_IN.refill_per_second * 60), (10, 10))
        self.assertEqual((API_WRITE.capacity, API_WRITE.refill_per_second * 60), (20, 30))

    def test_burst_then_refill(self):
        clock = Clock()
        buckets = TokenBuckets(BucketProfile(3, 1.0), clock=clock)
        self.assertEqual([buckets.take("a")[0] for _ in range(4)], [True, True, True, False])
        self.assertEqual(buckets.take("a"), (False, 1))
        self.assertTrue(buckets.take("b")[0])                  # keys are independent
        clock.now += 1.0
        self.assertEqual(buckets.take("a"), (True, 0))
        clock.now += 100
        self.assertEqual(sum(buckets.take("a")[0] for _ in range(10)), 3)   # never refills past capacity

    def test_retry_after_reflects_refill_rate(self):
        clock = Clock()
        buckets = TokenBuckets(SIGN_IN, clock=clock)
        for _ in range(10):
            buckets.take("x")
        allowed, retry = buckets.take("x")
        self.assertEqual((allowed, retry), (False, 6))          # one token per 6 s

    def test_profiles_must_refill(self):
        with self.assertRaises(ValueError):
            BucketProfile(5, 0.0)

    def test_tracked_keys_are_bounded(self):
        buckets = TokenBuckets(BucketProfile(1, 0.001), max_keys=5, clock=Clock())
        for i in range(50):
            buckets.take(f"k{i}")
        self.assertEqual(len(buckets._buckets), 5)


class AdmissionMiddlewareTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.clock = Clock()
        self.client.app.state.admission = Admission(BucketProfile(3, 0.001), BucketProfile(2, 0.001), clock=self.clock)

    def test_sign_in_flood_is_refused_with_retry_after(self):
        statuses = [self.client.get("/auth/login", follow_redirects=False).status_code for _ in range(5)]
        self.assertEqual(statuses, [303, 303, 303, 429, 429])
        refused = self.client.get("/auth/callback", params={"code": "x", "state": "y"}, follow_redirects=False)
        self.assertEqual(refused.status_code, 429)
        self.assertIn("retry-after", refused.headers)
        self.assertEqual(refused.headers["cache-control"], "no-store")
        self.assertEqual(self.audit.types(), [])                # refused before any audit append

    def test_state_changing_api_requests_are_limited_per_principal(self):
        self.client.app.state.admission = Admission(BucketProfile(100, 0.001), BucketProfile(2, 0.001), clock=self.clock)
        self.sign_in()
        token = self.client.get("/auth/csrf").json()["csrf_token"]
        headers = {"Origin": APP, "X-CSRF-Token": token, "Idempotency-Key": "k" * 20}
        statuses = [self.client.post("/api/v1/cases", json={}, headers=headers).status_code for _ in range(3)]
        self.assertNotEqual(statuses[0], 429)
        self.assertEqual(statuses[2], 429)
        refused = self.client.post("/api/v1/cases", json={}, headers=headers)
        error = refused.json()["error"]
        self.assertEqual((error["code"], error["retryability"]), ("RATE_LIMITED", "RETRYABLE"))
        self.assertIn("retry-after", refused.headers)
        self.assertEqual(self.me().status_code, 200)            # reads are not write-limited

    def test_principals_have_independent_write_budgets(self):
        self.client.app.state.admission = Admission(BucketProfile(100, 0.001), BucketProfile(1, 0.001), clock=self.clock)
        self.assertNotEqual(self.client.post("/api/v1/cases", json={}).status_code, 429)   # anonymous: keyed by address
        self.assertEqual(self.client.post("/api/v1/cases", json={}).status_code, 429)
        self.sign_in()                                          # a signed-in principal has its own bucket
        self.assertNotEqual(self.client.post("/api/v1/cases", json={}, headers={"Origin": APP}).status_code, 429)


if __name__ == "__main__":
    unittest.main()
