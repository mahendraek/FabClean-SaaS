"""Opt-in store tax policies. No inferred rates, external lookup or legacy activation."""
from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
import re
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import Header, HTTPException
from tenant_scope import current_scope, ScopedMemoryDict
import pricing

VERSION = 'store-tax-policies-v2'
memory_policies = ScopedMemoryDict()
CENT = Decimal('.01')


def install(conn):
    if conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s', (VERSION,)).fetchone():
        return
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS stores_id_brand_tax_v2 ON stores(id,brand_id)')
    conn.execute('''CREATE TABLE store_tax_policy_versions_v2 (
        id TEXT PRIMARY KEY,
        business_id TEXT NOT NULL DEFAULT NULLIF(current_setting('app.brand_id',true),''),
        location_id TEXT NOT NULL DEFAULT NULLIF(current_setting('app.store_id',true),''),
        revision INTEGER NOT NULL CHECK(revision>0),
        effective_on DATE NOT NULL,
        policy JSONB NOT NULL,
        created_by TEXT NOT NULL REFERENCES staff_users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(business_id,location_id,revision),
        FOREIGN KEY(location_id,business_id) REFERENCES stores(id,brand_id)
    )''')
    conn.execute('CREATE INDEX tax_policy_effective_v2 ON store_tax_policy_versions_v2(business_id,location_id,effective_on DESC,revision DESC)')
    conn.execute('ALTER TABLE store_tax_policy_versions_v2 ENABLE ROW LEVEL SECURITY')
    conn.execute('ALTER TABLE store_tax_policy_versions_v2 FORCE ROW LEVEL SECURITY')
    conn.execute("""CREATE POLICY tax_store_scope ON store_tax_policy_versions_v2
      USING (current_setting('app.maintenance',true)='on' OR
       (business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),'')))
      WITH CHECK (current_setting('app.maintenance',true)='on' OR
       (business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),'')))""")
    conn.execute("""CREATE FUNCTION immutable_store_tax_policy_v2() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF current_setting('app.maintenance',true)='on' THEN RETURN COALESCE(NEW,OLD); END IF;
        RAISE EXCEPTION 'Tax policy history is append-only';
      END $$""")
    conn.execute('CREATE TRIGGER tax_policy_history_v2 BEFORE UPDATE OR DELETE ON store_tax_policy_versions_v2 FOR EACH ROW EXECUTE FUNCTION immutable_store_tax_policy_v2()')
    conn.execute('ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS tax_amount NUMERIC')
    conn.execute('ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS tax_breakdown JSONB')
    conn.execute('INSERT INTO fabclean_schema_migrations(version) VALUES (%s)', (VERSION,))


def location(s):
    brand, store = current_scope.get() or ('fabclean', 'main')
    if not s.DATABASE_URL:
        return {'country': 'US', 'state': '', 'city': '', 'postal_code': '', 'timezone': 'UTC', 'business_id': brand, 'location_id': store}
    with s.db() as conn:
        row = conn.execute('SELECT country,state,city,postal_code,timezone,address_line1,address_line2 FROM stores WHERE id=%s AND brand_id=%s', (store, brand)).fetchone()
    if not row:
        raise HTTPException(403, 'Store unavailable')
    return {**dict(row), 'business_id': brand, 'location_id': store}


def today(loc):
    try:
        return datetime.now(timezone.utc).astimezone(ZoneInfo(loc['timezone'])).date()
    except (ValueError, KeyError):
        raise HTTPException(409, 'Configure a valid store timezone before enabling taxes')


