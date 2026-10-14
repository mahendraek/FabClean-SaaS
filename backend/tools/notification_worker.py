"""Process the selected store's outbox using an ordinary scoped staff session.

No superuser or maintenance scan. Set FABCLEAN_NOTIFICATION_SESSION securely;
this worker cannot discover or operate on other stores. --once is useful for
supervisors/cron; provider uncertainty and terminal messages are never retried.
"""
import argparse
import os
import time
from urllib.parse import urlparse
from datetime import datetime, timezone
import httpx


def run_once(client):
    response = client.get('/api/notifications/outbox?pending=true')
    response.raise_for_status()
    processed = 0
    for row in response.json()['notifications']:
        delivery = row.get('delivery') or {}
        if row['status'] not in ('queued', 'blocked', 'failed') or delivery.get('attempts', 0) >= 3:
            continue
        if row['status'] == 'failed' and not delivery.get('retryable'):
            continue
        if delivery.get('next_attempt_at') and datetime.fromisoformat(delivery['next_attempt_at']) > datetime.now(timezone.utc):
            continue
        response = client.post('/api/notifications/outbox/'+row['id']+'/dispatch')
        if response.status_code == 409:
            continue
        response.raise_for_status()
        processed += 1
    return processed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    url = os.getenv('FABCLEAN_NOTIFICATION_API', 'http://127.0.0.1:8000')
    parts = urlparse(url)
    if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise SystemExit('Notification workers require HTTPS or a loopback API')
    token = os.getenv('FABCLEAN_NOTIFICATION_SESSION', '')
    brand = os.getenv('FABCLEAN_NOTIFICATION_BRAND', '')
    store = os.getenv('FABCLEAN_NOTIFICATION_STORE', '')
    if not token or not brand or not store:
        raise SystemExit('Configure a scoped notification session, brand and store securely')
    with httpx.Client(base_url=url, headers={'X-Session-Token': token,'X-Active-Brand-ID':brand,'X-Active-Store-ID':store},timeout=30) as client:
        while True:
            try:
                count = run_once(client)
                print(f'Processed {count} selected-store notifications', flush=True)
            except httpx.HTTPStatusError as exc:
                # Do not print exception URLs/headers or provider response bodies.
                raise SystemExit(f'Notification API returned HTTP {exc.response.status_code}; check the scoped session and configuration')
            except httpx.HTTPError:
                raise SystemExit('Notification API unavailable')
            if args.once:
                return
            time.sleep(30)


if __name__ == '__main__':
    main()
