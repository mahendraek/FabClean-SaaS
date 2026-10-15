"""Explicit, idempotent CleanandDry demo records; never automatic startup seeds."""
import uuid
from fastapi import Header,HTTPException
from models import CustomerCreate,Service
from tenant_scope import current_scope

def register(app,s):
    @app.post('/api/admin/cleananddry-samples')
    @s.store_creation_transaction
    def seed(x_session_token:str|None=Header(default=None)):
        actor=s.require_permission('admin',x_session_token);brand,store=s.operational_scope(actor)
        if not s.DATABASE_URL:raise HTTPException(503,'Sample seeding requires PostgreSQL and the actual selected store')
        with s.db() as conn:
            loc=conn.execute('SELECT s.name,s.city,b.name AS brand_name FROM stores s JOIN brands b ON b.id=s.brand_id WHERE s.id=%s AND s.brand_id=%s',(store,brand)).fetchone()
        normalize=lambda value:''.join(c for c in str(value).casefold() if c.isalnum())
        if not loc or normalize(loc['city'])!='schaumburg' or not any('cleananddry' in normalize(loc[k]) for k in ('name','brand_name')):raise HTTPException(409,'Select the CleanandDry store in Schaumburg before adding its samples')
        customer=s.find_customer_by_phone('+12025550123',brand,store)
        if not customer:customer=s.create_customer_record(CustomerCreate(name='TEST — CleanandDry Customer',phone='+12025550123',email='cleananddry-test@example.invalid',notes='Explicit test customer; do not send real notifications',business_id=brand,location_id=store))
        created=[]
        with s.db() as conn:
            conn.execute("INSERT INTO service_categories(id,name,active,sort_order) VALUES ('cleananddry-samples','TEST services',TRUE,999) ON CONFLICT DO NOTHING")
            for key,name,price in [('sample-wash-fold','TEST — Wash & Fold',2.50),('sample-shirt','TEST — Shirt Cleaning',4.50),('sample-dry-clean','TEST — Dry Cleaning',12.00)]:
                row=conn.execute('SELECT id FROM services WHERE id=%s',(key,)).fetchone()
                if row:continue
                item=Service(id=key,name=name,category='TEST services',pricing_type='per_item',base_price=price,business_id=brand,location_id=store,description='Demo service; review pricing before real use')
                conn.execute('INSERT INTO services(id,payload,active) VALUES (%s,%s::jsonb,TRUE)',(key,item.model_dump_json()));created.append(key)
            s.platform_audit_write(conn,actor,'cleananddry_samples_created',brand,{'store_id':store,'created_services':created})
        return {'customer':customer,'created_services':created,'message':'CleanandDry test records are available. No tax rates were guessed; review each service taxability.'}
