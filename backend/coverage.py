"""Store-scoped delivery coverage. OSM renders the map; eligibility is local math.

Coverage is opt-in for existing stores. Once enabled, every new pickup/delivery
order and every address/fulfillment change must pass the server check. Historical
snapshots are retained for unrelated edits. Customer pins are explicitly entered,
not geocoded or inferred from device/IP/tax jurisdiction.
"""
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from fastapi import Header, HTTPException
from tenant_scope import ScopedMemoryDict, current_scope

VERSION = 'service-area-maps-v1'
MAX_LAT = 85.05112878  # Web Mercator / OSM tile extent.
EARTH_KM = 6371.0088
memory = ScopedMemoryDict()
lock = RLock()

def coordinate(value, latitude=True):
    limit = MAX_LAT if latitude else 180
    if type(value) not in (int, float) or not math.isfinite(value) or not -limit <= value <= limit:
        raise HTTPException(400, 'Coordinates must be finite numbers within the map extent')
    return float(value)

def point(value):
    if not isinstance(value, dict) or set(value) != {'latitude', 'longitude'}:
        raise HTTPException(400, 'Supply latitude and longitude only')
    return {'latitude': coordinate(value['latitude']), 'longitude': coordinate(value['longitude'], False)}

def distance_km(a, b):
    lat1, lat2 = math.radians(a['latitude']), math.radians(b['latitude'])
    dlat = lat2-lat1; dlon = math.radians(b['longitude']-a['longitude'])
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*EARTH_KM*math.asin(math.sqrt(min(1, max(0, h))))

def cross(a, b, c):
    return (b['longitude']-a['longitude'])*(c['latitude']-a['latitude'])-(b['latitude']-a['latitude'])*(c['longitude']-a['longitude'])

def on_edge(p, a, b):
    return abs(cross(a,b,p)) <= 1e-10 and min(a['latitude'],b['latitude'])-1e-10 <= p['latitude'] <= max(a['latitude'],b['latitude'])+1e-10 and min(a['longitude'],b['longitude'])-1e-10 <= p['longitude'] <= max(a['longitude'],b['longitude'])+1e-10

def intersects(a, b, c, d):
    x1,x2,x3,x4 = cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    if ((x1>0 and x2<0) or (x1<0 and x2>0)) and ((x3>0 and x4<0) or (x3<0 and x4>0)): return True
    return any(on_edge(p,u,v) for p,u,v in ((a,c,d),(b,c,d),(c,a,b),(d,a,b)))

def validate_polygon(vertices):
    if not isinstance(vertices, list) or not 3 <= len(vertices) <= 100:
        raise HTTPException(400, 'Zones require 3 to 100 vertices')
    vertices = [point(v) for v in vertices]
    if len({(p['latitude'],p['longitude']) for p in vertices}) != len(vertices):
        raise HTTPException(400, 'Zone vertices must be unique; do not repeat the first point')
    if max(p['longitude'] for p in vertices)-min(p['longitude'] for p in vertices) >= 180:
        raise HTTPException(400, 'Split zones at the international date line')
    area = abs(sum(a['longitude']*b['latitude']-b['longitude']*a['latitude'] for a,b in zip(vertices,vertices[1:]+vertices[:1])))
    if area <= 1e-10: raise HTTPException(400, 'Zone area must be nonzero')
    n=len(vertices)
    for i,b in enumerate(vertices):
        a,c=vertices[i-1],vertices[(i+1)%n]
        if abs(cross(a,b,c))<=1e-10 and (a['latitude']-b['latitude'])*(c['latitude']-b['latitude'])+(a['longitude']-b['longitude'])*(c['longitude']-b['longitude'])>0:
            raise HTTPException(400,'Adjacent zone edges cannot overlap')
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1): continue
            if intersects(vertices[i],vertices[(i+1)%n],vertices[j],vertices[(j+1)%n]):
                raise HTTPException(400, 'Zone edges cannot intersect')
    return vertices

def contains(vertices, p):
    inside=False
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        if on_edge(p,a,b): return True
        if (a['latitude']>p['latitude']) != (b['latitude']>p['latitude']):
            x=a['longitude']+(p['latitude']-a['latitude'])*(b['longitude']-a['longitude'])/(b['latitude']-a['latitude'])
            if p['longitude'] < x: inside=not inside
    return inside

