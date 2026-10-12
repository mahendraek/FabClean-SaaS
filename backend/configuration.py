"""Brand defaults and explicit store overrides; all persistence is forced-RLS scoped."""
import json
import math
import re
import uuid
from copy import deepcopy
from threading import RLock
from datetime import datetime, timezone
from fastapi import Header, HTTPException
from pydantic import ValidationError
from models import Service
from tenant_scope import current_scope, ScopedMemoryDict

VERSION='configuration-inheritance-v1'
EMPTY={'settings':{},'services':{},'offers':{}}
memory_brands={}
memory_lock=RLock()
memory_overrides=ScopedMemoryDict()
memory_usage=ScopedMemoryDict()
SETTING_KEYS={'delivery_fee_taxable','business_name','business_address','business_phone','currency','barcode_mode','service_coverage_mode','service_radius_miles','pickup_delivery_slot_minutes','service_area_notes','hardware_profile','pickup_enabled','delivery_enabled','rewards_enabled','offers_enabled','referrals_enabled','subscriptions_enabled','ai_assistance_enabled'}
OFFER_KEYS={'name','code','discount_type','discount_value','min_order','first_order_only','auto_apply','active','starts_at','ends_at','usage_limit'}

def install(conn):
    if conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s',(VERSION,)).fetchone():return
    conn.execute('''CREATE TABLE brand_configuration (business_id TEXT PRIMARY KEY REFERENCES brands(id), payload JSONB NOT NULL, revision INTEGER NOT NULL DEFAULT 1)''')
    conn.execute('''CREATE TABLE store_configuration (business_id TEXT NOT NULL, location_id TEXT NOT NULL, payload JSONB NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(business_id,location_id), FOREIGN KEY(location_id,business_id) REFERENCES stores(id,brand_id))''')
    conn.execute('''CREATE TABLE configuration_offer_usage (business_id TEXT NOT NULL,location_id TEXT NOT NULL,template_id TEXT NOT NULL,usage_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(business_id,location_id,template_id),FOREIGN KEY(location_id,business_id) REFERENCES stores(id,brand_id))''')
    for table,store in [('brand_configuration',False),('store_configuration',True),('configuration_offer_usage',True)]:
        predicate="business_id=NULLIF(current_setting('app.brand_id',true),'')"+(" AND location_id=NULLIF(current_setting('app.store_id',true),'')" if store else '')
        conn.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY');conn.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        conn.execute(f"CREATE POLICY configuration_scope ON {table} USING (current_setting('app.maintenance',true)='on' OR ({predicate})) WITH CHECK (current_setting('app.maintenance',true)='on' OR ({predicate}))")
    conn.execute('INSERT INTO fabclean_schema_migrations(version) VALUES (%s)',(VERSION,))

def scope():return current_scope.get() or ('fabclean','main')
def load(s,brand=False):
    if not s.DATABASE_URL:
        row=memory_brands.get(scope()[0]) if brand else memory_overrides.get('configuration')
    else:
        with s.db() as conn:
            row=conn.execute('SELECT payload,revision FROM '+('brand_configuration WHERE business_id=%s' if brand else 'store_configuration WHERE business_id=%s AND location_id=%s'),(scope()[0],) if brand else scope()).fetchone()
    return deepcopy(row) if row else {'payload':deepcopy(EMPTY),'revision':0}

def settings(s):
    brand=load(s,True)['payload']['settings']
    if not s.DATABASE_URL:local=dict(s.memory_settings)
    else:
        with s.db() as conn:row=conn.execute("SELECT payload FROM app_settings WHERE id='business'").fetchone()
        local=row['payload'] if row else {}
    return {**s.DEFAULT_SETTINGS,**brand,**local},local

