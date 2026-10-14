"""Service-store tax rules, decimal calculation and immutable order rate snapshots."""
import json
import re
import uuid
import locations
from copy import deepcopy
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import Header,HTTPException
from tenant_scope import current_scope,ScopedMemoryDict
VERSION='location-taxes-v1'
CENT=Decimal('0.01')
memory_rules=ScopedMemoryDict()

def number(value,label='Amount'):
    if isinstance(value,bool):raise HTTPException(400,label+' must be a finite non-negative number')
    try:d=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError):raise HTTPException(400,'Invalid '+label.lower())
    if not d.is_finite() or d<0 or d>Decimal('100000000'):raise HTTPException(400,'Invalid '+label.lower())
    return d

def money(value):return number(value).quantize(CENT,rounding=ROUND_HALF_UP)
def iso_date(value):
    try:
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError()
        return date.fromisoformat(value)
    except ValueError:raise HTTPException(400,'Dates must use YYYY-MM-DD')
def install(conn):
    if conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s',(VERSION,)).fetchone():return
    conn.execute('''CREATE TABLE tax_rules(id TEXT PRIMARY KEY,business_id TEXT NOT NULL,location_id TEXT NOT NULL,payload JSONB NOT NULL,
        FOREIGN KEY(location_id,business_id) REFERENCES stores(id,brand_id))''')
    conn.execute('ALTER TABLE tax_rules ENABLE ROW LEVEL SECURITY');conn.execute('ALTER TABLE tax_rules FORCE ROW LEVEL SECURITY')
    pred="business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),'')"
    conn.execute(f"CREATE POLICY tax_scope ON tax_rules USING (current_setting('app.maintenance',true)='on' OR ({pred})) WITH CHECK (current_setting('app.maintenance',true)='on' OR ({pred}))")
    conn.execute('CREATE INDEX tax_rule_scope ON tax_rules(business_id,location_id)')
    conn.execute("ALTER TABLE payment_transactions ADD COLUMN tax_amount NUMERIC NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE payment_transactions ADD COLUMN tax_breakdown JSONB NOT NULL DEFAULT '[]'::jsonb")
    conn.execute('INSERT INTO fabclean_schema_migrations(version) VALUES (%s)',(VERSION,))

def location(s):
    brand,store=current_scope.get() or ('fabclean','main')
    if s.DATABASE_URL:
        with s.db() as conn:row=conn.execute('SELECT country,state,city,postal_code,timezone FROM stores WHERE id=%s AND brand_id=%s',(store,brand)).fetchone()
        if not row:raise HTTPException(404,'Active service store not found')
        result=dict(row)
    else:result={'country':'US','state':'','city':'','postal_code':'','timezone':'UTC'}
    return {'business_id':brand,'location_id':store,**result}

def store_date(loc,instant=None):
    try:tz=ZoneInfo(loc.get('timezone') or 'UTC')
    except ZoneInfoNotFoundError:raise HTTPException(409,'Configure a valid store timezone before calculating tax')
    return (instant or datetime.now(timezone.utc)).astimezone(tz).date().isoformat()

def rules(s):
    if not s.DATABASE_URL:return [deepcopy(v) for v in memory_rules.values()]
    with s.db() as conn:return [r['payload'] for r in conn.execute('SELECT payload FROM tax_rules ORDER BY id').fetchall()]

def normalized(text):return str(text or '').strip().casefold()
def canonical_location(loc):return {**loc,'country':locations.country(loc.get('country')),'state':locations.state(loc.get('state'),loc.get('country'))}
def validate_rule(value):
    fields={'component','jurisdiction','country','state','city','postal_code','rate','effective_from','effective_to'}
    if not isinstance(value,dict) or set(value)-fields:raise HTTPException(400,'Unsupported tax-rule fields')
    r={'city':'','postal_code':'','effective_to':None,**value}
    for key in ('component','jurisdiction','country','state','city','postal_code'):
        if not isinstance(r.get(key),str) or len(r[key])>120:raise HTTPException(400,'Invalid jurisdiction fields')
        r[key]=r[key].strip()
    if not re.fullmatch('[a-z][a-z0-9_-]{0,39}',r['component']) or not r['jurisdiction'] or not re.fullmatch('[A-Za-z]{2}',r['country']) or not r['state']:raise HTTPException(400,'Component, jurisdiction, country and state are required')
    locations.validate_location(r);rate=number(r.get('rate'),'Rate')
    if rate>100 or rate.as_tuple().exponent<-4:raise HTTPException(400,'Rate must be 0–100 percent with at most four decimal places')
    r['rate']=str(rate)
    start=iso_date(r.get('effective_from'));end=iso_date(r['effective_to']) if r['effective_to'] else None
    if end and end<=start:raise HTTPException(400,'Effective end must follow start (end is exclusive)')
    return r