def validate(payload):
    if not isinstance(payload,dict) or set(payload) != {'enabled','mode','unit','radius','zones'}:
        raise HTTPException(400, 'Supply enabled, mode, unit, radius and zones')
    if type(payload['enabled']) is not bool or payload['mode'] not in ('radius','zones') or payload['unit'] not in ('mi','km'):
        raise HTTPException(400, 'Invalid coverage mode, distance unit or enabled flag')
    radius=payload['radius']
    if type(radius) not in (int,float) or not math.isfinite(radius) or not 0.1 <= radius*(1.609344 if payload['unit']=='mi' else 1) <= 500:
        raise HTTPException(400, 'Radius must be between 0.1 and 500 kilometres')
    if not isinstance(payload['zones'],list) or len(payload['zones'])>20 or (payload['mode']=='zones' and not payload['zones']):
        raise HTTPException(400, 'Zone mode requires 1 to 20 zones')
    zones=[]; ids=set()
    for zone in payload['zones']:
        if not isinstance(zone,dict) or set(zone) != {'id','name','pickup','delivery','active','vertices'}: raise HTTPException(400, 'Invalid zone fields')
        if not isinstance(zone['id'],str) or not 1<=len(zone['id'])<=100 or zone['id'] in ids: raise HTTPException(400, 'Zone IDs must be unique')
        if not isinstance(zone['name'],str) or not zone['name'].strip() or len(zone['name'])>120: raise HTTPException(400, 'Zone name is required')
        if any(type(zone[k]) is not bool for k in ('pickup','delivery','active')): raise HTTPException(400, 'Zone flags must be booleans')
        ids.add(zone['id']);zones.append({**zone,'name':zone['name'].strip(),'vertices':validate_polygon(zone['vertices'])})
    return {**payload,'radius':float(radius),'zones':zones}

def install(conn):
    pins_version='service-area-map-subscription-pins-v1'
    if not conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s',(pins_version,)).fetchone():
        conn.execute('ALTER TABLE customer_subscriptions ADD COLUMN service_latitude DOUBLE PRECISION, ADD COLUMN service_longitude DOUBLE PRECISION')
        conn.execute('INSERT INTO fabclean_schema_migrations(version) VALUES (%s)',(pins_version,))
    if conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s',(VERSION,)).fetchone(): return
    conn.execute('''CREATE TABLE store_delivery_coverage (
        business_id TEXT NOT NULL, location_id TEXT NOT NULL, payload JSONB NOT NULL, revision INTEGER NOT NULL,
        PRIMARY KEY(business_id,location_id), FOREIGN KEY(location_id,business_id) REFERENCES stores(id,brand_id))''')
    conn.execute('ALTER TABLE store_delivery_coverage ENABLE ROW LEVEL SECURITY')
    conn.execute('ALTER TABLE store_delivery_coverage FORCE ROW LEVEL SECURITY')
    predicate="current_setting('app.maintenance',true)='on' OR (business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),''))"
    conn.execute(f'CREATE POLICY coverage_scope ON store_delivery_coverage USING ({predicate}) WITH CHECK ({predicate})')
    conn.execute('INSERT INTO fabclean_schema_migrations(version) VALUES (%s)',(VERSION,))

def load(s):
    if not s.DATABASE_URL: row=memory.get('policy')
    else:
        with s.db() as conn: row=conn.execute('SELECT payload,revision FROM store_delivery_coverage').fetchone()
    return deepcopy(dict(row)) if row else {'payload':None,'revision':0}

def location(s):
    brand,store=current_scope.get() or ('fabclean','main')
    if not s.DATABASE_URL: return {'id':store,'name':'Selected store','latitude':None,'longitude':None}
    with s.db() as conn: row=conn.execute('SELECT id,name,latitude,longitude FROM stores WHERE id=%s AND brand_id=%s',(store,brand)).fetchone()
    if not row: raise HTTPException(404,'Selected service store not found')
    return dict(row)

def origin(loc):
    try: return point({k:float(loc[k]) if loc[k] is not None else None for k in ('latitude','longitude')})
    except (HTTPException,TypeError,ValueError): raise HTTPException(409,'Save valid store coordinates in Brand & Stores before enabling coverage')

