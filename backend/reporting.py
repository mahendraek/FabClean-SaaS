"""Read-only, RLS-preserving brand reports. Money is never combined across currencies."""
import csv
import io
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Header, HTTPException, Query
from fastapi.responses import Response

MAX_ORDERS = 5000
MAX_PAYMENTS = 20000
TERMINAL = {'cancelled', 'completed', 'collected', 'delivered'}
STATUSES = {'received', 'inspection', 'cleaning', 'quality_check', 'inspecting', 'in_progress', 'processing', 'ready_for_pickup', 'out_for_delivery', 'completed', 'collected', 'delivered', 'cancelled'}


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(409, 'An order or payment has invalid monetary data; correct it before reporting')


def timestamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(409, 'An order has an invalid timestamp; correct it before reporting')
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise HTTPException(409, 'An order has a missing or ambiguous timestamp; correct it before reporting')
    return value.astimezone(timezone.utc)


def date_range(start, end, zone, now):
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(409, 'The brand timezone must be configured before reporting')
    today = now.astimezone(tz).date()
    try:
        if any(value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) for value in (start, end)):
            raise ValueError
        first = date.fromisoformat(start) if start else today.replace(day=1)
        last = date.fromisoformat(end) if end else today
        if first > last or (last - first).days >= 366:
            raise ValueError
        upper = last + timedelta(days=1)
    except (ValueError, OverflowError):
        raise HTTPException(400, 'Use YYYY-MM-DD dates in order, covering at most 366 days')
    return first, last, datetime.combine(first, time.min, tz).astimezone(timezone.utc), datetime.combine(upper, time.min, tz).astimezone(timezone.utc)


def currency(order):
    value = order.get('currency') or (order.get('tax_snapshot') or {}).get('currency')
    return value.upper() if isinstance(value, str) and re.fullmatch('[A-Za-z]{3}', value) else 'UNSPECIFIED'


def totals(rows, payments):
    groups = {}

    def group(code):
        if code not in groups:
            groups[code] = {'currency': code, 'orders': 0, 'payment_methods': {}, **{key: Decimal(0) for key in ('order_value', 'paid_on_orders', 'outstanding', 'overpaid', 'payments', 'refunds', 'adjustments', 'other_transactions', 'net_collected')}}
        return groups[code]

    for row in rows:
        g = group(row['currency'])
        g['orders'] += 1
        for key in ('order_value', 'paid_on_orders', 'outstanding', 'overpaid'):
            g[key] += Decimal(row[key])
    for p in payments:
        g = group(p['currency'])
        amount = money(p['amount'])
        key = {'payment': 'payments', 'refund': 'refunds', 'adjustment': 'adjustments'}.get(p.get('transaction_type'), 'other_transactions')
        g[key] += -amount if key == 'refunds' else amount
        g['net_collected'] += amount
        method = p.get('payment_method') or 'other'
        g['payment_methods'][method] = g['payment_methods'].get(method, Decimal(0)) + amount
    for g in groups.values():
        for key, value in list(g.items()):
            if isinstance(value, Decimal):
                g[key] = format(value, '.2f')
        g['payment_methods'] = {k: format(v, '.2f') for k, v in sorted(g['payment_methods'].items())}
    return [groups[k] for k in sorted(groups)]


def operational_metrics(rows):
    samples = [r['turnaround_hours'] for r in rows if r['turnaround_hours'] is not None]
    return {'orders': len(rows), 'overdue': sum(r['overdue'] for r in rows), 'awaiting_pricing': sum(r['pricing_status'] == 'estimated' for r in rows), 'cancelled': sum(r['status'] == 'cancelled' for r in rows), 'orders_with_balance': sum(Decimal(r['outstanding']) > 0 and r['status'] != 'cancelled' for r in rows), 'turnaround_samples': len(samples), 'turnaround_missing': sum(r['status'] in TERMINAL - {'cancelled'} and r['turnaround_hours'] is None for r in rows), 'average_turnaround_hours': round(sum(samples) / len(samples), 2) if samples else None, 'unspecified_currency': sum(r['currency'] == 'UNSPECIFIED' for r in rows)}


def cell(value):
    text = str(value if value is not None else '')
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text


def csv_report(report):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['Brand', 'Store', 'Store ID', 'Order', 'Created at (UTC)', 'Status', 'Currency', 'Order value', 'Net paid on order', 'Outstanding', 'Overpaid', 'Turnaround hours', 'Overdue', 'Pricing status'])
    for row in report['orders']:
        writer.writerow([cell(report['brand_id']), cell(row['store_name']), cell(row['store_id']), cell(row['order_number']), row['created_at'], cell(row['status']), row['currency'], row['order_value'], row['paid_on_orders'], row['outstanding'], row['overpaid'], row['turnaround_hours'], row['overdue'], cell(row['pricing_status'])])
    return out.getvalue()


