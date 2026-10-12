"""Repeatable in-process HTTP load against disposable local PostgreSQL only."""
import argparse
import json
import os
import sys
import time
import platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_store_operations import StoreOperationsAPITests as Fixtures


def run(count=50, requests=160, workers=8):
    url = urlparse(os.environ.get('FABCLEAN_TEST_DATABASE_URL', ''))
    if url.hostname not in ('localhost', '127.0.0.1', '::1') or not any(x in url.path.lower() for x in ('test', 'integration')):
        raise RuntimeError('Use an explicitly disposable local test/integration database')
    Fixtures.setUpClass()
    fixture = Fixtures()
    for _ in range(count): fixture.order()
    paths = ['/api/orders', '/api/dashboard', '/api/context', '/api/handoffs']
    def one(index):
        path = paths[index % len(paths)]
        actor = 'source' if (index // len(paths)) % 2 else 'other'
        started = time.perf_counter()
        response = Fixtures.request(actor, 'get', path)
        if response.status_code != 200: raise AssertionError(f'{path}: HTTP {response.status_code}')
        if path == '/api/orders':
            expected = Fixtures.stores[0 if actor == 'source' else 2]
            assert all(row['location_id'] == expected for row in response.json()['orders'])
        return path, (time.perf_counter() - started) * 1000
    try:
        from database_pool import get_pool
        pool_stats_before = get_pool(os.environ["FABCLEAN_TEST_DATABASE_URL"]).get_stats()
    except ImportError: pool_stats_before = {}
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool: results = list(pool.map(one, range(requests)))
    elapsed = time.perf_counter() - started
    report = {'orders_seeded': count, 'requests': requests, 'workers': workers, 'elapsed_seconds': round(elapsed, 3), 'requests_per_second': round(requests / elapsed, 2), 'errors': 0, 'paths': {}}
    report['environment'] = {'python': platform.python_version(), 'http_client': 'FastAPI TestClient', 'database': 'local PostgreSQL', 'cpu_count': os.cpu_count()}
    if pool_stats_before:
        after = get_pool(os.environ['FABCLEAN_TEST_DATABASE_URL']).get_stats()
        report['pool'] = {key: after.get(key, 0)-pool_stats_before.get(key, 0) for key in ('requests_num','connections_num','requests_queued','requests_wait_ms')}
        report['pool']['size'] = after['pool_size']
    for path in paths:
        samples = sorted(ms for p, ms in results if p == path)
        report['paths'][path] = {f'p{percent}_ms': round(samples[min(len(samples)-1, int(len(samples)*percent/100))], 2) for percent in (50,95,99)}
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--orders', type=int, default=50)
    parser.add_argument('--requests', type=int, default=160)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    result = run(args.orders, args.requests, args.workers)
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