def validate_settings(values):
    if not isinstance(values,dict) or set(values)-SETTING_KEYS:raise HTTPException(400,'Unsupported settings')
    for key,value in values.items():
        if value is None:continue
        if (key.endswith('_enabled') or key=='delivery_fee_taxable') and type(value) is not bool:raise HTTPException(400,'Capabilities must be booleans')
        if key in ('service_radius_miles','pickup_delivery_slot_minutes'):
            if type(value) not in (int,float) or not math.isfinite(value) or value<0 or value>10000 or (key=='pickup_delivery_slot_minutes' and (value<15 or value>1440 or value%1)):raise HTTPException(400,'Invalid fulfillment rule')
        elif key=='hardware_profile':
            if not isinstance(value,dict) or len(json.dumps(value))>10000:raise HTTPException(400,'Invalid hardware profile')
        elif not (key.endswith('_enabled') or key=='delivery_fee_taxable'):
            if not isinstance(value,str) or len(value)>2000:raise HTTPException(400,'Invalid setting text')
        if key=='barcode_mode' and value not in ('both','order','item'):raise HTTPException(400,'Invalid barcode mode')
        if key=='service_coverage_mode' and value not in ('radius','postal_codes'):raise HTTPException(400,'Invalid coverage mode')
        if key=='currency' and not re.fullmatch('[A-Z]{3}',value):raise HTTPException(400,'Currency requires a three-letter code')
    return values

def validate_service(value,key):
    allowed=set(Service.model_fields)-{'business_id','location_id'}
    if not isinstance(value,dict) or set(value)-allowed or (value.get('id',key)!=key):raise HTTPException(400,'Invalid service fields or ID')
    try:item=Service(**{**value,'id':key})
    except ValidationError:raise HTTPException(400,'Invalid service definition')
    for v in (item.base_price,item.minimum_price,item.tax_rate,item.express_surcharge_percent,*[v.price for v in item.variants],*[m.amount for m in item.modifiers]):
        if not math.isfinite(v) or v<0:raise HTTPException(400,'Prices and rates must be finite and non-negative')
    if not item.name.strip() or not item.category.strip() or len(item.name)>160 or item.turnaround_hours<0:raise HTTPException(400,'Invalid service name/category/turnaround')
    for field in allowed:
        if field.endswith('_enabled') or field.endswith('_eligible') or field in ('active','taxable'):
            if field in value and type(value[field]) is not bool:raise HTTPException(400,'Service flags must be booleans')
    return {k:v for k,v in item.model_dump(mode='json').items() if k in allowed}