def summary_csv(report):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    metric_keys = ('overdue', 'awaiting_pricing', 'cancelled', 'orders_with_balance', 'average_turnaround_hours', 'turnaround_samples', 'turnaround_missing', 'unspecified_currency')
    writer.writerow(['Scope', 'Store', 'Currency', 'Orders in currency', 'Order value', 'Net paid on orders', 'Outstanding', 'Overpaid', 'Payments', 'Refunds', 'Adjustments', 'Other transactions', 'Net collected', 'From date', 'To date', 'Timezone', 'Status', 'Generated at', *[k.replace('_', ' ').title() + ' (all currencies)' for k in metric_keys]])
    sections = [('Selected stores', 'All selected stores', report['currencies'], report['metrics'])]
    sections.extend(('Store', st['store_name'], st['currencies'], st['metrics']) for st in report['by_store'])
    for scope, name, groups, metrics in sections:
        for g in groups or [None]:
            writer.writerow([scope, cell(name), g['currency'] if g else '', g['orders'] if g else 0, *[g[k] if g else '' for k in ('order_value', 'paid_on_orders', 'outstanding', 'overpaid', 'payments', 'refunds', 'adjustments', 'other_transactions', 'net_collected')], report['filters']['from_date'], report['filters']['to_date'], cell(report['timezone']), cell(report['filters']['status'] or 'All statuses'), report['generated_at'], *[metrics[k] for k in metric_keys]])
    return out.getvalue()