def evaluate(document, loc, target, fulfillment, capabilities):
    if fulfillment not in ('pickup_only','delivery_only','pickup_and_delivery'):
        raise HTTPException(400,'Select pickup, delivery or both for an address check')
    policy=document['payload']; needs_pickup=fulfillment in ('pickup_only','pickup_and_delivery');needs_delivery=fulfillment in ('delivery_only','pickup_and_delivery')
    base={'policy_revision':document['revision'],'store_id':loc['id'],'fulfillment_type':fulfillment,'selected_point':target}
    if not policy or not policy['enabled']: return {**base,'eligible':None,'state':'not_enforced','reason':'Coverage is not enabled for this store; the legacy scheduling workflow remains available','matched_zones':[]}
    center=origin(loc);distance=distance_km(center,target);unit=policy['unit'];zone_matches=[]
    if policy['mode']=='radius':
        within=distance <= policy['radius']*(1.609344 if unit=='mi' else 1)+1e-9
        pickup=delivery=within
    else:
        zone_matches=[{'id':z['id'],'name':z['name'],'pickup':z['pickup'],'delivery':z['delivery']} for z in policy['zones'] if z['active'] and contains(z['vertices'],target)]
        pickup=any(z['pickup'] for z in zone_matches);delivery=any(z['delivery'] for z in zone_matches)
    eligible=(not needs_pickup or pickup and capabilities['pickup']) and (not needs_delivery or delivery and capabilities['delivery'])
    enabled=(not needs_pickup or capabilities['pickup']) and (not needs_delivery or capabilities['delivery'])
    reason='Address pin is inside the selected store coverage' if eligible else 'Pickup/delivery is disabled for this store' if not enabled else 'Address pin is outside the requested pickup/delivery coverage'
    return {**base,'eligible':bool(eligible),'state':'inside' if eligible else 'outside','reason':reason,'mode':policy['mode'],'distance':round(distance/(1.609344 if unit=='mi' else 1),3),'unit':unit,'store_point':center,'matched_zones':zone_matches,'policy':deepcopy(policy)}

def check(s, payload):
    if not isinstance(payload,dict) or set(payload)-{'latitude','longitude','address','fulfillment_type'}: raise HTTPException(400,'Coverage location and store are resolved by the server')
    target=point({k:payload.get(k) for k in ('latitude','longitude')})
    address=payload.get('address','')
    if not isinstance(address,str) or not address.strip() or len(address)>1000: raise HTTPException(400,'Enter the service address and confirm its map pin')
    result=evaluate(load(s),location(s),target,payload.get('fulfillment_type'),{'pickup':s.capability_enabled('pickup_enabled',False),'delivery':s.capability_enabled('delivery_enabled',False)})
    return {**result,'address':address.strip(),'coordinate_source':'staff_confirmed_pin','checked_at':datetime.now(timezone.utc).isoformat()}

def validate_order(s, order):
    if order.get('fulfillment_type','walk_in')=='walk_in': return None
    policy=load(s)
    if not policy['payload'] or not policy['payload']['enabled']: return None
    result=check(s,{'latitude':order.get('service_latitude'),'longitude':order.get('service_longitude'),'address':order.get('service_address'),'fulfillment_type':order.get('fulfillment_type')})
    if result['eligible'] is not True: raise HTTPException(409,result['reason'])
    return result

def subscription_pin(payload):
    lat,lon=payload.get('service_latitude'),payload.get('service_longitude')
    if (lat is None)!=(lon is None):raise HTTPException(400,'Supply both subscription coordinates or leave both blank')
    if lat is not None:point({'latitude':lat,'longitude':lon})

def register(app,s):
    @app.get('/api/coverage')
    def get(x_session_token:str|None=Header(default=None)):
        s.require_permission('orders',x_session_token)
        return {**load(s),'location':location(s),'pickup_enabled':s.capability_enabled('pickup_enabled',False),'delivery_enabled':s.capability_enabled('delivery_enabled',False)}

    @app.put('/api/coverage')
    def put(payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_permission('admin',x_session_token)
        if set(payload)!={'revision','payload'} or type(payload['revision']) is not int: raise HTTPException(400,'Supply coverage policy and revision')
        document=validate(payload['payload']);scope=s.operational_scope(actor)
        def save(conn=None):
            before=load(s)
            if payload['revision']!=before['revision']:raise HTTPException(409,'Coverage changed; refresh before saving')
            if document['enabled']:origin(location(s))
            row={'payload':document,'revision':before['revision']+1}
            if conn is None:memory['policy']=row
            else:
                conn.execute('INSERT INTO store_delivery_coverage(business_id,location_id,payload,revision) VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT(business_id,location_id) DO UPDATE SET payload=EXCLUDED.payload,revision=EXCLUDED.revision',(*scope,json.dumps(document),row['revision']))
                s.platform_audit_write(conn,actor,'delivery_coverage_updated',scope[0],{'store_id':scope[1],'revision':row['revision'],'enabled':document['enabled'],'mode':document['mode']})
            return {**row,'location':location(s)}
        if not s.DATABASE_URL:
            with lock:return save()
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,scope[0]);marker=s.transaction_connection.set(conn)
            try:return save(conn)
            finally:s.transaction_connection.reset(marker)

    @app.post('/api/coverage/check')
    def check_address(payload:dict,x_session_token:str|None=Header(default=None)):
        s.require_permission('orders',x_session_token);return check(s,payload)