def same_selector(a,b):return all(normalized(a.get(k))==normalized(b.get(k)) for k in ('component','country','state','city','postal_code'))
def overlaps(a,b):return a['effective_from']<(b.get('effective_to') or '9999-12-31') and b['effective_from']<(a.get('effective_to') or '9999-12-31')
def selected(rates,loc,day):
    loc=canonical_location(loc)
    rates=[{**r,**{k:canonical_location(r)[k] for k in ('country','state')}} for r in rates]
    matches=[r for r in rates if not r.get('voided') and r['effective_from']<=day and (not r.get('effective_to') or day<r['effective_to']) and all(not r.get(k) or normalized(r[k])==normalized(loc.get(k)) for k in ('country','state','city','postal_code'))]
    components={}
    for r in matches:
        specificity=(bool(r.get('postal_code')),bool(r.get('city')))
        old=components.get(r['component'])
        if old and specificity==old[0]:raise HTTPException(409,'Ambiguous tax rules; correct overlapping jurisdiction selectors')
        if not old or specificity>old[0]:components[r['component']]=(specificity,r)
    return [{'rule_id':r['id'],'component':key,'jurisdiction':r['jurisdiction'],'rate':r['rate'],**({'provenance':deepcopy(r['provenance'])} if r.get('provenance') else {})} for key,(_,r) in sorted(components.items())]

def allocate(total,weights):
    """Largest remainder in cents, with line index as the deterministic tie breaker."""
    if not weights or sum(weights)==0:return [Decimal(0) for _ in weights]
    raw=[total*w/sum(weights) for w in weights];base=[v.quantize(CENT,rounding='ROUND_DOWN') for v in raw]
    remainder=int((total-sum(base))/CENT)
    order=sorted(range(len(raw)),key=lambda i:(-(raw[i]-base[i]),i))
    for index in order[:remainder]:base[index]+=CENT
    return base

