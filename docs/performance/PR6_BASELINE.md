# PR #6 local performance baseline

12 October 2026. These are in-process FastAPI TestClient measurements against local PostgreSQL 16 using a NOSUPERUSER/NOBYPASSRLS owner, Python 3.12.14 and a five-CPU cloud workspace. They exclude Internet/Render network latency. Each run creates a unique brand/store fixture with 50 orders, then issues 160 requests across four endpoints with eight concurrent workers. Both source and another store are exercised; returned order ownership is checked under concurrent load. Fixtures do not touch production.

The before run includes the initial security changes and measures the existing direct-connection behavior before the pooling/store-validation optimization. The final after run uses the complete PR #6 implementation. The retained JSON artifacts contain the exact measured samples/summary; results vary with host contention and are not production SLOs.

| Endpoint | Before p50 ms | After p50 ms | Before p95 ms | After p95 ms | Before p99 ms | After p99 ms |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/orders` | 201.42 | 120.83 | 275.99 | 209.64 | 284.68 | 236.56 |
| `/api/dashboard` | 203.14 | 114.08 | 252.16 | 178.19 | 259.05 | 305.61 |
| `/api/context` | 132.23 | 106.32 | 169.79 | 182.11 | 187.94 | 277.08 |
| `/api/handoffs` | 195.57 | 107.83 | 261.12 | 218.97 | 268.91 | 265.78 |

Throughput: **42.9 → 65.73 requests/second**; errors: **0 → 0**. Overall throughput improved by approximately 53% in these runs. Context p95 increased slightly in the final run; the improvement is aggregate, and individual tails require larger staging measurements.

The measured workload made 600 pooled checkouts, opened 5 new connections during the load phase, and ended at a bounded pool size of 8. Store validation now happens once per operational request; permission/session state is never cached across requests. Pool return clears tenant and maintenance settings, and every checkout revalidates the non-bypass role and applies the new scope.

The local regression gate requires zero errors, at least 10 requests/second, and p95 at most 1,000 ms for each endpoint with this workload. These conservative limits catch failures or severe degradation across varying CI machines. Authentication hashing, notification-provider latency, larger datasets and real network traffic need separate staging measurements; production load tests were not run.

Artifacts: [before](pr6-before.json), [after](pr6-after.json).

Reproduce from backend with an explicitly disposable local FABCLEAN_TEST_DATABASE_URL:

```bash
python tools/performance_baseline.py --output /tmp/pr6-load.json
```

For the complete validation gate, use `scripts/validate_pr6.sh` from the repository root. Native device checks and deployment prerequisites are in [the security release review](../PR6_SECURITY_RELEASE.md).