def register(app, s):
    def options(token):
        staff = s.require_permission('admin', token)
        brand, store = s.operational_scope(staff)
        if not s.DATABASE_URL:
            raise HTTPException(503, 'Reporting requires the PostgreSQL database')
        can_brand = s.has_role(staff, 'super_admin') or s.has_role(staff, 'brand_admin', brand_id=brand)
        with s.db() as conn:
            b = conn.execute('SELECT timezone FROM brands WHERE id=%s', (brand,)).fetchone()
            stores = conn.execute('SELECT id,name,active FROM stores WHERE brand_id=%s AND (%s OR id=%s) ORDER BY name,id', (brand, can_brand, store)).fetchall()
        if not b:
            raise HTTPException(403, 'Brand unavailable')
        first, last, _, _ = date_range(None, None, b['timezone'], datetime.now(timezone.utc))
        return {'brand_id': brand, 'active_store_id': store, 'can_report_brand': can_brand, 'timezone': b['timezone'], 'stores': [dict(r) for r in stores], 'default_from_date': first.isoformat(), 'default_to_date': last.isoformat(), 'statuses': sorted(STATUSES)}

    def build(token, from_date, to_date, scope, store_ids, status):
        opt = options(token)
        if scope not in ('store', 'brand'):
            raise HTTPException(400, 'Scope must be store or brand')
        if scope == 'brand' and not opt['can_report_brand']:
            raise HTTPException(403, 'Brand reporting requires a brand administrator')
        allowed = {r['id']: r for r in opt['stores']}
        selected = set(store_ids or ([opt['active_store_id']] if scope == 'store' else allowed))
        if not selected or selected - allowed.keys():
            raise HTTPException(404, 'Store not found in the authorized brand')
        if len(selected) > 100:
            raise HTTPException(400, 'Select at most 100 stores')
        if scope == 'store' and len(selected) != 1:
            raise HTTPException(400, 'Select one store or use brand scope')
        if status and status not in STATUSES:
            raise HTTPException(400, 'Unknown order status')
        now = datetime.now(timezone.utc)
        first, last, lower, upper = date_range(from_date, to_date, opt['timezone'], now)
        upper = min(upper, now)
        rows, period_payments = [], []
        # A single read-only snapshot; change only transaction-local RLS scope for
        # each explicitly authorized store. No maintenance/bypass connection.
        with s.db() as conn:
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                for store in sorted(selected):
                    conn.execute("SELECT set_config('app.brand_id',%s,true),set_config('app.store_id',%s,true),set_config('app.maintenance','off',true)", (opt['brand_id'], store))
                    orders = conn.execute('SELECT id,payload,created_at FROM orders WHERE created_at >= %s AND created_at < %s AND (%s::text IS NULL OR payload->>\'status\'=%s) ORDER BY created_at,id LIMIT %s', (lower, upper, status, status, MAX_ORDERS + 1)).fetchall()
                    if len(rows) + len(orders) > MAX_ORDERS:
                        raise HTTPException(413, 'Report exceeds 5000 orders; narrow the dates or stores')
                    ids = [o['id'] for o in orders]
                    paid = {p['order_id']: p['amount'] for p in conn.execute('SELECT order_id,SUM(amount) AS amount FROM payment_transactions WHERE order_id=ANY(%s) AND created_at<=%s GROUP BY order_id', (ids, now)).fetchall()}
                    events = {e['order_id']: e['finished_at'] for e in conn.execute("SELECT order_id,COALESCE(MIN(e.created_at) FILTER (WHERE to_value='ready_for_pickup'), MIN(e.created_at)) AS finished_at FROM order_events e JOIN orders o ON o.id=e.order_id AND o.business_id=e.business_id AND o.location_id=e.location_id WHERE order_id=ANY(%s) AND e.created_at>=o.created_at AND event_type='status_changed' AND to_value IN ('ready_for_pickup','completed','collected','delivered') AND e.created_at<=%s GROUP BY order_id", (ids, now)).fetchall()}
                    for order in orders:
                        p = order['payload']
                        created = timestamp(order['created_at'])
                        value, net = money(p.get('total')), money(paid.get(order['id'], 0))
                        finished = events.get(order['id'])
                        hours = (timestamp(finished) - created).total_seconds() / 3600 if finished else None
                        if hours is not None and hours < 0:
                            hours = None
                        due = timestamp(p['due_at']) if p.get('due_at') else None
                        rows.append({'id': order['id'], 'order_number': p.get('order_number', order['id']), 'store_id': store, 'store_name': allowed[store]['name'], 'created_at': created.isoformat(), 'status': p.get('status', 'received'), 'currency': currency(p), 'order_value': format(value, '.2f'), 'paid_on_orders': format(net, '.2f'), 'outstanding': format(max(value - net, Decimal(0)), '.2f'), 'overpaid': format(max(net - value, Decimal(0)), '.2f'), 'turnaround_hours': hours, 'overdue': bool(due and due < now and p.get('status') not in TERMINAL), 'pricing_status': p.get('pricing_status', 'estimated')})
                    payments = conn.execute("SELECT p.amount,p.transaction_type,p.payment_method,o.payload FROM payment_transactions p JOIN orders o ON o.id=p.order_id AND o.business_id=p.business_id AND o.location_id=p.location_id WHERE p.created_at>=%s AND p.created_at<%s AND (%s::text IS NULL OR o.payload->>'status'=%s) ORDER BY p.created_at,p.id LIMIT %s", (lower, upper, status, status, MAX_PAYMENTS + 1)).fetchall()
                    if len(period_payments) + len(payments) > MAX_PAYMENTS:
                        raise HTTPException(413, 'Report exceeds 20000 transactions; narrow the dates or stores')
                    period_payments.extend({'store_id': store, 'currency': currency(p['payload']), 'amount': p['amount'], 'transaction_type': p['transaction_type'], 'payment_method': p['payment_method']} for p in payments)
        rows.sort(key=lambda r: (r['created_at'], r['id']), reverse=True)
        return {**opt, 'generated_at': now.isoformat(), 'filters': {'from_date': first.isoformat(), 'to_date': last.isoformat(), 'scope': scope, 'store_ids': sorted(selected), 'status': status}, 'metrics': operational_metrics(rows), 'currencies': totals(rows, period_payments), 'by_store': [{'store_id': store, 'store_name': allowed[store]['name'], 'metrics': operational_metrics([r for r in rows if r['store_id'] == store]), 'currencies': totals([r for r in rows if r['store_id'] == store], [p for p in period_payments if p['store_id'] == store])} for store in sorted(selected)], 'orders': rows}

    @app.get('/api/reports/options')
    def report_options(x_session_token: str | None = Header(default=None)):
        return options(x_session_token)

    @app.get('/api/reports/summary')
    def summary(offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=200), from_date: str | None = None, to_date: str | None = None, scope: str = 'store', store_id: list[str] = Query(default=[]), status: str | None = None, x_session_token: str | None = Header(default=None)):
        result = build(x_session_token, from_date, to_date, scope, store_id, status)
        result['total'] = len(result['orders'])
        result['orders'] = result['orders'][offset:offset + limit]
        return result

    @app.get('/api/reports/orders')
    def detail(from_date: str | None = None, to_date: str | None = None, scope: str = 'store', store_id: list[str] = Query(default=[]), status: str | None = None, offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200), x_session_token: str | None = Header(default=None)):
        result = build(x_session_token, from_date, to_date, scope, store_id, status)
        return {'orders': result['orders'][offset:offset + limit], 'total': len(result['orders']), 'offset': offset, 'limit': limit, 'generated_at': result['generated_at']}

    @app.get('/api/reports/export')
    def export(dataset: str = 'orders', from_date: str | None = None, to_date: str | None = None, scope: str = 'store', store_id: list[str] = Query(default=[]), status: str | None = None, x_session_token: str | None = Header(default=None)):
        if dataset not in ('orders', 'summary'):
            raise HTTPException(400, 'Export dataset must be orders or summary')
        result = build(x_session_token, from_date, to_date, scope, store_id, status)
        name = f"fabclean-{dataset}-report-{result['filters']['from_date']}-to-{result['filters']['to_date']}.csv"
        return Response(summary_csv(result) if dataset == 'summary' else csv_report(result), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{name}"', 'Cache-Control': 'no-store'})