def validate_policy(payload, services, loc):
    fields = {'enabled', 'pricing_mode', 'components', 'services', 'delivery_fee_taxable', 'effective_on', 'source_note'}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise HTTPException(400, 'Provide the complete tax policy using supported fields')
    p = deepcopy(payload)
    if type(p['enabled']) is not bool or type(p['delivery_fee_taxable']) is not bool or p['pricing_mode'] not in ('exclusive', 'inclusive'):
        raise HTTPException(400, 'Select valid tax flags and inclusive/exclusive pricing')
    if not isinstance(p['source_note'], str) or not 5 <= len(p['source_note'].strip()) <= 1000:
        raise HTTPException(400, 'Record the source used to verify these tax rates (5–1000 characters)')
    if not isinstance(p['effective_on'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', p['effective_on']):
        raise HTTPException(400, 'Effective date requires YYYY-MM-DD')
    try:
        effective = date.fromisoformat(p['effective_on'])
    except ValueError:
        raise HTTPException(400, 'Invalid effective date')
    if not today(loc) <= effective <= today(loc) + timedelta(days=366):
        raise HTTPException(400, 'Effective date must be today through the next 366 days')
    if p['enabled'] and (not loc.get('country') or not loc.get('state') or not loc.get('postal_code')):
        raise HTTPException(409, 'Set the store country, state/region and postal code before enabling tax')
    components = p['components']
    if not isinstance(components, list) or len(components) > 5 or (p['enabled'] and not components):
        raise HTTPException(400, 'Provide one to five verified tax components when enabled')
    names, rate_total = set(), Decimal(0)
    for component in components:
        if not isinstance(component, dict) or set(component) != {'name', 'rate'}:
            raise HTTPException(400, 'A component requires name and percentage rate')
        name = component['name']
        if not isinstance(name, str) or not name.strip() or len(name) > 80 or name.strip().casefold() in names:
            raise HTTPException(400, 'Use unique tax component names up to 80 characters')
        rate = pricing.number(component['rate'], 'Tax rate')
        if rate > 100 or rate.as_tuple().exponent < -4:
            raise HTTPException(400, 'Rates require 0–100 percent, with at most four decimal places')
        component['rate'] = str(rate)
        component['name'] = name.strip()
        names.add(name.strip().casefold())
        rate_total += rate
    if rate_total > 100:
        raise HTTPException(400, 'Combined tax rate cannot exceed 100 percent')
    classifications = p['services']
    if not isinstance(classifications, dict) or len(classifications) > 2000 or any(key not in services or value not in ('taxable', 'exempt') for key, value in classifications.items()):
        raise HTTPException(404, 'Classify only services in the active store as taxable or exempt')
    return p


def versions(s):
    if not s.DATABASE_URL:
        return deepcopy(memory_policies.get('versions', []))
    with s.db() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM store_tax_policy_versions_v2 ORDER BY revision DESC LIMIT 50').fetchall()]


def current_policy(s, loc):
    if s.DATABASE_URL:
        with s.db() as conn:
            row = conn.execute('SELECT * FROM store_tax_policy_versions_v2 WHERE effective_on<=%s ORDER BY effective_on DESC,revision DESC LIMIT 1', (today(loc),)).fetchone()
        return dict(row) if row else None
    applicable = [v for v in memory_policies.get('versions', []) if date.fromisoformat(str(v['effective_on'])) <= today(loc)]
    applicable.sort(key=lambda v: (str(v['effective_on']), v['revision']), reverse=True)
    return applicable[0] if applicable else None


def allocate(amount, weights):
    """Allocate exact cents by largest remainder, stable on equal weights."""
    amount = Decimal(amount)
    if not weights:
        return []
    total = sum(weights)
    if total == 0:
        return [Decimal(0)] * len(weights)
    exact = [amount * w / total for w in weights]
    floor = [v.quantize(CENT, rounding='ROUND_DOWN') for v in exact]
    cents = int((amount - sum(floor)) / CENT)
    ranking = sorted(range(len(weights)), key=lambda i: (exact[i] - floor[i], -i), reverse=True)
    for i in ranking[:cents]:
        floor[i] += CENT
    return floor


def calculate(items, discount, delivery_fee, policy, loc, currency, policy_id):
    base = pricing.quote(items, discount, delivery_fee)
    p = policy
    if not p['enabled']:
        return {**base, 'tax': 0, 'tax_snapshot': None}
    gross = [pricing.money(pricing.number(i.get('quantity', 1)) * pricing.number(i.get('unit_price', 0))) for i in items]
    discounts = allocate(pricing.money(discount), gross)
    components = p['components']
    rates = [Decimal(c['rate']) for c in components]
    rate = sum(rates) / 100
    tax_total = Decimal(0)
    lines, breakdown = [], [{'jurisdiction': c['name'], 'rate': c['rate'], 'amount': Decimal(0), 'taxable_base': Decimal(0)} for c in components]
    entries = [(item, value, reduction, p['services'].get(item['service_id'])) for item, value, reduction in zip(items, gross, discounts)]
    if pricing.money(delivery_fee):
        entries.append(({'service_id': '__delivery_fee__', 'service_name': 'Pickup / delivery'}, pricing.money(delivery_fee), Decimal(0), 'taxable' if p['delivery_fee_taxable'] else 'exempt'))
    for item, value, reduction, classification in entries:
        if classification not in ('taxable', 'exempt'):
            raise HTTPException(409, 'Classify every selected service in the tax policy before charging tax')
        net = value - reduction
        taxable = net if classification == 'taxable' else Decimal(0)
        if p['pricing_mode'] == 'inclusive' and rate and taxable:
            taxable = (net / (1 + rate)).quantize(CENT, rounding=ROUND_HALF_UP)
            parts = allocate(net - taxable, rates)
        else:
            parts = [(taxable * r / 100).quantize(CENT, rounding=ROUND_HALF_UP) for r in rates]
        tax = sum(parts)
        tax_total += tax
        for b, amount in zip(breakdown, parts):
            b['amount'] += amount
            b['taxable_base'] += taxable
        lines.append({'service_id': item['service_id'], 'service_name': item.get('service_name', ''), 'base': float(value), 'discount': float(reduction), 'classification': classification, 'taxable_base': float(taxable), 'tax': float(tax), 'total': float(net if p['pricing_mode'] == 'inclusive' else net + tax)})
    snapshot = {'engine_version': 2, 'policy_id': policy_id, 'policy': deepcopy(p), 'currency': currency, 'location': deepcopy(loc), 'pricing_mode': p['pricing_mode'], 'lines': lines, 'breakdown': [{**b, 'amount': float(b['amount']), 'taxable_base': float(b['taxable_base'])} for b in breakdown]}
    total = pricing.money(base['total']) + (tax_total if p['pricing_mode'] == 'exclusive' else Decimal(0))
    return {**base, 'currency': currency, 'tax': float(tax_total), 'tax_snapshot': snapshot, 'total': float(total)}


def quote(s, items, discount=0, delivery_fee=0, snapshot=None):
    if snapshot and snapshot.get('engine_version') == 2:
        return calculate(items, discount, delivery_fee, snapshot['policy'], snapshot['location'], snapshot['currency'], snapshot['policy_id'])
    loc = location(s)
    row = current_policy(s, loc)
    if not row or not row['policy']['enabled']:
        return {**pricing.quote(items, discount, delivery_fee), 'currency': s.get_settings_value().get('currency', 'USD'), 'tax': 0, 'tax_snapshot': None}
    saved = row['policy']
    if any(saved['location'].get(k) != loc.get(k) for k in ('country', 'state', 'city', 'postal_code', 'address_line1', 'address_line2', 'timezone')):
        raise HTTPException(409, 'Store location changed; review and publish a matching tax policy')
    currency = s.get_settings_value().get('currency', 'USD')
    if saved['currency'] != currency:
        raise HTTPException(409, 'Store currency changed; review and publish a matching tax policy')
    return calculate(items, discount, delivery_fee, saved, loc, currency, row['id'])


def refund_credit(order, rows, amount):
    snapshot = order.get('tax_snapshot') or {}
    if snapshot.get('engine_version') != 2:
        return None, None
    previous = [r for r in rows if r.get('transaction_type') == 'refund']
    if any(r.get('tax_amount') is None for r in previous):
        raise HTTPException(409, 'Prior refund tax credits require reconciliation before another refund')
    refunded = sum(abs(Decimal(str(r['amount']))) for r in previous)
    credited = sum(Decimal(str(r['tax_amount'])) for r in previous)
    gross, total = pricing.money(amount), pricing.money(order['total'])
    cumulative = ((refunded + gross) * pricing.money(order['tax']) / total).quantize(CENT, rounding=ROUND_HALF_UP) if total else Decimal(0)
    credit = max(Decimal(0), min(pricing.money(order['tax']) - credited, cumulative - credited))
    prior_by_name = {}
    for r in previous:
        for b in r.get('tax_breakdown') or []:
            prior_by_name[b['jurisdiction']] = prior_by_name.get(b['jurisdiction'], Decimal(0)) + Decimal(str(b['amount']))
    weights = [Decimal(str(b['amount'])) - prior_by_name.get(b['jurisdiction'], 0) for b in snapshot['breakdown']]
    if any(w < 0 for w in weights) or sum(prior_by_name.values()) != credited or credit > sum(weights):
        raise HTTPException(409, 'Prior component tax credits require reconciliation')
    amounts = allocate(credit, weights)
    breakdown = [{'jurisdiction': b['jurisdiction'], 'amount': float(a)} for b, a in zip(snapshot['breakdown'], amounts)]
    return float(credit), breakdown


def register(app, s):
    @app.get('/api/taxes/policy')
    def get_policy(x_session_token: str | None = Header(default=None)):
        s.require_permission('admin', x_session_token)
        loc = location(s)
        values = versions(s)
        return {'location': loc, 'currency': s.get_settings_value().get('currency', 'USD'), 'today': today(loc).isoformat(), 'revision': max((v['revision'] for v in values), default=0), 'active': current_policy(s, loc), 'versions': values[:50], 'services': s.get_service_values(include_inactive=True)}

    @app.post('/api/taxes/policy')
    @s.store_creation_transaction
    def publish(payload: dict, x_session_token: str | None = Header(default=None)):
        staff = s.require_permission('admin', x_session_token)
        if set(payload) != {'expected_revision', 'policy'} or type(payload['expected_revision']) is not int:
            raise HTTPException(400, 'Supply the reviewed policy and its expected revision')
        loc = location(s)
        values = versions(s)
        revision = max((v['revision'] for v in values), default=0)
        if revision != payload['expected_revision']:
            raise HTTPException(409, 'Tax policy changed; reload before publishing')
        services = {v['id'] for v in s.get_service_values(include_inactive=True)}
        policy = validate_policy(payload['policy'], services, loc)
        policy.update(location=loc, currency=s.get_settings_value().get('currency', 'USD'))
        row = {'id': str(uuid4()), 'revision': revision + 1, 'effective_on': policy['effective_on'], 'policy': policy, 'created_by': staff['id']}
        if s.DATABASE_URL:
            with s.db() as conn:
                row = dict(conn.execute('INSERT INTO store_tax_policy_versions_v2(id,revision,effective_on,policy,created_by) VALUES (%s,%s,%s,%s::jsonb,%s) RETURNING *', (row['id'], row['revision'], row['effective_on'], json.dumps(policy), staff['id'])).fetchone())
        else:
            memory_policies['versions'] = [row, *values]
        return row

    @app.post('/api/taxes/estimate')
    @s.store_creation_transaction
    def estimate(payload: dict, x_session_token: str | None = Header(default=None)):
        s.require_permission('orders', x_session_token)
        if set(payload) - {'items', 'discount', 'delivery_fee'}:
            raise HTTPException(400, 'Only items, discount and delivery fee are accepted')
        pricing.quote(payload.get('items', []), payload.get('discount', 0), payload.get('delivery_fee', 0))
        s.validate_order_references(payload, x_session_token)
        return quote(s, payload.get('items', []), payload.get('discount', 0), payload.get('delivery_fee', 0))

    @app.get('/api/taxes/report')
    def report(from_date: str | None = None, to_date: str | None = None, format: str = 'json', x_session_token: str | None = Header(default=None)):
        import reporting
        import csv
        import io
        from fastapi.responses import Response
        s.require_permission('admin', x_session_token)
        if not s.DATABASE_URL:
            raise HTTPException(503, 'Tax reporting requires PostgreSQL')
        if format not in ('json', 'csv'):
            raise HTTPException(400, 'Select JSON or CSV')
        loc = location(s)
        now = datetime.now(timezone.utc)
        first, last, lower, upper = reporting.date_range(from_date, to_date, loc['timezone'], now)
        upper = min(upper, now)
        groups = {}
        def group(code):
            return groups.setdefault(code, {'currency': code, 'orders': 0, 'taxable_sales': Decimal(0), 'tax_recorded': Decimal(0), 'estimated_tax': Decimal(0), 'cancelled_tax': Decimal(0), 'finalized_tax': Decimal(0), 'refund_tax_credits': Decimal(0), 'unclassified_refunds': 0, 'unclassified_tax_bases': 0})
        with s.db() as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            orders = conn.execute('SELECT payload FROM orders WHERE created_at>=%s AND created_at<%s ORDER BY created_at,id LIMIT 5001', (lower, upper)).fetchall()
            refunds = conn.execute("SELECT p.tax_amount,p.tax_breakdown,o.payload FROM payment_transactions p JOIN orders o ON o.id=p.order_id AND o.business_id=p.business_id AND o.location_id=p.location_id WHERE p.transaction_type='refund' AND p.created_at>=%s AND p.created_at<%s ORDER BY p.created_at,p.id LIMIT 20001", (lower, upper)).fetchall()
            if len(orders) > 5000 or len(refunds) > 20000:
                raise HTTPException(413, 'Tax report is too large; narrow the date range')
            for row in orders:
                order = row['payload']
                snapshot = order.get('tax_snapshot') or {}
                if not order.get('tax') and snapshot.get('engine_version') != 2:
                    continue
                g = group(reporting.currency(order))
                g['orders'] += 1
                amount = reporting.money(order.get('tax', 0))
                g['tax_recorded'] += amount
                bucket = 'cancelled_tax' if order.get('status') == 'cancelled' else ('estimated_tax' if order.get('pricing_status') != 'final' else 'finalized_tax')
                g[bucket] += amount
                if snapshot.get('engine_version') == 2:
                    g['taxable_sales'] += sum(reporting.money(line['taxable_base']) for line in snapshot['lines'])
                else:
                    g['unclassified_tax_bases'] += 1
            for row in refunds:
                order = row['payload']
                if not order.get('tax') and (order.get('tax_snapshot') or {}).get('engine_version') != 2:
                    continue
                g = group(reporting.currency(order))
                if row['tax_amount'] is None or ((order.get('tax_snapshot') or {}).get('engine_version') != 2 and not row['tax_amount'] and not row['tax_breakdown']):
                    g['unclassified_refunds'] += 1
                else:
                    amount = reporting.money(row['tax_amount'])
                    if amount < 0:
                        raise HTTPException(409, 'A refund has an invalid negative tax credit')
                    g['refund_tax_credits'] += amount
        for g in groups.values():
            g['net_recorded_tax'] = g['tax_recorded'] - g['refund_tax_credits']
            for key, value in list(g.items()):
                if isinstance(value, Decimal):
                    g[key] = str(value.quantize(CENT))
        result = {'from_date': first.isoformat(), 'to_date': last.isoformat(), 'timezone': loc['timezone'], 'generated_at': now.isoformat(), 'currencies': [groups[k] for k in sorted(groups)]}
        if format == 'csv':
            out = io.StringIO(newline='')
            fields = ['currency', 'orders', 'taxable_sales', 'tax_recorded', 'estimated_tax', 'cancelled_tax', 'finalized_tax', 'refund_tax_credits', 'net_recorded_tax', 'unclassified_refunds', 'unclassified_tax_bases']
            writer = csv.writer(out)
            writer.writerow([*fields, 'from_date', 'to_date', 'timezone', 'generated_at'])
            for g in result['currencies']:
                writer.writerow([*[g[k] for k in fields], first.isoformat(), last.isoformat(), reporting.cell(loc['timezone']), now.isoformat()])
            return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="tax-report-{first.isoformat()}-{last.isoformat()}.csv"', 'Cache-Control': 'no-store'})
        return result

    @app.post('/api/orders/{order_id}/tax-estimate')
    @s.order_transaction
    def estimate_existing(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
        s.require_permission('orders', x_session_token)
        order = s.get_order(order_id, x_session_token)
        if not isinstance(order, dict):
            order = order.model_dump(mode='json')
        if set(payload) - {'items', 'discount', 'delivery_fee'}:
            raise HTTPException(400, 'Only item pricing, discount and delivery fee are accepted')
        items, discount, fee = payload.get('items', order['items']), payload.get('discount', order.get('discount', 0)), payload.get('delivery_fee', order.get('delivery_fee', 0))
        pricing.quote(items, discount, fee)
        s.validate_order_references({'items': items}, x_session_token)
        snapshot = order.get('tax_snapshot') or {}
        changed = items != order['items'] or discount != order.get('discount', 0) or fee != order.get('delivery_fee', 0)
        if snapshot.get('engine_version') == 2:
            rows, _, _ = s.payment_totals(order_id, order['total'])
            if changed and rows:
                raise HTTPException(409, 'Taxed invoice pricing is frozen after a payment; create a new order or adjustment')
            return quote(s, items, discount, fee, snapshot=snapshot)
        if snapshot or order.get('tax'):
            if changed:
                raise HTTPException(409, 'Historical invoices with recorded tax are read-only for repricing; create a new order')
            return {k: order.get(k) for k in ['subtotal', 'discount', 'delivery_fee', 'tax', 'tax_snapshot', 'total']}
        return {**pricing.quote(items, discount, fee), 'tax': 0, 'tax_snapshot': None}
