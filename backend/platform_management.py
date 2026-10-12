"""Global platform control state; never broadens operational tenant RLS."""
import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import Header, HTTPException, Request

VERSION = 'platform-onboarding-v1'
FEATURES = ('offers','rewards','referrals','subscriptions','pickup','delivery','handoffs','ai','reports')
CAPABILITY_FEATURE = {key+'_enabled':key for key in FEATURES}
CAPABILITY_FEATURE['ai_assistance_enabled']='ai'
LIMITS=('stores','staff')
ALL_FEATURES={key:True for key in FEATURES}
DEFAULT_PLANS=(
    ('legacy','Existing brands',ALL_FEATURES,{'stores':None,'staff':None}),
    ('starter','Starter',{key:key=='reports' for key in FEATURES},{'stores':1,'staff':5}),
    ('growth','Growth',{key:key!='ai' for key in FEATURES},{'stores':10,'staff':100}),
    ('enterprise','Enterprise',ALL_FEATURES,{'stores':None,'staff':None}),
)


def install_platform(conn):
    if conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s',(VERSION,)).fetchone():return
    conn.execute('''CREATE TABLE platform_plans (
        code TEXT PRIMARY KEY, name TEXT NOT NULL, features JSONB NOT NULL, limits JSONB NOT NULL,
        active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    for code,name,features,limits in DEFAULT_PLANS:
        conn.execute('INSERT INTO platform_plans(code,name,features,limits) VALUES (%s,%s,%s::jsonb,%s::jsonb)',(code,name,json.dumps(features),json.dumps(limits)))
    conn.execute("ALTER TABLE brands ADD COLUMN plan_code TEXT NOT NULL DEFAULT 'legacy'")
    conn.execute("ALTER TABLE brands ADD COLUMN entitlement_overrides JSONB NOT NULL DEFAULT '{}'::jsonb")
    conn.execute("ALTER TABLE brands ADD CONSTRAINT brand_platform_plan FOREIGN KEY(plan_code) REFERENCES platform_plans(code) NOT VALID")
    conn.execute("ALTER TABLE brands ADD CONSTRAINT brand_lifecycle_status CHECK(status IN ('active','suspended')) NOT VALID")
    conn.execute('''CREATE TABLE owner_invitations (
        id TEXT PRIMARY KEY, brand_id TEXT NOT NULL REFERENCES brands(id), store_id TEXT NOT NULL,
        email TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','revoked')),
        invited_by TEXT NOT NULL, accepted_by TEXT, expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), accepted_at TIMESTAMPTZ,
        FOREIGN KEY(store_id,brand_id) REFERENCES stores(id,brand_id))''')
    conn.execute("CREATE UNIQUE INDEX pending_owner_email ON owner_invitations(brand_id,email) WHERE status='pending'")
    conn.execute('CREATE INDEX owner_invitation_brand_created ON owner_invitations(brand_id,created_at DESC)')
    conn.execute('''CREATE OR REPLACE FUNCTION prevent_platform_audit_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Platform audit is append-only' USING ERRCODE='42501'; END; $$''')
    conn.execute('CREATE TRIGGER immutable_platform_audit BEFORE UPDATE OR DELETE ON platform_audit FOR EACH ROW EXECUTE FUNCTION prevent_platform_audit_rewrite()')
    conn.execute('INSERT INTO fabclean_schema_migrations(version) VALUES (%s)',(VERSION,))


def validate_features(value, partial=False):
    if not isinstance(value,dict) or set(value)-set(FEATURES) or any(type(v) is not bool for v in value.values()):
        raise HTTPException(400,'Feature values must be booleans using supported feature keys')
    return dict(value) if partial else {key:value.get(key,False) for key in FEATURES}


def validate_limits(value, partial=False):
    if not isinstance(value,dict) or set(value)-set(LIMITS):raise HTTPException(400,'Unsupported plan limits')
    for v in value.values():
        if v is not None and (type(v) is not int or not 1<=v<=10000):raise HTTPException(400,'Limits must be 1–10000 or null for unlimited')
    return dict(value) if partial else {key:value.get(key) for key in LIMITS}