def calculate(s,items,discount=0,delivery_fee=0,frozen=None):
    if not isinstance(items,list) or len(items)>500:raise HTTPException(400,'Invalid estimate items')
    if frozen and not frozen.get('lines'):frozen=None
    catalog={v['id']:v for v in s.get_service_values(include_inactive=True)}
    old_lines={v['service_id']:v for v in (frozen or {}).get('lines',[])}
    bases=[];services=[]
    for item in items:
        if not isinstance(item,dict) or item.get('service_id') not in catalog:raise HTTPException(404,'Service not found in the active store')
        quantity=number(item.get('quantity',1),'Quantity');price=number(item.get('unit_price',0),'Unit price')
        if quantity<=0:raise HTTPException(400,'Quantity must be greater than zero')
        bases.append(money(quantity*price));services.append(catalog[item['service_id']])
    subtotal=sum(bases,Decimal(0));reduction=money(discount);fee=money(delivery_fee)
    if reduction>subtotal:raise HTTPException(400,'Discount exceeds the item subtotal')
    loc=deepcopy(frozen['location']) if frozen else location(s);day=frozen['service_date'] if frozen else store_date(loc)
    fee_taxable=frozen.get('delivery_fee_taxable',False) if frozen else bool(s.get_settings_value().get('delivery_fee_taxable',False))
    taxable=[old_lines.get(v['id'],v).get('taxable',False) for v in services]
    if frozen:
        components=deepcopy(frozen['components']);source=frozen['source']
        if source=='store_rules' and (any(taxable) or (fee_taxable and fee)) and not components:raise HTTPException(409,'Saved jurisdiction has no effective rates for taxable pricing; create a new verified order')
    else:
        rates=rules(s);components=selected(rates,loc,day);source='store_rules'
        if (any(taxable) or (fee_taxable and fee)) and (not loc.get('country') or not loc.get('state') or not components):raise HTTPException(409,'Configure verified location tax rules before pricing taxable services; per-service rates cannot establish the store jurisdiction')
    discounts=allocate(reduction,bases)
    if fee_taxable and fee:
        if source!='store_rules':raise HTTPException(409,'Configure store tax rules before taxing delivery fees')
        items=[*items,{'service_id':'__delivery_fee'}];services=[*services,{'id':'__delivery_fee','taxable':True,'tax_rate':0}];bases.append(fee);discounts.append(Decimal(0));taxable.append(True)
    lines=[];totals={}
    for index,(item,service,base,off,is_taxable) in enumerate(zip(items,services,bases,discounts,taxable)):
        active=components
        legacy_rate=old_lines.get(service['id'],service).get('service_rate',service.get('tax_rate',0))
        if number(legacy_rate,'Rate')>100:raise HTTPException(400,'Service tax rate must be 0–100 percent')
        if source=='legacy_service_rates':active=[{'rule_id':None,'component':'service-'+service['id'],'jurisdiction':'Service configured tax','rate':str(number(legacy_rate,'Rate'))}]
        line_components=[]
        for component in active:
            tax=money((base-off)*number(component['rate'],'Rate')/100) if is_taxable else Decimal(0)
            entry={**component,'taxable_base':float(base-off) if is_taxable else 0,'amount':float(tax)};line_components.append(entry)
            key=(component['component'],component['jurisdiction'],component['rate'],component.get('rule_id'))
            if key not in totals:totals[key]={**component,'amount':Decimal(0),'taxable_base':Decimal(0)}
            totals[key]['amount']+=tax;totals[key]['taxable_base']+=(base-off) if is_taxable else Decimal(0)
        lines.append({'index':index,'service_id':item['service_id'],'taxable':bool(is_taxable),'service_rate':str(legacy_rate),'base':float(base),'discount':float(off),'taxable_base':float(base-off) if is_taxable else 0,'exemption_reason':None if is_taxable else 'Service is exempt','components':line_components,'tax':round(sum(v['amount'] for v in line_components),2)})
    breakdown=[{**v,'amount':float(v['amount']),'taxable_base':float(v['taxable_base'])} for v in totals.values()]
    tax=sum((money(v['amount']) for v in breakdown),Decimal(0))
    snapshot={'version':1,'source':source,'service_date':day,'currency':frozen.get('currency') if frozen else s.get_settings_value().get('currency','USD'),'location':loc,'components':components,'lines':lines,'breakdown':breakdown,'delivery_fee_taxable':bool(fee_taxable),'rounding':'line-component HALF_UP cents; proportional discount largest remainder','calculated_at':datetime.now(timezone.utc).isoformat()}
    return {'subtotal':float(subtotal),'discount':float(reduction),'delivery_fee':float(fee),'tax':float(tax),'total':float(subtotal-reduction+fee+tax),'tax_snapshot':snapshot}

def refund(order,rows,amount):
    gross=money(amount);total=money(order.get('total',0));net_paid=sum(Decimal(str(r['amount'])) for r in rows)
    prior=[r for r in rows if r.get('transaction_type')=='refund'];refunded=sum(abs(Decimal(str(r['amount']))) for r in prior)
    if gross<=0 or gross>net_paid or gross+refunded>total:raise HTTPException(409,'Refund exceeds the paid balance or unrefunded order total')
    breakdown=(order.get('tax_snapshot') or {}).get('breakdown') or ([{'component':'legacy-manual','jurisdiction':'Legacy recorded tax','rate':None,'amount':order.get('tax',0)}] if order.get('tax') else [])
    originals=[money(entry['amount']) for entry in breakdown]
    total_tax=sum(originals,Decimal(0))
    if total_tax>total:raise HTTPException(409,'Saved tax exceeds the invoice total; review the legacy record before refunding')
    credited=[Decimal(0) for _ in originals];running=Decimal(0)
    def cumulative(value):return money(total_tax*value/total) if total else Decimal(0)
    for row in prior:
        prior_gross=abs(Decimal(str(row['amount'])));increment=cumulative(running+prior_gross)-cumulative(running)
        running+=prior_gross
        recorded={entry['component']:money(entry['amount']) for entry in row.get('tax_breakdown') or []}
        if recorded:
            portions=[recorded.get(entry['component'],Decimal(0)) for entry in breakdown]
        else:
            # Legacy tax is not transferred into this refund or backfilled into old rows.
            portions=allocate(increment,[max(Decimal(0),original-used) for original,used in zip(originals,credited)])
        credited=[used+portion for used,portion in zip(credited,portions)]
    credit=cumulative(refunded+gross)-cumulative(refunded)
    remaining=[max(Decimal(0),original-used) for original,used in zip(originals,credited)]
    if credit>sum(remaining):raise HTTPException(409,'Historical refund tax conflicts with this saved invoice')
    portions=allocate(credit,remaining)
    result=[{**entry,'amount':float(portion)} for entry,portion in zip(breakdown,portions)]
    return float(credit),result