def validate_offer(value,key):
    if not isinstance(value,dict) or set(value)-OFFER_KEYS:raise HTTPException(400,'Invalid offer fields')
    item={'name':'','code':None,'discount_type':'fixed','discount_value':0,'min_order':0,'first_order_only':False,'auto_apply':False,'active':True,'starts_at':None,'ends_at':None,'usage_limit':None,**value}
    if not isinstance(item['name'],str) or not item['name'].strip() or len(item['name'])>160:raise HTTPException(400,'Offer name is required')
    if item['discount_type'] not in ('fixed','percent'):raise HTTPException(400,'Invalid discount type')
    for field in ('discount_value','min_order'):
        v=item[field]
        if type(v) not in (float,int) or not math.isfinite(v) or v<0:raise HTTPException(400,'Invalid offer amount')
    if item['discount_type']=='percent' and item['discount_value']>100:raise HTTPException(400,'Percentage must not exceed 100')
    for field in ('first_order_only','auto_apply','active'):
        if type(item[field]) is not bool:raise HTTPException(400,'Offer flags must be booleans')
    if item['usage_limit'] is not None and (type(item['usage_limit']) is not int or item['usage_limit']<1):raise HTTPException(400,'Invalid usage limit')
    dates=[]
    for field in ('starts_at','ends_at'):
        if item[field] is not None:
            try:dates.append(datetime.fromisoformat(item[field].replace('Z','+00:00')))
            except (TypeError,ValueError,AttributeError):raise HTTPException(400,'Invalid offer date')
            if dates[-1].tzinfo is None:raise HTTPException(400,'Offer dates require a timezone')
    if len(dates)==2 and dates[0]>=dates[1]:raise HTTPException(400,'Offer end must follow start')
    if item['code'] is not None:
        if not isinstance(item['code'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}',item['code']):raise HTTPException(400,'Invalid offer code')
        item['code']=item['code'].upper()
    return item

def service_values(s,local,include_inactive=False):
    templates=load(s,True)['payload']['services'];overrides=load(s)['payload']['services']
    values={key:{**value,**overrides.get(key,{}),'id':key,'business_id':scope()[0],'location_id':scope()[1]} for key,value in templates.items()}
    values.update({v['id']:v for v in local})
    return [v for _,v in sorted(values.items()) if include_inactive or v.get('active',True)]

def offer_values(s,include_inactive=False):
    templates=load(s,True)['payload']['offers'];overrides=load(s)['payload']['offers']
    if not s.DATABASE_URL:local=list(s.memory_catalogs['offers'].values());counts=dict(memory_usage)
    else:
        with s.db() as conn:
            local=[dict(r) for r in conn.execute('SELECT * FROM offers ORDER BY created_at DESC').fetchall()]
            counts={r['template_id']:r['usage_count'] for r in conn.execute('SELECT template_id,usage_count FROM configuration_offer_usage').fetchall()}
    codes={str(v.get('code') or '').upper() for v in local if v.get('code')}
    values=list(local)
    for key,value in sorted(templates.items()):
        row=validate_offer({**value,**overrides.get(key,{})},key)
        if row.get('code') and row['code'].upper() in codes:continue
        row.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([*scope(),key]))),template_id=key,business_id=scope()[0],location_id=scope()[1],usage_count=counts.get(key,0))
        values.append(row)
    return [v for v in values if include_inactive or v.get('active',True)]

def consume_offer(s,conn,offer):
    key=offer.get('template_id')
    if not s.DATABASE_URL:
        if key:memory_usage[key]=memory_usage.get(key,0)+1
        else:s.memory_catalogs['offers'][offer['id']]={**offer,'usage_count':offer.get('usage_count',0)+1}
    elif key:
        conn.execute('INSERT INTO configuration_offer_usage(business_id,location_id,template_id,usage_count) VALUES (%s,%s,%s,1) ON CONFLICT(business_id,location_id,template_id) DO UPDATE SET usage_count=configuration_offer_usage.usage_count+1',(*scope(),key))
    else:conn.execute('UPDATE offers SET usage_count=usage_count+1 WHERE id=%s',(offer['id'],))

def save_settings(s,values):
    validate_settings(values)
    _,local=settings(s)
    for key,value in values.items():
        if value is None:local.pop(key,None)
        else:local[key]=value
    if not s.DATABASE_URL:s.memory_settings.clear();s.memory_settings.update(local)
    else:
        with s.db() as conn:conn.execute("INSERT INTO app_settings(id,payload) VALUES ('business',%s::jsonb) ON CONFLICT(business_id,location_id,id) DO UPDATE SET payload=EXCLUDED.payload",(json.dumps(local),))
    return settings(s)[0]

def snapshot(s):
    brand=load(s,True);store=load(s);effective,local=settings(s)
    services=s.get_service_values(True);offers=offer_values(s,True)
    if not s.DATABASE_URL:local_service_ids=set(s.memory_services)
    else:
        with s.db() as conn:local_service_ids={r['id'] for r in conn.execute('SELECT id FROM services').fetchall()}
    return {'system_settings':deepcopy(s.DEFAULT_SETTINGS),'brand':brand,'store':store,'local_settings':local,'settings':effective,'settings_sources':{k:'store' if k in local else 'brand' if k in brand['payload']['settings'] else 'system' for k in effective},'services':services,'service_sources':{v['id']:'store' if v['id'] in local_service_ids or v['id'] in store['payload']['services'] else 'brand' for v in services},'offers':offers,'can_edit_brand':False}