def validate_overrides(value):
    if not isinstance(value,dict) or set(value)-{'features','limits'}:raise HTTPException(400,'Unsupported entitlement overrides')
    return {'features':validate_features(value.get('features',{}),True),'limits':validate_limits(value.get('limits',{}),True)}


def entitlements(row):
    overrides=row.get('entitlement_overrides') or {}
    return {'plan_code':row['plan_code'],'features':{**row['features'],**overrides.get('features',{})},'limits':{**row['limits'],**overrides.get('limits',{})}}


def brand_policy(conn,brand_id):
    row=conn.execute('SELECT b.*,p.features,p.limits FROM brands b JOIN platform_plans p ON p.code=b.plan_code WHERE b.id=%s',(brand_id,)).fetchone()
    if not row:raise HTTPException(404,'Brand not found')
    return dict(row),entitlements(row)


def usage(conn,brand_id,exclude_user=None,exclude_email=None):
    stores=conn.execute('SELECT COUNT(*) AS n FROM stores WHERE brand_id=%s AND active=TRUE',(brand_id,)).fetchone()['n']
    staff=conn.execute('''SELECT COUNT(*) AS n FROM staff_users u WHERE active=TRUE AND (%s::text IS NULL OR u.id<>%s) AND
        (u.business_id=%s OR EXISTS(SELECT 1 FROM user_role_assignments a WHERE a.user_id=u.id AND a.brand_id=%s AND a.active=TRUE))''',(exclude_user,exclude_user,brand_id,brand_id)).fetchone()['n']
    pending=conn.execute('''SELECT COUNT(DISTINCT i.email) AS n FROM owner_invitations i WHERE i.brand_id=%s AND i.status='pending' AND i.expires_at>NOW()
        AND (%s::text IS NULL OR i.email<>%s) AND NOT EXISTS(SELECT 1 FROM staff_users u WHERE u.email=i.email AND u.active=TRUE
            AND (u.business_id=%s OR EXISTS(SELECT 1 FROM user_role_assignments a WHERE a.user_id=u.id AND a.brand_id=%s AND a.active=TRUE)))''',(brand_id,exclude_email,exclude_email,brand_id,brand_id)).fetchone()['n']
    return {'stores':stores,'staff':staff,'pending_owner_seats':pending}


def require_capacity(conn,brand_id,kind,exclude_user=None,exclude_email=None,increment=1):
    brand,policy=brand_policy(conn,brand_id)
    if brand['status']!='active':raise HTTPException(403,'Brand is suspended or unavailable')
    counts=usage(conn,brand_id,exclude_user,exclude_email)
    current=counts[kind]+(counts['pending_owner_seats'] if kind=='staff' else 0)
    maximum=policy['limits'][kind]
    if maximum is not None and current+increment>maximum:raise HTTPException(409,f"Brand's {kind} limit would be exceeded")


def validate_policy_change(conn,brand_id,policy):
    counts=usage(conn,brand_id)
    for kind in LIMITS:
        current=counts[kind]+(counts['pending_owner_seats'] if kind=='staff' else 0)
        if policy['limits'][kind] is not None and current>policy['limits'][kind]:raise HTTPException(409,f"{kind.title()} limit is below existing usage or reserved owner seats")
    if not policy['features']['handoffs']:
        if conn.execute('SELECT 1 FROM stores WHERE brand_id=%s AND open_handoff_count>0 LIMIT 1',(brand_id,)).fetchone():
            raise HTTPException(409,'Close all open handoffs before disabling handoffs')


def route_feature(path):
    if path.startswith('/api/offers'):return 'offers'
    if path.startswith('/api/referrals') or path.endswith('/referrals'):return 'referrals'
    if path.endswith('/rewards'):return 'rewards'
    if path.startswith('/api/subscriptions') or path.endswith('/subscriptions'):return 'subscriptions'
    if path.startswith(('/api/handoffs','/api/handoff-destinations')):return 'handoffs'
    if path.startswith('/api/ai/'):return 'ai'
    if path.startswith(('/api/reports','/api/financial/')):return 'reports'
    return None


