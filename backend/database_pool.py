"""Bounded per-process pools; reset tenant state before every return to idle."""
import os
import threading
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_lock = threading.Lock()
_pools = {}


def reset_scope(conn):
    conn.execute("SELECT set_config('app.brand_id','',false), set_config('app.store_id','',false), set_config('app.maintenance','off',false)")


def get_pool(dsn):
    with _lock:
        if dsn not in _pools:
            if len(_pools) >= 8: raise RuntimeError('Too many database configurations in one process')
            size = int(os.environ.get('DB_POOL_MAX_SIZE', '8'))
            if not 1 <= size <= 32: raise RuntimeError('DB_POOL_MAX_SIZE must be between 1 and 32')
            _pools[dsn] = ConnectionPool(dsn, min_size=0, max_size=size, timeout=10,
                max_waiting=64, max_idle=60, kwargs={'autocommit': True, 'row_factory': dict_row},
                reset=reset_scope, open=True)
        return _pools[dsn]


def close_pools():
    with _lock:
        for pool in _pools.values(): pool.close()
        _pools.clear()