def register(app,s):
    @app.get('/api/configuration')
    def get(x_session_token:str|None=Header(default=None)):
        staff=s.require_permission('admin',x_session_token);result=snapshot(s)
        result['can_edit_brand']=s.has_role(staff,'super_admin') or s.has_role(staff,'brand_admin',brand_id=scope()[0])
        return result

    @app.put('/api/configuration/{level}')
    def update(level:str,payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_permission('admin',x_session_token)
        if level not in ('brand','store'):raise HTTPException(404,'Configuration level not found')
        brand=level=='brand'
        if brand:s.require_brand_admin_for(scope()[0],x_session_token)
        if set(payload)-{'revision','settings','services','offers'}:raise HTTPException(400,'Unsupported configuration sections')
        if len(json.dumps(payload))>200000:raise HTTPException(400,'Configuration is too large')
        def mutate():
            current=load(s,brand)
            if type(payload.get('revision')) is not int or payload['revision']!=current['revision']:raise HTTPException(409,'Configuration changed; refresh before saving')
            document=current['payload'];templates=load(s,True)['payload']
            if 'settings' in payload:
                validate_settings(payload['settings'])
                if brand:
                    document['settings']={k:v for k,v in payload['settings'].items() if v is not None}
                else:save_settings(s,payload['settings'])
            for section,validator in [('services',validate_service),('offers',validate_offer)]:
                if section not in payload:continue
                values=payload[section]
                if not isinstance(values,dict) or len(values)>300:raise HTTPException(400,'Invalid catalogue')
                if brand:
                    document[section]={}
                    for key,value in values.items():
                        if not re.fullmatch('[A-Za-z0-9_-]{1,100}',key):raise HTTPException(400,'Invalid template ID')
                        document[section][key]=validator(value,key)
                else:
                    for key,value in values.items():
                        if key not in templates[section]:raise HTTPException(404,'Brand template not found')
                        if value is None:
                            document[section].pop(key,None)
                            if section=='services':
                                if not s.DATABASE_URL:s.memory_services.pop(key,None)
                                else:
                                    with s.db() as conn:conn.execute('DELETE FROM services WHERE id=%s',(key,))
                        else:
                            if not isinstance(value,dict):raise HTTPException(400,'Overrides must be objects or null')
                            legacy={}
                            if section=='services':
                                if not s.DATABASE_URL:
                                    local=s.memory_services.get(key)
                                    legacy=local.model_dump(mode='json') if local is not None else {}
                                else:
                                    with s.db() as conn:
                                        local=conn.execute('SELECT payload,active FROM services WHERE id=%s',(key,)).fetchone()
                                        if local:legacy={**local['payload'],'active':local['active']}
                                legacy={k:v for k,v in legacy.items() if k in Service.model_fields and k not in ('business_id','location_id')}
                            combined={**legacy,**document[section].get(key,{}),**value}
                            validator({**templates[section][key],**combined},key)
                            if section=='services':
                                if not s.DATABASE_URL:s.memory_services.pop(key,None)
                                else:
                                    with s.db() as conn:conn.execute('DELETE FROM services WHERE id=%s',(key,))
                            document[section][key]=deepcopy(combined)
            if brand:
                validate_inheriting_stores(s,document)
                codes=[v['code'] for v in document['offers'].values() if v['code']]
                if len(codes)!=len(set(codes)):raise HTTPException(409,'Brand offer codes must be unique')
            if not brand:validate_resolved_catalogue(templates,document)
            revision=current['revision']+1
            if not s.DATABASE_URL:
                row={'payload':document,'revision':revision}
                if brand:memory_brands[scope()[0]]=row
                else:memory_overrides['configuration']=row
            else:
                with s.db() as conn:
                    table='brand_configuration' if brand else 'store_configuration'
                    if brand:conn.execute(f'INSERT INTO {table}(business_id,payload,revision) VALUES (%s,%s::jsonb,%s) ON CONFLICT(business_id) DO UPDATE SET payload=EXCLUDED.payload,revision=EXCLUDED.revision',(scope()[0],json.dumps(document),revision))
                    else:conn.execute(f'INSERT INTO {table}(business_id,location_id,payload,revision) VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT(business_id,location_id) DO UPDATE SET payload=EXCLUDED.payload,revision=EXCLUDED.revision',(*scope(),json.dumps(document),revision))
                    s.platform_audit_write(conn,actor,'configuration_'+level+'_updated',scope()[0],{'store_id':None if brand else scope()[1],'revision':revision,'sections':[k for k in payload if k!='revision']})
            result=snapshot(s)
            result['can_edit_brand']=s.has_role(actor,'super_admin') or s.has_role(actor,'brand_admin',brand_id=scope()[0])
            return result
        if not s.DATABASE_URL:
            with memory_lock:
                saved=deepcopy((memory_brands,memory_overrides.buckets,s.memory_settings.buckets,s.memory_services.buckets))
                try:return mutate()
                except Exception:
                    memory_brands.clear();memory_brands.update(saved[0]);memory_overrides.buckets=saved[1];s.memory_settings.buckets=saved[2];s.memory_services.buckets=saved[3]
                    raise
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,scope()[0])
            marker=s.transaction_connection.set(conn)
            try:return mutate()
            finally:s.transaction_connection.reset(marker)