def audit(conn,actor,action,brand_id=None,metadata=None):
    conn.execute('INSERT INTO platform_audit(id,actor_user_id,action,brand_id,metadata) VALUES (%s,%s,%s,%s,%s::jsonb)',(str(uuid.uuid4()),actor.get('id',''),action,brand_id,json.dumps(metadata or {})))


def valid_email(value):
    email=str(value or '').strip().lower()
    if len(email)>254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):raise HTTPException(400,'A valid owner email is required')
    return email


def public_invite(row):
    result={key:row.get(key) for key in ('id','brand_id','store_id','email','status','expires_at','created_at','accepted_at','accepted_by')}
    if result['status']=='pending' and row['expires_at']<=datetime.now(timezone.utc):result['status']='expired'
    return result


def create_invite(conn,s,actor,brand_id,email,store_id):
    email=valid_email(email)
    brand,_=brand_policy(conn,brand_id)
    if brand['status']!='active':raise HTTPException(403,'Activate the brand before inviting an owner')
    if not conn.execute('SELECT 1 FROM stores WHERE id=%s AND brand_id=%s AND active=TRUE',(store_id,brand_id)).fetchone():raise HTTPException(404,'Active initial store not found in this brand')
    existing=conn.execute('SELECT u.id FROM staff_users u JOIN user_role_assignments a ON a.user_id=u.id WHERE u.email=%s AND u.active=TRUE AND a.brand_id=%s AND a.role=\'brand_admin\' AND a.scope_type=\'brand\' AND a.store_id IS NULL AND a.active=TRUE',(email,brand_id)).fetchone()
    if existing:raise HTTPException(409,'This account is already an active brand owner')
    user=conn.execute('SELECT id,active FROM staff_users WHERE email=%s',(email,)).fetchone()
    if user and not user['active']: raise HTTPException(403,'Reactivate this account before inviting it as an owner')
    require_capacity(conn,brand_id,'staff',user['id'] if user else None,email)
    revoked=conn.execute("UPDATE owner_invitations SET status='revoked' WHERE brand_id=%s AND email=%s AND status='pending' RETURNING id",(brand_id,email)).fetchall()
    token=secrets.token_urlsafe(32);iid=str(uuid.uuid4())
    row=conn.execute("INSERT INTO owner_invitations(id,brand_id,store_id,email,token_hash,invited_by,expires_at) VALUES (%s,%s,%s,%s,%s,%s,NOW()+INTERVAL '48 hours') RETURNING *",(iid,brand_id,store_id,email,hashlib.sha256(token.encode()).hexdigest(),actor['id'])).fetchone()
    audit(conn,actor,'owner_invited',brand_id,{'invitation_id':iid,'replaced_ids':[x['id'] for x in revoked]})
    base=os.getenv('PUBLIC_WEB_URL','https://fabclean-saas-web.onrender.com').rstrip('/')
    parsed=urlparse(base)
    if parsed.scheme not in ('https','http') or not parsed.netloc or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.path or ((os.getenv('APP_ENV')=='production' or os.getenv('RENDER')=='true') and parsed.scheme!='https'):raise HTTPException(500,'Invitation web URL is not configured correctly')
    return {**public_invite(row),'token':token,'acceptance_url':base+'/accept-invite#token='+token}