def register(app,s):
    @app.get('/api/taxes/rules')
    def get_rules(x_session_token:str|None=Header(default=None)):
        s.require_permission('admin',x_session_token)
        loc=canonical_location(location(s));day=store_date(loc);saved=rules(s);effective=selected(saved,loc,day)
        taxable=[v['name'] for v in s.get_service_values() if v.get('taxable')]
        return {'rules':saved,'location':loc,'service_date':day,'diagnostics':{'effective_components':effective,'taxable_services':taxable,'status':'location_rules_active' if effective else 'missing_location_rules','message':('Location rates match the saved store. '+('Taxable services: '+', '.join(taxable) if taxable else 'All services are exempt; mark applicable services taxable to calculate tax.')) if effective else 'No current location rule matches this store. Add the correct rates for its saved country/state and effective date. ZIP lookup does not supply tax rates.'}}

    @app.post('/api/taxes/rules')
    def create(payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_permission('admin',x_session_token);row=validate_rule(payload);row['id']=str(uuid.uuid4())
        def mutate():
            for existing in rules(s):
                if not existing.get('voided') and same_selector(existing,row) and overlaps(existing,row):raise HTTPException(409,'Rate dates overlap an existing rule for this component and jurisdiction')
            if not s.DATABASE_URL:memory_rules[row['id']]=row
            else:
                with s.db() as conn:
                    conn.execute('INSERT INTO tax_rules(id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb)',(row['id'],*current_scope.get(),json.dumps(row)))
                    s.platform_audit_write(conn,actor,'tax_rule_created',current_scope.get()[0],{'store_id':current_scope.get()[1],'rule_id':row['id']})
            return row
        if not s.DATABASE_URL:return mutate()
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,current_scope.get()[0]);marker=s.transaction_connection.set(conn)
            try:return mutate()
            finally:s.transaction_connection.reset(marker)

    @app.post('/api/taxes/rules/{rule_id}/end')
    def end(rule_id:str,payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_permission('admin',x_session_token)
        if set(payload)!={'effective_to'}:raise HTTPException(400,'Supply effective_to only')
        day=iso_date(payload['effective_to']).isoformat()
        def mutate():
            row=next((r for r in rules(s) if r['id']==rule_id),None)
            if not row:raise HTTPException(404,'Tax rule not found')
            if day<=row['effective_from']:raise HTTPException(400,'End must follow start')
            if row.get('effective_to') and day>row['effective_to']:raise HTTPException(409,'An existing end can only be shortened')
            row['effective_to']=day
            if not s.DATABASE_URL:memory_rules[rule_id]=row
            else:
                with s.db() as conn:
                    conn.execute('UPDATE tax_rules SET payload=%s::jsonb WHERE id=%s',(json.dumps(row),rule_id))
                    s.platform_audit_write(conn,actor,'tax_rule_ended',current_scope.get()[0],{'store_id':current_scope.get()[1],'rule_id':rule_id,'effective_to':day})
            return row
        if not s.DATABASE_URL:return mutate()
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,current_scope.get()[0]);marker=s.transaction_connection.set(conn)
            try:return mutate()
            finally:s.transaction_connection.reset(marker)

    @app.post('/api/taxes/rules/{rule_id}/void')
    def void(rule_id:str,payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_permission('admin',x_session_token);reason=payload.get('reason')
        if set(payload)!={'reason'} or not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise HTTPException(400,'A reason of 1–500 characters is required')
        def mutate():
            row=next((r for r in rules(s) if r['id']==rule_id),None)
            if not row:raise HTTPException(404,'Tax rule not found')
            if row.get('voided'):raise HTTPException(409,'Tax rule is already voided')
            row['voided']=True
            if not s.DATABASE_URL:memory_rules[rule_id]=row
            else:
                with s.db() as conn:
                    conn.execute('UPDATE tax_rules SET payload=%s::jsonb WHERE id=%s',(json.dumps(row),rule_id))
                    s.platform_audit_write(conn,actor,'tax_rule_voided',current_scope.get()[0],{'store_id':current_scope.get()[1],'rule_id':rule_id,'reason':reason.strip()})
            return row
        if not s.DATABASE_URL:return mutate()
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,current_scope.get()[0]);marker=s.transaction_connection.set(conn)
            try:return mutate()
            finally:s.transaction_connection.reset(marker)

    @app.post('/api/taxes/estimate')
    def estimate(payload:dict,x_session_token:str|None=Header(default=None)):
        s.require_permission('orders',x_session_token)
        if set(payload)-{'items','discount','delivery_fee','promo_code','customer_id','order_id'}:raise HTTPException(400,'Estimate jurisdiction and rates come from the server')
        frozen=None
        if payload.get('order_id'):
            order=s.get_order(payload['order_id'],x_session_token);order=order.model_dump(mode='json') if hasattr(order,'model_dump') else dict(order);frozen=order.get('tax_snapshot')
        items=payload.get('items',[]);discount=payload.get('discount',0)
        if payload.get('order_id') and not frozen and not payload.get('promo_code') and items==order.get('items') and money(discount)==money(order.get('discount',0)) and money(payload.get('delivery_fee',0))==money(order.get('delivery_fee',0)):
            return {key:order.get(key,0) for key in ('subtotal','discount','delivery_fee','tax','total','tax_snapshot')}
        subtotal=calculate(s,items,0,payload.get('delivery_fee',0),frozen)['subtotal']
        if payload.get('customer_id'):s.get_customer(payload['customer_id'],x_session_token)
        if payload.get('promo_code'):
            offer,discount=s.find_valid_offer(payload['promo_code'],subtotal,payload.get('customer_id'))
            if not offer:raise HTTPException(400,'Promo code is not active or eligible')
        return calculate(s,items,discount,payload.get('delivery_fee',0),frozen)

    @app.get('/api/financial/taxes')
    def report(from_date:str,to_date:str,x_session_token:str|None=Header(default=None)):
        s.require_permission('admin',x_session_token);start=iso_date(from_date);end=iso_date(to_date)
        if end<start or (end-start).days>366:raise HTTPException(400,'Report range must be at most 366 days')
        loc=location(s);components={};count=0;unclassified_refunds=0
        orders=s.get_order_values();order_taxes={o['id']:o.get('tax',0) for o in orders}
        def add(entry,kind):
            key=(entry['component'],entry['jurisdiction'],entry.get('rate'))
            if key not in components:components[key]={'component':key[0],'jurisdiction':key[1],'rate':key[2],'billed_tax':Decimal(0),'refunded_tax':Decimal(0)}
            components[key][kind]+=money(entry['amount'])
        for order in orders:
            snapshot=order.get('tax_snapshot') or {};day=snapshot.get('service_date') or store_date(loc,datetime.fromisoformat(str(order['created_at']).replace('Z','+00:00')))
            if from_date<=day<=to_date:
                count+=1
                breakdown=snapshot.get('breakdown') or ([{'component':'legacy-manual','jurisdiction':'Legacy recorded tax','rate':None,'amount':order['tax']}] if order.get('tax') else [])
                for entry in breakdown:add(entry,'billed_tax')
        if not s.DATABASE_URL:rows=[r for r in s.memory_payments if r.get('order_id') in {o['id'] for o in s.get_order_values()}]
        else:
            with s.db() as conn:rows=[dict(r) for r in conn.execute("SELECT * FROM payment_transactions WHERE transaction_type='refund'").fetchall()]
        for row in rows:
            stamp=row.get('created_at');stamp=stamp if isinstance(stamp,datetime) else datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if from_date<=store_date(loc,stamp)<=to_date:
                if not row.get('tax_breakdown') and order_taxes.get(row['order_id'],0):unclassified_refunds+=1
                for entry in row.get('tax_breakdown') or []:add(entry,'refunded_tax')
        entries=[{**v,'billed_tax':float(v['billed_tax']),'refunded_tax':float(v['refunded_tax']),'net_tax':float(v['billed_tax']-v['refunded_tax'])} for v in components.values()]
        return {'from_date':from_date,'to_date':to_date,'basis':'invoiced service-store date; refunds on local transaction date','location':loc,'order_count':count,'unclassified_refunds':unclassified_refunds,'components':entries,'billed_tax':round(sum(v['billed_tax'] for v in entries),2),'refunded_tax':round(sum(v['refunded_tax'] for v in entries),2),'net_tax':round(sum(v['net_tax'] for v in entries),2)}