def store_patch(s,section,key,patch,actor):
    """Existing catalogue editors also create explicit, revisioned store overrides."""
    def mutate():
        current=load(s);template=load(s,True)['payload'][section].get(key)
        if template is None:raise HTTPException(404,'Brand template not found')
        combined={**current['payload'][section].get(key,{}),**patch}
        (validate_service if section=='services' else validate_offer)({**template,**combined},key)
        current['payload'][section][key]=combined;current['revision']+=1
        if not s.DATABASE_URL:memory_overrides['configuration']=current
        else:
            with s.db() as conn:
                conn.execute('INSERT INTO store_configuration(business_id,location_id,payload,revision) VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT(business_id,location_id) DO UPDATE SET payload=EXCLUDED.payload,revision=EXCLUDED.revision',(*scope(),json.dumps(current['payload']),current['revision']))
                s.platform_audit_write(conn,actor,'configuration_store_updated',scope()[0],{'store_id':scope()[1],'revision':current['revision'],'sections':[section]})
    if not s.DATABASE_URL:return mutate()
    with s.db() as conn,conn.transaction():
        s.lock_brand_operations(conn,scope()[0]);marker=s.transaction_connection.set(conn)
        try:return mutate()
        finally:s.transaction_connection.reset(marker)

def validate_resolved_catalogue(templates,overrides):
    codes=[]
    for section,validator in [('services',validate_service),('offers',validate_offer)]:
        for key,value in templates[section].items():
            item=validator({**value,**overrides[section].get(key,{})},key)
            if section=='offers' and item['code']:codes.append(item['code'])
    if len(codes)!=len(set(codes)):raise HTTPException(409,'Effective offer codes must be unique')

def validate_inheriting_stores(s,templates):
    """Brand admins may validate stores in their brand using scoped RLS, never maintenance."""
    if not s.DATABASE_URL:
        rows=[v.get('configuration',{'payload':deepcopy(EMPTY)}) for (brand,_),v in memory_overrides.buckets.items() if brand==scope()[0]]
    else:
        rows=[]
        with s.db() as conn:
            stores=conn.execute('SELECT id FROM stores WHERE brand_id=%s',(scope()[0],)).fetchall()
            try:
                for store in stores:
                    conn.execute("SELECT set_config('app.store_id',%s,true)",(store['id'],))
                    row=conn.execute('SELECT payload FROM store_configuration WHERE business_id=%s AND location_id=%s',(scope()[0],store['id'])).fetchone()
                    if row:rows.append(row)
            finally:conn.execute("SELECT set_config('app.store_id',%s,true)",(scope()[1],))
    for row in rows:
        try:validate_resolved_catalogue(templates,row['payload'])
        except HTTPException:raise HTTPException(409,'A store override conflicts with these brand defaults; update the override first')