def register_platform_routes(app,s):
    def database_required():
        if not s.DATABASE_URL:raise HTTPException(503,'Platform lifecycle and onboarding require PostgreSQL')

    @app.get('/api/platform/plans')
    def plans(x_session_token: str | None=Header(default=None)):
        s.require_super_admin(x_session_token);database_required()
        with s.db() as conn:rows=conn.execute('SELECT * FROM platform_plans ORDER BY code').fetchall()
        return {'plans':[dict(x) for x in rows],'feature_keys':list(FEATURES),'limit_keys':list(LIMITS)}

    def plan_values(payload,current=None):
        data={**(current or {}),**payload}
        code=str(data.get('code','')).strip().lower();name=str(data.get('name','')).strip()
        if not re.fullmatch('[a-z][a-z0-9-]{0,39}',code) or not name or len(name)>120:raise HTTPException(400,'Plan code and name are required')
        if 'active' in data and type(data['active']) is not bool:raise HTTPException(400,'Plan active must be boolean')
        return code,name,validate_features(data.get('features',{})),validate_limits(data.get('limits',{})),data.get('active',True)

    @app.post('/api/platform/plans')
    def create_plan(payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_super_admin(x_session_token);database_required()
        code,name,features,limits,active=plan_values(payload)
        with s.db() as conn,conn.transaction():
            row=conn.execute('INSERT INTO platform_plans(code,name,features,limits,active) VALUES (%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING *',(code,name,json.dumps(features),json.dumps(limits),active)).fetchone()
            audit(conn,actor,'plan_created',metadata={'plan_code':code,'features':features,'limits':limits})
        return dict(row)

    @app.put('/api/platform/plans/{code}')
    def update_plan(code:str,payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_super_admin(x_session_token);database_required()
        if code=='legacy':raise HTTPException(400,'The compatibility plan is read-only; assign an editable plan instead')
        if 'code' in payload and payload['code']!=code:raise HTTPException(400,'Plan codes are immutable')
        with s.db() as conn,conn.transaction():
            # Global catalogue lock plus ordered brand locks makes plan edits and assignments consistent.
            conn.execute('SELECT pg_advisory_xact_lock(471007)')
            current=conn.execute('SELECT * FROM platform_plans WHERE code=%s FOR UPDATE',(code,)).fetchone()
            if not current:raise HTTPException(404,'Plan not found')
            _,name,features,limits,active=plan_values(payload,current)
            brands=conn.execute('SELECT id,entitlement_overrides FROM brands WHERE plan_code=%s ORDER BY id',(code,)).fetchall()
            for brand in brands:
                s.lock_brand_operations(conn,brand['id'])
                validate_policy_change(conn,brand['id'],entitlements({**brand,'plan_code':code,'features':features,'limits':limits}))
            row=conn.execute('UPDATE platform_plans SET name=%s,features=%s::jsonb,limits=%s::jsonb,active=%s,updated_at=NOW() WHERE code=%s RETURNING *',(name,json.dumps(features),json.dumps(limits),active,code)).fetchone()
            audit(conn,actor,'plan_updated',metadata={'plan_code':code,'before':{'features':current['features'],'limits':current['limits']},'after':{'features':features,'limits':limits,'active':active}})
        return dict(row)

    @app.get('/api/platform/brands/{brand_id}')
    def detail(brand_id:str,x_session_token:str|None=Header(default=None)):
        s.require_super_admin(x_session_token);database_required()
        with s.db() as conn:
            brand,policy=brand_policy(conn,brand_id)
            stores=conn.execute('SELECT * FROM stores WHERE brand_id=%s ORDER BY name',(brand_id,)).fetchall()
            invites=conn.execute('SELECT * FROM owner_invitations WHERE brand_id=%s ORDER BY created_at DESC LIMIT 100',(brand_id,)).fetchall()
            counts=usage(conn,brand_id)
        return {'brand':brand,'entitlements':policy,'usage':counts,'stores':[dict(x) for x in stores],'invitations':[public_invite(x) for x in invites]}

    @app.post('/api/platform/brands/{brand_id}/owner-invitations')
    def invite(brand_id:str,payload:dict,x_session_token:str|None=Header(default=None)):
        actor=s.require_super_admin(x_session_token);database_required()
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,brand_id)
            return create_invite(conn,s,actor,brand_id,payload.get('email'),payload.get('store_id'))

    @app.post('/api/platform/owner-invitations/{invitation_id}/revoke')
    def revoke(invitation_id:str,x_session_token:str|None=Header(default=None)):
        actor=s.require_super_admin(x_session_token);database_required()
        with s.db() as conn,conn.transaction():
            existing=conn.execute('SELECT brand_id FROM owner_invitations WHERE id=%s',(invitation_id,)).fetchone()
            if not existing:raise HTTPException(404,'Invitation not found')
            s.lock_brand_operations(conn,existing['brand_id'])
            row=conn.execute("UPDATE owner_invitations SET status='revoked' WHERE id=%s AND status='pending' RETURNING *",(invitation_id,)).fetchone()
            if not row:raise HTTPException(409,'Invitation is already accepted or revoked')
            audit(conn,actor,'owner_invitation_revoked',row['brand_id'],{'invitation_id':invitation_id})
        return public_invite(row)

    def invitation_for_token(conn,token):
        if not isinstance(token,str) or not re.fullmatch('[A-Za-z0-9_-]{32,128}',token):raise HTTPException(404,'Invitation is invalid or unavailable')
        row=conn.execute('SELECT * FROM owner_invitations WHERE token_hash=%s',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row or row['status']!='pending' or row['expires_at']<=datetime.now(timezone.utc):raise HTTPException(410,'Invitation is expired, revoked or already accepted')
        return row

    def reserve_invitation(conn,token,request):
        if not isinstance(token,str) or len(token)>128:raise HTTPException(400,'Invalid invitation token')
        s.reserve_login(conn,s.rate_keys('owner-invite:'+token,s.get_request_ip(request)))

    @app.post('/api/auth/owner-invitations/preview')
    def preview(payload:dict,request:Request):
        database_required()
        with s.db() as conn:
            reserve_invitation(conn,payload.get('token'),request)
            row=invitation_for_token(conn,payload.get('token'))
            brand,_=brand_policy(conn,row['brand_id'])
            if brand['status']!='active':raise HTTPException(403,'Brand is suspended or unavailable')
            store=conn.execute('SELECT name FROM stores WHERE id=%s AND active=TRUE',(row['store_id'],)).fetchone()
            if not store:raise HTTPException(403,'Invited store is unavailable')
            existing=conn.execute('SELECT 1 FROM staff_users WHERE email=%s',(row['email'],)).fetchone()
        return {'brand_name':brand['name'],'store_name':store['name'],'email':row['email'],'existing_account':bool(existing),'expires_at':row['expires_at']}

    @app.post('/api/auth/owner-invitations/accept')
    def accept(payload:dict,request:Request,x_session_token:str|None=Header(default=None)):
        database_required();token=payload.get('token');name=str(payload.get('name','')).strip();password=str(payload.get('password',''))
        if len(password)>1024 or len(name)>160:raise HTTPException(400,'Invalid name or password length')
        identity=s.get_current_staff(x_session_token) if x_session_token else None
        with s.db() as conn:
            reserve_invitation(conn,token,request)
            invitation=invitation_for_token(conn,token)
        with s.db() as conn,conn.transaction():
            s.lock_brand_operations(conn,invitation['brand_id'])
            invitation=invitation_for_token(conn,token)
            conn.execute('SELECT id FROM owner_invitations WHERE id=%s FOR UPDATE',(invitation['id'],))
            brand,_=brand_policy(conn,invitation['brand_id'])
            if brand['status']!='active':raise HTTPException(403,'Brand is suspended or unavailable')
            if not conn.execute('SELECT 1 FROM stores WHERE id=%s AND brand_id=%s AND active=TRUE',(invitation['store_id'],invitation['brand_id'])).fetchone():raise HTTPException(403,'Invited store is unavailable')
            # Email lock also serializes invitations for one identity across brands.
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,471008))',(invitation['email'],))
            user=conn.execute('SELECT * FROM staff_users WHERE email=%s FOR UPDATE',(invitation['email'],)).fetchone()
            if user:
                if not user['active']:raise HTTPException(403,'Account is inactive; contact the administrator')
                valid_session = bool(identity and identity['id']==user['id'] and conn.execute('SELECT 1 FROM staff_sessions WHERE token=%s AND staff_id=%s AND expires_at>NOW()', (x_session_token,user['id'])).fetchone())
                if not valid_session and not (password and user.get('password_hash') and s.verify_password(password,user.get('password_salt'),user['password_hash'])):
                    raise HTTPException(401,'Sign in as the invited account or provide its current password')
                uid=user['id']
                require_capacity(conn,invitation['brand_id'],'staff',uid,invitation['email'])
            else:
                if not name or len(password)<8:raise HTTPException(400,'Name and a password of 8–1024 characters are required')
                require_capacity(conn,invitation['brand_id'],'staff',exclude_email=invitation['email'])
                uid=str(uuid.uuid4());salt=secrets.token_hex(16)
                user=conn.execute("INSERT INTO staff_users(id,name,email,role,business_id,location_id,password_salt,password_hash) VALUES (%s,%s,%s,'owner',%s,%s,%s,%s) RETURNING *",(uid,name,invitation['email'],invitation['brand_id'],invitation['store_id'],salt,s.hash_password(password,salt))).fetchone()
            role=conn.execute("SELECT id FROM user_role_assignments WHERE user_id=%s AND brand_id=%s AND role='brand_admin' AND scope_type='brand' AND store_id IS NULL",(uid,invitation['brand_id'])).fetchone()
            if role:conn.execute('UPDATE user_role_assignments SET active=TRUE WHERE id=%s',(role['id'],))
            else:conn.execute("INSERT INTO user_role_assignments(id,user_id,role,scope_type,brand_id) VALUES (%s,%s,'brand_admin','brand',%s)",(str(uuid.uuid4()),uid,invitation['brand_id']))
            conn.execute("UPDATE owner_invitations SET status='accepted',accepted_by=%s,accepted_at=NOW() WHERE id=%s",(uid,invitation['id']))
            audit(conn,{'id':uid},'owner_invitation_accepted',invitation['brand_id'],{'invitation_id':invitation['id']})
        return {'accepted':True,'staff_id':uid,'store_id':invitation['store_id'],'brand_id':invitation['brand_id'],'email':invitation['email'],'message':'Owner invitation accepted. Sign in to continue.'}

    @app.get('/api/platform/audit')
    def audit_history(brand_id:str|None=None,limit:int=100,x_session_token:str|None=Header(default=None)):
        s.require_super_admin(x_session_token);database_required()
        with s.db() as conn:rows=conn.execute('SELECT * FROM platform_audit WHERE (%s::text IS NULL OR brand_id=%s) ORDER BY created_at DESC,id DESC LIMIT %s',(brand_id,brand_id,max(1,min(limit,500)))).fetchall()
        return {'events':[dict(x) for x in rows]}

    @app.get('/api/platform/health')
    def health(x_session_token:str|None=Header(default=None)):
        s.require_super_admin(x_session_token);database_required()
        with s.db() as conn:
            brand_counts=conn.execute('SELECT status,COUNT(*) AS count FROM brands GROUP BY status').fetchall()
            stores=conn.execute('SELECT COUNT(*) AS n FROM stores WHERE active=TRUE').fetchone()['n']
            pending=conn.execute("SELECT COUNT(*) AS n FROM owner_invitations WHERE status='pending' AND expires_at>NOW()").fetchone()['n']
            migration=conn.execute('SELECT 1 FROM fabclean_schema_migrations WHERE version=%s',(VERSION,)).fetchone()
        return {'status':'ok','database':'postgres','schema_ready':bool(migration),'brand_counts':{r['status']:r['count'] for r in brand_counts},'active_stores':stores,'pending_owner_invitations':pending}


def login_scope(conn,s,staff):
    staff['assignments']=[dict(x) for x in conn.execute('SELECT * FROM user_role_assignments WHERE user_id=%s AND active=TRUE',(staff['id'],)).fetchall()]
    staff['assignments_loaded']=True
    if s.has_role(staff,'super_admin'):return staff['business_id'],staff['location_id']
    brands=s.accessible_brand_ids(staff) or set()
    active=conn.execute("SELECT id FROM brands WHERE id=ANY(%s) AND status='active' ORDER BY name,id",(list(brands),)).fetchall() if brands else []
    if not active:raise HTTPException(403,'No active brand is available for this account')
    brand=staff['business_id'] if any(x['id']==staff['business_id'] for x in active) else active[0]['id']
    allowed=s.accessible_store_ids(staff,brand)
    stores=conn.execute('SELECT id FROM stores WHERE brand_id=%s AND active=TRUE ORDER BY name,id',(brand,)).fetchall()
    stores=[x for x in stores if allowed is None or x['id'] in allowed]
    store=staff['location_id'] if any(x['id']==staff['location_id'] for x in stores) else stores[0]['id'] if stores else None
    return brand,store
