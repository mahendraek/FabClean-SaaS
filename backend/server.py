import base64
import json
import os
import uuid
import hashlib
import secrets
import time
import httpx
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from twilio.rest import Client as TwilioClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from models import Service, Order, OrderCreate, Customer, CustomerCreate
from seed import SERVICES

app = FastAPI(title="FabClean API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna").strip()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "").strip()
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "").strip()
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "FabClean").strip()

memory_services = {item["id"]: Service(**item) for item in SERVICES}
memory_orders = {}
memory_customers = {}
memory_payments = []
memory_garments = {}
memory_settings = {
    "business_name": "FabClean Demo Laundry",
    "pickup_enabled": False,
    "delivery_enabled": False,
    "rewards_enabled": True,
    "offers_enabled": True,
    "referrals_enabled": True,
    "subscriptions_enabled": True,
    "ai_assistance_enabled": True,
    "barcode_mode": "both",
    "currency": "USD",
    "service_coverage_mode": "radius",
    "service_radius_miles": 10,
    "pickup_delivery_slot_minutes": 180,
}

@contextmanager
def db():
    if not DATABASE_URL:
        yield None
        return
    conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    if not DATABASE_URL:
        return
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id TEXT PRIMARY KEY,
                payload JSONB NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                payload JSONB NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_categories (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL DEFAULT 'fabclean',
                location_id TEXT NOT NULL DEFAULT 'main',
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                reward_points INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers (phone)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers (LOWER(name))")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS brands (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                legal_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                primary_email TEXT NOT NULL DEFAULT '',
                primary_phone TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT 'US',
                timezone TEXT NOT NULL DEFAULT 'America/Chicago',
                currency TEXT NOT NULL DEFAULT 'USD',
                logo_url TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_brands_status_name ON brands (status, name)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id TEXT PRIMARY KEY,
                brand_id TEXT NOT NULL REFERENCES brands(id),
                store_code TEXT NOT NULL,
                name TEXT NOT NULL,
                parent_store_id TEXT REFERENCES stores(id),
                store_type TEXT NOT NULL DEFAULT 'regular',
                address_line1 TEXT NOT NULL DEFAULT '',
                address_line2 TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL DEFAULT '',
                postal_code TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT 'US',
                latitude NUMERIC,
                longitude NUMERIC,
                timezone TEXT NOT NULL DEFAULT 'America/Chicago',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(brand_id, store_code)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stores_brand_active ON stores (brand_id, active, name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stores_parent ON stores (parent_store_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_role_assignments (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                brand_id TEXT REFERENCES brands(id),
                store_id TEXT REFERENCES stores(id),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, role, scope_type, brand_id, store_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON user_role_assignments (user_id, active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_brand ON user_role_assignments (brand_id, active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_store ON user_role_assignments (store_id, active)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_audit (
                id TEXT PRIMARY KEY,
                actor_user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                brand_id TEXT,
                store_id TEXT,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON platform_audit (created_at DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                business_id TEXT NOT NULL DEFAULT 'fabclean',
                location_id TEXT NOT NULL DEFAULT 'main',
                password_salt TEXT,
                password_hash TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS password_salt TEXT")
        conn.execute("ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS password_hash TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_sessions (
                token TEXT PRIMARY KEY,
                staff_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '12 hours'
            )
        """)
        conn.execute("ALTER TABLE staff_sessions ADD COLUMN IF NOT EXISTS active_brand_id TEXT")
        conn.execute("ALTER TABLE staff_sessions ADD COLUMN IF NOT EXISTS active_store_id TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_audit (
                id TEXT PRIMARY KEY,
                staff_id TEXT NOT NULL,
                staff_name TEXT NOT NULL,
                staff_email TEXT NOT NULL,
                staff_role TEXT NOT NULL,
                ip_address TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT '',
                timezone TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                login_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_audit_login_at ON login_audit (login_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_audit_staff ON login_audit (staff_id, login_at DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                order_number TEXT UNIQUE NOT NULL,
                barcode_value TEXT UNIQUE NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id TEXT PRIMARY KEY,
                receipt_number TEXT UNIQUE NOT NULL,
                order_id TEXT NOT NULL,
                customer_id TEXT,
                transaction_type TEXT NOT NULL DEFAULT 'payment',
                payment_method TEXT NOT NULL DEFAULT 'cash',
                amount NUMERIC NOT NULL,
                reference_number TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                staff_id TEXT,
                staff_name TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payment_transactions (order_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_customer ON payment_transactions (customer_id, created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_events (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                from_value TEXT,
                to_value TEXT,
                notes TEXT NOT NULL DEFAULT '',
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_events_order_id ON order_events (order_id, created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_item_inspections (
                order_id TEXT NOT NULL,
                item_barcode TEXT NOT NULL,
                tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                condition_notes TEXT NOT NULL DEFAULT '',
                condition_status TEXT NOT NULL DEFAULT 'not_inspected',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (order_id, item_barcode)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_garments (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                garment_code TEXT UNIQUE NOT NULL,
                garment_index INTEGER NOT NULL,
                service_line_index INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                service_line_barcode TEXT NOT NULL DEFAULT '',
                last_stage TEXT NOT NULL DEFAULT 'tagged',
                assembled BOOLEAN NOT NULL DEFAULT FALSE,
                tag_print_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_garments_order ON order_garments (order_id, garment_index)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_garments_code ON order_garments (garment_code)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_photos (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                item_barcode TEXT,
                phase TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                data BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_photos_order_id ON order_photos (order_id, created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT UNIQUE,
                discount_type TEXT NOT NULL,
                discount_value NUMERIC NOT NULL DEFAULT 0,
                min_order NUMERIC NOT NULL DEFAULT 0,
                first_order_only BOOLEAN NOT NULL DEFAULT FALSE,
                auto_apply BOOLEAN NOT NULL DEFAULT FALSE,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                starts_at TIMESTAMPTZ,
                ends_at TIMESTAMPTZ,
                usage_limit INTEGER,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reward_transactions (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                order_id TEXT,
                transaction_type TEXT NOT NULL,
                points INTEGER NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id TEXT PRIMARY KEY,
                referrer_customer_id TEXT NOT NULL,
                referral_code TEXT UNIQUE NOT NULL,
                referred_customer_id TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                reward_points INTEGER NOT NULL DEFAULT 0,
                qualifying_order_id TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                qualified_at TIMESTAMPTZ
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reward_customer ON reward_transactions (customer_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_code ON referrals (referral_code)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_areas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                postal_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                delivery_fee NUMERIC NOT NULL DEFAULT 0,
                minimum_order NUMERIC NOT NULL DEFAULT 0,
                free_delivery_threshold NUMERIC NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_slots (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                day_of_week INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 10,
                pickup_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                delivery_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                active BOOLEAN NOT NULL DEFAULT TRUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_blackouts (
                id TEXT PRIMARY KEY,
                blackout_date DATE NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                pickup_blocked BOOLEAN NOT NULL DEFAULT TRUE,
                delivery_blocked BOOLEAN NOT NULL DEFAULT TRUE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                frequency TEXT NOT NULL,
                discount_percent NUMERIC NOT NULL DEFAULT 0,
                minimum_order NUMERIC NOT NULL DEFAULT 0,
                eligible_service_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recurring_order_runs (
                id TEXT PRIMARY KEY,
                subscription_id TEXT NOT NULL,
                pickup_date DATE NOT NULL,
                order_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(subscription_id, pickup_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_notifications (
                id TEXT PRIMARY KEY,
                customer_id TEXT,
                order_id TEXT,
                subscription_id TEXT,
                notification_type TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'manual',
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'prepared',
                staff_id TEXT,
                staff_name TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("ALTER TABLE customer_notifications ADD COLUMN IF NOT EXISTS provider_message_id TEXT")
        conn.execute("ALTER TABLE customer_notifications ADD COLUMN IF NOT EXISTS error_message TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE customer_notifications ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_notifications_customer ON customer_notifications (customer_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_notifications_order ON customer_notifications (order_id, created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_assistance_log (
                id TEXT PRIMARY KEY,
                staff_id TEXT,
                assistance_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                accepted BOOLEAN NOT NULL DEFAULT FALSE,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_subscriptions (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                plan_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                start_date DATE NOT NULL,
                next_pickup_date DATE,
                service_area_id TEXT,
                scheduled_slot_id TEXT,
                service_address TEXT NOT NULL DEFAULT '',
                service_postal_code TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute(
            "INSERT INTO app_settings (id, payload) VALUES ('business', %s::jsonb) ON CONFLICT (id) DO NOTHING",
            (json.dumps(memory_settings),),
        )
        default_brand_id="fabclean"
        default_store_id="main"
        conn.execute(
            "INSERT INTO brands (id,name,slug,legal_name,status,country,timezone,currency) VALUES (%s,'FabClean','fabclean','FabClean','active','US','America/Chicago','USD') ON CONFLICT (id) DO NOTHING",
            (default_brand_id,),
        )
        conn.execute(
            "INSERT INTO stores (id,brand_id,store_code,name,store_type,country,timezone,active) VALUES (%s,%s,'MAIN','Main Store','regular','US','America/Chicago',TRUE) ON CONFLICT (id) DO NOTHING",
            (default_store_id,default_brand_id),
        )
        conn.execute("UPDATE staff_users SET business_id=%s WHERE business_id='demo'",(default_brand_id,))
        conn.execute("UPDATE staff_users SET location_id=%s WHERE location_id='main'",(default_store_id,))
        conn.execute("UPDATE customers SET business_id=%s WHERE business_id='demo'",(default_brand_id,))
        conn.execute("UPDATE customers SET location_id=%s WHERE location_id='main'",(default_store_id,))
        existing_services_for_tenant=conn.execute("SELECT id,payload FROM services").fetchall()
        for service_row in existing_services_for_tenant:
            service_payload=dict(service_row["payload"])
            if service_payload.get("business_id","demo")=="demo":
                service_payload["business_id"]=default_brand_id
                conn.execute("UPDATE services SET payload=%s::jsonb WHERE id=%s",(json.dumps(service_payload),service_row["id"]))
        existing_orders_for_tenant=conn.execute("SELECT id,payload FROM orders").fetchall()
        for order_row in existing_orders_for_tenant:
            order_payload=dict(order_row["payload"])
            changed=False
            if order_payload.get("business_id","demo")=="demo":
                order_payload["business_id"]=default_brand_id; changed=True
            if order_payload.get("location_id","main")=="main":
                order_payload["location_id"]=default_store_id; changed=True
            customer_payload=dict(order_payload.get("customer") or {})
            if customer_payload and customer_payload.get("business_id","demo")=="demo":
                customer_payload["business_id"]=default_brand_id; customer_payload["location_id"]=default_store_id; order_payload["customer"]=customer_payload; changed=True
            if changed:
                conn.execute("UPDATE orders SET payload=%s::jsonb WHERE id=%s",(json.dumps(order_payload),order_row["id"]))
        existing_staff=conn.execute("SELECT id,role,business_id,location_id FROM staff_users").fetchall()
        for staff_row in existing_staff:
            role_map={"owner":"brand_admin","manager":"store_manager","counter":"counter","processing":"processing","driver":"driver"}
            scoped_role=role_map.get(staff_row["role"],staff_row["role"])
            scope_type="brand" if scoped_role=="brand_admin" else "store"
            brand_id=staff_row.get("business_id") or default_brand_id
            store_id=None if scope_type=="brand" else (staff_row.get("location_id") or default_store_id)
            assignment_id=f"legacy-{staff_row['id']}-{scoped_role}-{scope_type}"
            conn.execute(
                "INSERT INTO user_role_assignments (id,user_id,role,scope_type,brand_id,store_id,active) VALUES (%s,%s,%s,%s,%s,%s,TRUE) ON CONFLICT DO NOTHING",
                (assignment_id,staff_row["id"],scoped_role,scope_type,brand_id,store_id),
            )
        first_owner=conn.execute("SELECT id FROM staff_users WHERE role='owner' ORDER BY created_at LIMIT 1").fetchone()
        if first_owner:
            conn.execute(
                "INSERT INTO user_role_assignments (id,user_id,role,scope_type,brand_id,store_id,active) VALUES (%s,%s,'super_admin','platform',NULL,NULL,TRUE) ON CONFLICT DO NOTHING",
                (f"platform-super-{first_owner['id']}",first_owner["id"]),
            )
        conn.execute("""
            UPDATE app_settings
            SET payload=jsonb_set(payload,'{pickup_delivery_slot_minutes}','180'::jsonb,TRUE)
            WHERE id='business' AND COALESCE(payload->>'pickup_delivery_slot_minutes','')='120'
        """)
        for item in SERVICES:
            conn.execute(
                "INSERT INTO services (id, payload, active) VALUES (%s, %s::jsonb, %s) ON CONFLICT (id) DO NOTHING",
                (item["id"], json.dumps(item), item.get("active", True)),
            )
        category_aliases={"Laundry":"Wash & Fold","Household":"Bedding"}
        legacy_services=conn.execute("SELECT id,payload FROM services").fetchall()
        for row in legacy_services:
            service_payload=dict(row["payload"])
            old_category=service_payload.get("category")
            canonical_category=category_aliases.get(old_category)
            if canonical_category:
                service_payload["category"]=canonical_category
                conn.execute("UPDATE services SET payload=%s::jsonb WHERE id=%s",(json.dumps(service_payload),row["id"]))
        for old_name,new_name in category_aliases.items():
            old_row=conn.execute("SELECT * FROM service_categories WHERE name=%s",(old_name,)).fetchone()
            new_row=conn.execute("SELECT * FROM service_categories WHERE name=%s",(new_name,)).fetchone()
            if old_row and new_row:
                conn.execute("DELETE FROM service_categories WHERE id=%s",(old_row["id"],))
            elif old_row:
                conn.execute("UPDATE service_categories SET name=%s WHERE id=%s",(new_name,old_row["id"]))
        existing_service_rows = conn.execute("SELECT payload FROM services").fetchall()
        existing_category_names = sorted({row["payload"].get("category", "Other") for row in existing_service_rows})
        for index, name in enumerate(existing_category_names, 1):
            category_id = name.lower().replace("&", "and").replace(" ", "-")
            conn.execute(
                "INSERT INTO service_categories (id, name, active, sort_order) VALUES (%s, %s, TRUE, %s) ON CONFLICT (name) DO NOTHING",
                (category_id, name, index),
            )
        default_slot_windows=[("08:00","11:00"),("11:00","14:00"),("14:00","17:00"),("17:00","20:00")]
        for day in range(7):
            for start_time,end_time in default_slot_windows:
                exists=conn.execute("SELECT 1 FROM delivery_slots WHERE day_of_week=%s AND start_time=%s AND end_time=%s LIMIT 1",(day,start_time,end_time)).fetchone()
                if exists:
                    continue
                slot_id=f"default-{day}-{start_time.replace(':','')}-{end_time.replace(':','')}"
                label=datetime.strptime(start_time,"%H:%M").strftime("%-I %p")+" - "+datetime.strptime(end_time,"%H:%M").strftime("%-I %p")
                conn.execute(
                    "INSERT INTO delivery_slots (id,name,day_of_week,start_time,end_time,capacity,pickup_enabled,delivery_enabled,active) VALUES (%s,%s,%s,%s,%s,%s,TRUE,TRUE,TRUE) ON CONFLICT (id) DO NOTHING",
                    (slot_id,label,day,start_time,end_time,10),
                )
        migration_settings=conn.execute("SELECT payload FROM app_settings WHERE id='business'").fetchone()
        migration_done=bool((migration_settings["payload"] if migration_settings else {}).get("_slot_duration_3h_migrated",False))
        if not migration_done:
            existing_slots=conn.execute("SELECT id,start_time,end_time FROM delivery_slots").fetchall()
            for slot in existing_slots:
                start_dt=datetime.strptime(slot["start_time"],"%H:%M")
                expected_end=(start_dt+timedelta(hours=3)).strftime("%H:%M")
                if slot["end_time"]!=expected_end:
                    conn.execute("UPDATE delivery_slots SET end_time=%s WHERE id=%s",(expected_end,slot["id"]))
            conn.execute("UPDATE app_settings SET payload=jsonb_set(payload,'{_slot_duration_3h_migrated}','true'::jsonb,TRUE) WHERE id='business'")

@app.on_event("startup")
def startup():
    init_db()

def get_settings_value():
    if not DATABASE_URL:
        return memory_settings
    with db() as conn:
        row = conn.execute("SELECT payload FROM app_settings WHERE id='business'").fetchone()
        return row["payload"] if row else memory_settings

def capability_enabled(key: str, default: bool = True):
    return bool(get_settings_value().get(key, default))

def require_capability(key: str, label: str):
    if not capability_enabled(key, True):
        raise HTTPException(403, f"{label} is disabled in Admin")

def get_service_values(include_inactive: bool = False):
    if not DATABASE_URL:
        values = [s.model_dump() for s in memory_services.values()]
        return values if include_inactive else [s for s in values if s.get("active", True)]
    with db() as conn:
        if include_inactive:
            rows = conn.execute("SELECT payload, active FROM services ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT payload, active FROM services WHERE active=TRUE ORDER BY id").fetchall()
        values = []
        for row in rows:
            payload = dict(row["payload"])
            payload["active"] = bool(row["active"])
            try:
                payload = Service(**payload).model_dump(mode="json")
            except Exception:
                payload["variants"] = payload.get("variants") or []
                payload["modifiers"] = payload.get("modifiers") or []
                payload["minimum_price"] = float(payload.get("minimum_price", 0) or 0)
                payload["taxable"] = bool(payload.get("taxable", False))
                payload["tax_rate"] = float(payload.get("tax_rate", 0) or 0)
                payload["express_enabled"] = bool(payload.get("express_enabled", False))
                payload["express_surcharge_percent"] = float(payload.get("express_surcharge_percent", 0) or 0)
            values.append(payload)
        return values

def get_order_values():
    if not DATABASE_URL:
        return [o.model_dump(mode="json") for o in memory_orders.values()]
    with db() as conn:
        rows = conn.execute("SELECT payload FROM orders ORDER BY created_at DESC").fetchall()
        return [row["payload"] for row in rows]

def record_order_event(order_id: str, event_type: str, from_value=None, to_value=None, notes: str = "", metadata: dict | None = None):
    event = {
        "id": str(uuid.uuid4()),
        "order_id": order_id,
        "event_type": event_type,
        "from_value": None if from_value is None else str(from_value),
        "to_value": None if to_value is None else str(to_value),
        "notes": notes or "",
        "metadata": metadata or {},
    }
    if not DATABASE_URL:
        return event
    with db() as conn:
        row = conn.execute(
            "INSERT INTO order_events (id, order_id, event_type, from_value, to_value, notes, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *",
            (event["id"], order_id, event_type, event["from_value"], event["to_value"], event["notes"], json.dumps(event["metadata"]))
        ).fetchone()
    data = dict(row)
    data["metadata"] = dict(data.get("metadata") or {})
    return data

def get_order_events(order_id: str):
    if not DATABASE_URL:
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM order_events WHERE order_id=%s ORDER BY created_at ASC", (order_id,)).fetchall()
    return [dict(row) for row in rows]

def reward_balance(customer_id: str):
    if not DATABASE_URL:
        customer = memory_customers.get(customer_id)
        return int(getattr(customer, "reward_points", 0) if customer else 0)
    with db() as conn:
        row = conn.execute("SELECT COALESCE(SUM(points),0) AS balance FROM reward_transactions WHERE customer_id=%s", (customer_id,)).fetchone()
    return int(row["balance"] if row else 0)

def get_or_create_referral_code(customer_id: str):
    if not DATABASE_URL:
        return "FC-" + customer_id[:6].upper()
    with db() as conn:
        row = conn.execute("SELECT * FROM referrals WHERE referrer_customer_id=%s ORDER BY created_at LIMIT 1", (customer_id,)).fetchone()
        if row:
            return row["referral_code"]
        code = "FC-" + customer_id.replace("-", "")[:6].upper()
        while conn.execute("SELECT 1 FROM referrals WHERE referral_code=%s", (code,)).fetchone():
            code = "FC-" + uuid.uuid4().hex[:6].upper()
        conn.execute("INSERT INTO referrals (id, referrer_customer_id, referral_code) VALUES (%s,%s,%s)", (str(uuid.uuid4()), customer_id, code))
        return code

def calculate_offer_discount(offer: dict, subtotal: float, is_first_order: bool):
    if not offer.get("active", True): return 0
    if offer.get("first_order_only") and not is_first_order: return 0
    if subtotal < float(offer.get("min_order", 0) or 0): return 0
    usage_limit = offer.get("usage_limit")
    if usage_limit is not None and int(offer.get("usage_count", 0) or 0) >= int(usage_limit): return 0
    kind = offer.get("discount_type", "fixed")
    value = float(offer.get("discount_value", 0) or 0)
    discount = subtotal * value / 100 if kind == "percent" else value
    return round(max(0, min(subtotal, discount)), 2)

def find_valid_offer(code: str, subtotal: float, customer_id: str | None):
    if not capability_enabled("offers_enabled", True):
        return None, 0
    code = (code or "").strip().upper()
    if not code or not DATABASE_URL:
        return None, 0
    with db() as conn:
        offer = conn.execute(
            "SELECT * FROM offers WHERE UPPER(code)=UPPER(%s) AND active=TRUE AND (starts_at IS NULL OR starts_at<=NOW()) AND (ends_at IS NULL OR ends_at>=NOW())",
            (code,),
        ).fetchone()
    if not offer:
        return None, 0
    order_count = 0
    if customer_id:
        order_count = len([o for o in get_order_values() if o.get("customer",{}).get("id")==customer_id])
    discount = calculate_offer_discount(dict(offer), subtotal, order_count==0)
    return (dict(offer), discount) if discount > 0 else (None, 0)

ROLE_PERMISSIONS = {
    "super_admin": {"platform_admin","admin","customers","orders","processing","delivery"},
    "brand_admin": {"admin","customers","orders","processing","delivery"},
    "store_manager": {"admin","customers","orders","processing","delivery"},
    "owner": {"admin","customers","orders","processing","delivery"},
    "manager": {"admin","customers","orders","processing","delivery"},
    "counter": {"customers","orders"},
    "processing": {"orders","processing"},
    "driver": {"orders","delivery"},
}

def get_request_ip(request: Request):
    forwarded=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")

def approximate_ip_location(ip: str):
    if not ip or ip.startswith("127.") or ip in ("::1","localhost"):
        return {"city":"","region":"","country":"","timezone":""}
    global _location_search_last_request
    elapsed=time.monotonic()-_location_search_last_request
    if elapsed<1.0:
        time.sleep(1.0-elapsed)
    try:
        response=httpx.get(f"https://ipapi.co/{ip}/json/",timeout=2.5,headers={"User-Agent":"FabClean/1.0"})
        if response.status_code >= 400:
            return {"city":"","region":"","country":"","timezone":""}
        data=response.json()
        return {
            "city":str(data.get("city") or ""),
            "region":str(data.get("region") or ""),
            "country":str(data.get("country_name") or data.get("country") or ""),
            "timezone":str(data.get("timezone") or ""),
        }
    except Exception:
        return {"city":"","region":"","country":"","timezone":""}

def record_login_audit(staff: dict, request: Request):
    if not DATABASE_URL:
        return
    ip=get_request_ip(request)
    loc=approximate_ip_location(ip)
    with db() as conn:
        conn.execute(
            "INSERT INTO login_audit (id,staff_id,staff_name,staff_email,staff_role,ip_address,city,region,country,timezone,user_agent) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                str(uuid.uuid4()), staff.get("id",""), staff.get("name",""), staff.get("email",""),
                staff.get("role",""), ip, loc["city"], loc["region"], loc["country"], loc["timezone"],
                request.headers.get("user-agent","")[:500],
            ),
        )

def hash_password(password: str, salt: str):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()

def get_user_assignments(user_id: str):
    if not DATABASE_URL:
        return [{"id":"demo-platform","user_id":user_id,"role":"super_admin","scope_type":"platform","brand_id":None,"store_id":None,"active":True}]
    with db() as conn:
        rows=conn.execute(
            "SELECT id,user_id,role,scope_type,brand_id,store_id,active,created_at FROM user_role_assignments WHERE user_id=%s AND active=TRUE ORDER BY scope_type,role",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]

def get_current_staff(x_session_token: str | None):
    if not x_session_token: return None
    if not DATABASE_URL:
        return {"id":"demo-owner","name":"Demo Owner","role":"owner","active":True,"business_id":"fabclean","location_id":"main","assignments":get_user_assignments("demo-owner")}
    with db() as conn:
        row=conn.execute("SELECT s.*,ss.active_brand_id,ss.active_store_id FROM staff_sessions ss JOIN staff_users s ON s.id=ss.staff_id WHERE ss.token=%s AND ss.expires_at>NOW() AND s.active=TRUE",(x_session_token,)).fetchone()
    if not row: return None
    staff=dict(row)
    staff["assignments"]=get_user_assignments(staff["id"])
    return staff

def effective_permissions(staff: dict):
    permissions=set(ROLE_PERMISSIONS.get(staff.get("role",""),set()))
    for assignment in staff.get("assignments") or []:
        permissions.update(ROLE_PERMISSIONS.get(assignment.get("role",""),set()))
    return permissions

def has_role(staff: dict, role: str, brand_id: str | None = None, store_id: str | None = None):
    for assignment in staff.get("assignments") or []:
        if assignment.get("role")!=role: continue
        if brand_id is not None and assignment.get("brand_id") not in (None,brand_id): continue
        if store_id is not None and assignment.get("store_id") not in (None,store_id): continue
        return True
    return False

def require_permission(permission: str, x_session_token: str | None):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    if permission not in effective_permissions(staff): raise HTTPException(403,"Permission denied")
    return staff

def require_super_admin(x_session_token: str | None):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    if not has_role(staff,"super_admin"): raise HTTPException(403,"SuperAdmin access required")
    return staff

def accessible_brand_ids(staff: dict):
    if has_role(staff,"super_admin"): return None
    values={a.get("brand_id") for a in staff.get("assignments") or [] if a.get("brand_id")}
    if staff.get("business_id"): values.add(staff["business_id"])
    return values

def accessible_store_ids(staff: dict, brand_id: str | None = None):
    if has_role(staff,"super_admin"): return None
    assignments=staff.get("assignments") or []
    if any(a.get("role")=="brand_admin" and (brand_id is None or a.get("brand_id")==brand_id) for a in assignments):
        return None
    values={a.get("store_id") for a in assignments if a.get("store_id") and (brand_id is None or a.get("brand_id")==brand_id)}
    if staff.get("location_id"): values.add(staff["location_id"])
    return values

def customer_metrics(customer_id: str, phone: str = ""):
    values = get_order_values()
    matches = [
        o for o in values
        if o.get("customer", {}).get("id") == customer_id
        or (phone and o.get("customer", {}).get("phone") == phone)
    ]
    return {
        "order_count": len(matches),
        "lifetime_value": round(sum(float(o.get("total", 0)) for o in matches), 2),
        "reward_points": reward_balance(customer_id) if capability_enabled("rewards_enabled", True) else 0,
        "referral_code": get_or_create_referral_code(customer_id) if customer_id and capability_enabled("referrals_enabled", True) else "",
    }

def customer_row_to_dict(row):
    data = {
        "id": row["id"],
        "business_id": row.get("business_id", "fabclean"),
        "location_id": row.get("location_id", "main"),
        "name": row["name"],
        "phone": row["phone"],
        "email": row.get("email", ""),
        "notes": row.get("notes", ""),
        "reward_points": int(row.get("reward_points", 0)),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    data.update(customer_metrics(data["id"], data["phone"]))
    return data

def find_customer_by_phone(phone: str):
    phone = (phone or "").strip()
    if not phone:
        return None
    if not DATABASE_URL:
        for customer in memory_customers.values():
            if customer.phone == phone:
                return customer
        return None
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE phone=%s ORDER BY updated_at DESC LIMIT 1",
            (phone,),
        ).fetchone()
    return customer_row_to_dict(row) if row else None

def create_customer_record(payload: CustomerCreate):
    existing = find_customer_by_phone(payload.phone)
    if existing:
        return existing
    customer_id = str(uuid.uuid4())
    if not DATABASE_URL:
        customer = Customer(id=customer_id, **payload.model_dump())
        memory_customers[customer_id] = customer
        return customer
    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO customers (id, business_id, location_id, name, phone, email, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING *
            """,
            (
                customer_id, payload.business_id, payload.location_id, payload.name.strip(),
                payload.phone.strip(), payload.email.strip(), payload.notes.strip()
            ),
        ).fetchone()
    return customer_row_to_dict(row)

@app.get("/")
def root_health():
    return {"status":"ok","app":"FabClean"}

@app.get("/api/health")
def health():
    database = "postgres" if DATABASE_URL else "memory"
    if DATABASE_URL:
        try:
            with db() as conn:
                conn.execute("SELECT 1").fetchone()
        except Exception as exc:
            raise HTTPException(503, f"Database unavailable: {exc}")
    return {"status": "ok", "app": "FabClean", "database": database}

@app.get("/api/settings")
def get_settings():
    return get_settings_value()

@app.put("/api/settings")
def update_settings(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    current = get_settings_value()
    current.update(payload)
    if not DATABASE_URL:
        memory_settings.clear()
        memory_settings.update(current)
        return memory_settings
    with db() as conn:
        conn.execute(
            "INSERT INTO app_settings (id, payload) VALUES ('business', %s::jsonb) "
            "ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload",
            (json.dumps(current),),
        )
    return current

@app.get("/api/services")
def list_services():
    values = get_service_values()
    active_categories = {row["name"] for row in get_category_values(include_inactive=False)}
    return {"services": [item for item in values if item.get("category") in active_categories]}

def get_category_values(include_inactive: bool = True):
    if not DATABASE_URL:
        names = sorted({s.category for s in memory_services.values()})
        return [{"id": n.lower().replace("&", "and").replace(" ", "-"), "name": n, "active": True, "sort_order": i + 1} for i, n in enumerate(names)]
    with db() as conn:
        if include_inactive:
            rows = conn.execute("SELECT id, name, active, sort_order FROM service_categories ORDER BY sort_order, name").fetchall()
        else:
            rows = conn.execute("SELECT id, name, active, sort_order FROM service_categories WHERE active=TRUE ORDER BY sort_order, name").fetchall()
    return [dict(row) for row in rows]

@app.get("/api/admin/overview")
def admin_overview(x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL:
        services=[s.model_dump(mode="json") for s in memory_services.values()]
        categories=get_category_values(include_inactive=True)
        return {
            "settings": memory_settings,
            "services": services,
            "categories": categories,
            "summary": {
                "total": len(services),
                "active": len([x for x in services if x.get("active", True)]),
                "inactive": len([x for x in services if not x.get("active", True)]),
                "categories": len(categories),
            },
        }
    with db() as conn:
        settings_row=conn.execute("SELECT payload FROM app_settings WHERE id='business'").fetchone()
        service_rows=conn.execute("SELECT payload, active FROM services ORDER BY id").fetchall()
        category_rows=conn.execute("SELECT id, name, active, sort_order FROM service_categories ORDER BY sort_order, name").fetchall()
    services=[]
    for row in service_rows:
        payload=dict(row["payload"])
        payload["active"]=bool(row["active"])
        try:
            payload=Service(**payload).model_dump(mode="json")
        except Exception:
            pass
        services.append(payload)
    categories=[dict(row) for row in category_rows]
    return {
        "settings": settings_row["payload"] if settings_row else memory_settings,
        "services": services,
        "categories": categories,
        "summary": {
            "total": len(services),
            "active": len([x for x in services if x.get("active", True)]),
            "inactive": len([x for x in services if not x.get("active", True)]),
            "categories": len(categories),
        },
    }

@app.get("/api/admin/categories")
def admin_list_categories(x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    return {"categories": get_category_values(include_inactive=True)}

@app.post("/api/admin/categories")
def create_category(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "Category name is required")
    category_id = str(payload.get("id") or name.lower().replace("&", "and").replace(" ", "-")).strip()
    active = bool(payload.get("active", True))
    sort_order = int(payload.get("sort_order", 0) or 0)
    if not DATABASE_URL:
        return {"id": category_id, "name": name, "active": active, "sort_order": sort_order}
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM service_categories WHERE id=%s OR LOWER(name)=LOWER(%s)", (category_id, name)).fetchone()
        if exists:
            raise HTTPException(409, "Category already exists")
        row = conn.execute("INSERT INTO service_categories (id, name, active, sort_order) VALUES (%s,%s,%s,%s) RETURNING id,name,active,sort_order", (category_id, name, active, sort_order)).fetchone()
    return dict(row)

@app.put("/api/admin/categories/{category_id}")
def update_category(category_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL:
        return {"id": category_id, "name": str(payload.get("name", category_id)), "active": bool(payload.get("active", True)), "sort_order": int(payload.get("sort_order", 0) or 0)}
    with db() as conn:
        current = conn.execute("SELECT * FROM service_categories WHERE id=%s", (category_id,)).fetchone()
        if not current:
            raise HTTPException(404, "Category not found")
        old_name = current["name"]
        name = str(payload.get("name", old_name)).strip()
        active = bool(payload.get("active", current["active"]))
        sort_order = int(payload.get("sort_order", current["sort_order"]) or 0)
        row = conn.execute("UPDATE service_categories SET name=%s, active=%s, sort_order=%s WHERE id=%s RETURNING id,name,active,sort_order", (name, active, sort_order, category_id)).fetchone()
        if name != old_name:
            service_rows = conn.execute("SELECT id, payload, active FROM services").fetchall()
            for service_row in service_rows:
                service_payload = dict(service_row["payload"])
                if service_payload.get("category") == old_name:
                    service_payload["category"] = name
                    conn.execute("UPDATE services SET payload=%s::jsonb WHERE id=%s", (json.dumps(service_payload), service_row["id"]))
    return dict(row)

@app.get("/api/admin/services")
def admin_list_services(x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    values = get_service_values(include_inactive=True)
    category_rows = get_category_values(include_inactive=True)
    categories = [row["name"] for row in category_rows]
    return {
        "services": values,
        "categories": categories,
        "summary": {
            "total": len(values),
            "active": len([item for item in values if item.get("active", True)]),
            "inactive": len([item for item in values if not item.get("active", True)]),
            "categories": len(categories),
        },
    }

@app.post("/api/services")
def create_service(payload: Service, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    data = payload.model_dump(mode="json")
    if not DATABASE_URL:
        if payload.id in memory_services:
            raise HTTPException(409, "Service ID already exists")
        memory_services[payload.id] = payload
        return payload
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM services WHERE id=%s", (payload.id,)).fetchone()
        if exists:
            raise HTTPException(409, "Service ID already exists")
        conn.execute(
            "INSERT INTO services (id, payload, active) VALUES (%s, %s::jsonb, %s)",
            (payload.id, json.dumps(data), payload.active),
        )
    return payload

@app.post("/api/services/{service_id}/duplicate")
def duplicate_service(service_id: str, payload: dict = {}, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    values = get_service_values(include_inactive=True)
    source = next((item for item in values if item.get("id") == service_id), None)
    if not source:
        raise HTTPException(404, "Service not found")
    new_id = str(payload.get("id") or (service_id + "-copy")).strip()
    new_name = str(payload.get("name") or (source.get("name", "Service") + " Copy")).strip()
    data = dict(source)
    data["id"] = new_id
    data["name"] = new_name
    data["active"] = False
    service = Service(**data)
    return create_service(service)

@app.put("/api/services/{service_id}")
def update_service(service_id: str, payload: Service, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL:
        if service_id not in memory_services:
            raise HTTPException(404, "Service not found")
        memory_services[service_id] = payload
        return payload
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM services WHERE id=%s", (service_id,)).fetchone()
        if not exists:
            raise HTTPException(404, "Service not found")
        conn.execute(
            "UPDATE services SET payload=%s::jsonb, active=%s WHERE id=%s",
            (json.dumps(payload.model_dump(mode="json")), payload.active, service_id),
        )
    return payload

_location_search_cache = {}
_location_search_last_request = 0.0

@app.get("/api/scheduling/location-search")
def scheduling_location_search(q: str = "", x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    query=(q or "").strip()
    if len(query)<2:
        return {"results":[]}
    key=query.lower()
    cached=_location_search_cache.get(key)
    now=datetime.now(timezone.utc)
    if cached and (now-cached["at"]).total_seconds()<86400:
        return {"results":cached["results"],"source":"cache"}
    try:
        response=httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q":query,"format":"jsonv2","addressdetails":1,"limit":5,"countrycodes":"us"},
            headers={"User-Agent":"FabClean/1.2 location-search (admin initiated)"},
            timeout=8.0,
        )
        response.raise_for_status()
        _location_search_last_request=time.monotonic()
        raw=response.json()
    except Exception as exc:
        raise HTTPException(502,f"Location search unavailable: {exc}")
    results=[]
    for item in raw[:5]:
        address=item.get("address") or {}
        results.append({
            "display_name":item.get("display_name",""),
            "lat":item.get("lat",""),
            "lon":item.get("lon",""),
            "city":address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or "",
            "state":address.get("state",""),
            "postcode":address.get("postcode",""),
            "osm_type":item.get("type",""),
        })
    _location_search_cache[key]={"at":now,"results":results}
    return {"results":results,"source":"openstreetmap"}

@app.get("/api/scheduling/admin-summary")
def scheduling_admin_summary(x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL:
        return {"areas":[],"slots":[],"blackouts":[],"settings":get_settings_value()}
    with db() as conn:
        area_rows=conn.execute("SELECT * FROM service_areas ORDER BY name").fetchall()
        slot_rows=conn.execute("SELECT * FROM delivery_slots ORDER BY day_of_week,start_time").fetchall()
        blackout_rows=conn.execute("SELECT * FROM delivery_blackouts ORDER BY blackout_date").fetchall()
        settings_row=conn.execute("SELECT payload FROM app_settings WHERE id='business'").fetchone()
    areas=[]
    for r in area_rows:
        d=dict(r);d["postal_codes"]=list(d.get("postal_codes") or []);areas.append(d)
    return {
        "areas":areas,
        "slots":[dict(r) for r in slot_rows],
        "blackouts":[dict(r) for r in blackout_rows],
        "settings":settings_row["payload"] if settings_row else memory_settings,
    }

@app.get("/api/scheduling/areas")
def list_service_areas(include_inactive: bool = False):
    if not DATABASE_URL: return {"areas": []}
    with db() as conn:
        rows = conn.execute("SELECT * FROM service_areas ORDER BY name").fetchall() if include_inactive else conn.execute("SELECT * FROM service_areas WHERE active=TRUE ORDER BY name").fetchall()
    return {"areas": [{**dict(r), "postal_codes": list(r.get("postal_codes") or [])} for r in rows]}

@app.post("/api/scheduling/areas")
def create_service_area(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    area_id = str(payload.get("id") or uuid.uuid4())
    name = str(payload.get("name","")).strip()
    if not name: raise HTTPException(400, "Area name is required")
    data=(area_id,name,json.dumps(list(payload.get("postal_codes") or [])),bool(payload.get("active",True)),float(payload.get("delivery_fee",0) or 0),float(payload.get("minimum_order",0) or 0),float(payload.get("free_delivery_threshold",0) or 0))
    if not DATABASE_URL: return {"id":area_id,**payload}
    with db() as conn:
        row=conn.execute("INSERT INTO service_areas (id,name,postal_codes,active,delivery_fee,minimum_order,free_delivery_threshold) VALUES (%s,%s,%s::jsonb,%s,%s,%s,%s) RETURNING *",data).fetchone()
    d=dict(row); d["postal_codes"]=list(d.get("postal_codes") or []); return d

@app.put("/api/scheduling/areas/{area_id}")
def update_service_area(area_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL: return {"id":area_id,**payload}
    with db() as conn:
        current=conn.execute("SELECT * FROM service_areas WHERE id=%s",(area_id,)).fetchone()
        if not current: raise HTTPException(404,"Service area not found")
        d=dict(current); d.update(payload)
        row=conn.execute("UPDATE service_areas SET name=%s,postal_codes=%s::jsonb,active=%s,delivery_fee=%s,minimum_order=%s,free_delivery_threshold=%s WHERE id=%s RETURNING *",(d["name"],json.dumps(list(d.get("postal_codes") or [])),bool(d.get("active",True)),float(d.get("delivery_fee",0) or 0),float(d.get("minimum_order",0) or 0),float(d.get("free_delivery_threshold",0) or 0),area_id)).fetchone()
    out=dict(row); out["postal_codes"]=list(out.get("postal_codes") or []); return out

@app.get("/api/scheduling/slots")
def list_delivery_slots(include_inactive: bool = False):
    if not DATABASE_URL: return {"slots":[]}
    with db() as conn:
        rows=conn.execute("SELECT * FROM delivery_slots ORDER BY day_of_week,start_time").fetchall() if include_inactive else conn.execute("SELECT * FROM delivery_slots WHERE active=TRUE ORDER BY day_of_week,start_time").fetchall()
    return {"slots":[dict(r) for r in rows]}

@app.post("/api/scheduling/slots")
def create_delivery_slot(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    slot_id=str(payload.get("id") or uuid.uuid4())
    if not str(payload.get("name","")).strip(): raise HTTPException(400,"Slot name is required")
    if not DATABASE_URL: return {"id":slot_id,**payload}
    with db() as conn:
        row=conn.execute("INSERT INTO delivery_slots (id,name,day_of_week,start_time,end_time,capacity,pickup_enabled,delivery_enabled,active) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",(slot_id,str(payload["name"]).strip(),int(payload.get("day_of_week",0)),str(payload.get("start_time","09:00")),str(payload.get("end_time","11:00")),int(payload.get("capacity",10) or 10),bool(payload.get("pickup_enabled",True)),bool(payload.get("delivery_enabled",True)),bool(payload.get("active",True)))).fetchone()
    return dict(row)

@app.put("/api/scheduling/slots/{slot_id}")
def update_delivery_slot(slot_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL: return {"id":slot_id,**payload}
    with db() as conn:
        current=conn.execute("SELECT * FROM delivery_slots WHERE id=%s",(slot_id,)).fetchone()
        if not current: raise HTTPException(404,"Slot not found")
        d=dict(current); d.update(payload)
        row=conn.execute("UPDATE delivery_slots SET name=%s,day_of_week=%s,start_time=%s,end_time=%s,capacity=%s,pickup_enabled=%s,delivery_enabled=%s,active=%s WHERE id=%s RETURNING *",(d["name"],int(d["day_of_week"]),d["start_time"],d["end_time"],int(d["capacity"]),bool(d["pickup_enabled"]),bool(d["delivery_enabled"]),bool(d["active"]),slot_id)).fetchone()
    return dict(row)

@app.get("/api/scheduling/blackouts")
def list_blackouts():
    if not DATABASE_URL: return {"blackouts":[]}
    with db() as conn: rows=conn.execute("SELECT * FROM delivery_blackouts ORDER BY blackout_date").fetchall()
    return {"blackouts":[dict(r) for r in rows]}

@app.post("/api/scheduling/blackouts")
def create_blackout(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    bid=str(payload.get("id") or uuid.uuid4())
    date=str(payload.get("blackout_date","")).strip()
    if not date: raise HTTPException(400,"Blackout date is required")
    if not DATABASE_URL: return {"id":bid,**payload}
    with db() as conn:
        row=conn.execute("INSERT INTO delivery_blackouts (id,blackout_date,reason,pickup_blocked,delivery_blocked) VALUES (%s,%s,%s,%s,%s) RETURNING *",(bid,date,str(payload.get("reason","")),bool(payload.get("pickup_blocked",True)),bool(payload.get("delivery_blocked",True)))).fetchone()
    return dict(row)

@app.get("/api/scheduling/availability")
def scheduling_availability(postal_code: str = "", mode: str = "pickup_and_delivery"):
    if not DATABASE_URL: return {"areas":[],"slots":[],"blackouts":[]}
    areas=list_service_areas()["areas"]
    if postal_code:
        areas=[a for a in areas if not a.get("postal_codes") or postal_code in a.get("postal_codes",[])]
    slots=list_delivery_slots()["slots"]
    pickup_on=capability_enabled("pickup_enabled", False)
    delivery_on=capability_enabled("delivery_enabled", False)
    if mode=="pickup_only":
        slots=[s for s in slots if pickup_on and s.get("pickup_enabled")]
    elif mode=="delivery_only":
        slots=[s for s in slots if delivery_on and s.get("delivery_enabled")]
    elif mode=="pickup_and_delivery":
        slots=[s for s in slots if pickup_on and delivery_on and s.get("pickup_enabled") and s.get("delivery_enabled")]
    return {"areas":areas,"slots":slots,"blackouts":list_blackouts()["blackouts"],"pickup_enabled":pickup_on,"delivery_enabled":delivery_on}

@app.get("/api/scheduling/orders")
def scheduled_orders(date: str = "", q: str = "", x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    query=(q or "").strip().lower()
    if not DATABASE_URL:
        values=[o.model_dump(mode="json") for o in memory_orders.values()]
        values=[o for o in values if o.get("fulfillment_type") in ("pickup_only","delivery_only","pickup_and_delivery")]
        if date:
            values=[o for o in values if o.get("pickup_date")==date or o.get("delivery_date")==date]
        if query:
            values=[o for o in values if query in str(o.get("order_number","")).lower() or query in str(o.get("customer",{}).get("name","")).lower() or query in str(o.get("customer",{}).get("phone","")).lower()]
        return {"orders":values[:250]}
    clauses=["COALESCE(payload->>'fulfillment_type','walk_in') IN ('pickup_only','delivery_only','pickup_and_delivery')"]
    params=[]
    if date:
        clauses.append("(payload->>'pickup_date'=%s OR payload->>'delivery_date'=%s)")
        params.extend([date,date])
    if query:
        clauses.append("(LOWER(payload->>'order_number') LIKE %s OR LOWER(payload->'customer'->>'name') LIKE %s OR LOWER(payload->'customer'->>'phone') LIKE %s)")
        like="%"+query+"%"
        params.extend([like,like,like])
    sql="SELECT payload FROM orders WHERE "+" AND ".join(clauses)+" ORDER BY created_at DESC LIMIT 250"
    with db() as conn:
        rows=conn.execute(sql,tuple(params)).fetchall()
    return {"orders":[row["payload"] for row in rows]}

@app.get("/api/offers")
def list_offers(include_inactive: bool = False, x_session_token: str | None = Header(default=None)):
    if include_inactive: require_permission("admin",x_session_token)
    if not DATABASE_URL: return {"offers": []}
    with db() as conn:
        if include_inactive:
            rows = conn.execute("SELECT * FROM offers ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM offers WHERE active=TRUE ORDER BY created_at DESC").fetchall()
    return {"offers": [dict(r) for r in rows]}

@app.post("/api/offers")
def create_offer(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    offer_id = str(payload.get("id") or uuid.uuid4())
    name = str(payload.get("name", "")).strip()
    if not name: raise HTTPException(400, "Offer name is required")
    code = str(payload.get("code", "")).strip().upper() or None
    dtype = str(payload.get("discount_type", "fixed"))
    if dtype not in ("fixed","percent"): raise HTTPException(400, "Invalid discount type")
    if not DATABASE_URL: return {**payload, "id": offer_id, "code": code}
    with db() as conn:
        row = conn.execute("""INSERT INTO offers (id,name,code,discount_type,discount_value,min_order,first_order_only,auto_apply,active,starts_at,ends_at,usage_limit)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (offer_id,name,code,dtype,float(payload.get("discount_value",0) or 0),float(payload.get("min_order",0) or 0),bool(payload.get("first_order_only",False)),bool(payload.get("auto_apply",False)),bool(payload.get("active",True)),payload.get("starts_at"),payload.get("ends_at"),payload.get("usage_limit"))).fetchone()
    return dict(row)

@app.put("/api/offers/{offer_id}")
def update_offer(offer_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL: return {**payload, "id": offer_id}
    with db() as conn:
        current = conn.execute("SELECT * FROM offers WHERE id=%s", (offer_id,)).fetchone()
        if not current: raise HTTPException(404, "Offer not found")
        data = dict(current); data.update(payload)
        row = conn.execute("""UPDATE offers SET name=%s,code=%s,discount_type=%s,discount_value=%s,min_order=%s,first_order_only=%s,auto_apply=%s,active=%s,starts_at=%s,ends_at=%s,usage_limit=%s WHERE id=%s RETURNING *""",
            (data["name"],(data.get("code") or None),data["discount_type"],float(data.get("discount_value",0) or 0),float(data.get("min_order",0) or 0),bool(data.get("first_order_only",False)),bool(data.get("auto_apply",False)),bool(data.get("active",True)),data.get("starts_at"),data.get("ends_at"),data.get("usage_limit"),offer_id)).fetchone()
    return dict(row)

@app.post("/api/offers/validate")
def validate_offer(payload: dict):
    require_capability("offers_enabled", "Offers")
    code = str(payload.get("code", "")).strip().upper()
    subtotal = float(payload.get("subtotal", 0) or 0)
    customer_id = payload.get("customer_id")
    if not code: raise HTTPException(400, "Promo code is required")
    offer, discount = find_valid_offer(code, subtotal, customer_id)
    if not offer: raise HTTPException(400, "Promo code is not active or not eligible for this order")
    return {"offer": offer, "discount": discount}

@app.get("/api/customers")
def list_customers(q: str = "", x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    query = (q or "").strip().lower()
    if not DATABASE_URL:
        values = [c.model_dump(mode="json") for c in memory_customers.values()]
        if query:
            values = [
                c for c in values
                if query in c.get("name", "").lower()
                or query in c.get("phone", "").lower()
                or query in c.get("email", "").lower()
            ]
        return {"customers": values[:50]}
    with db() as conn:
        if query:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM customers
                WHERE LOWER(name) LIKE %s OR LOWER(phone) LIKE %s OR LOWER(email) LIKE %s
                ORDER BY updated_at DESC LIMIT 50
                """,
                (like, like, like),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM customers ORDER BY updated_at DESC LIMIT 50").fetchall()
    return {"customers": [customer_row_to_dict(row) for row in rows]}

@app.get("/api/customers/{customer_id}/payments")
def customer_payment_history(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not DATABASE_URL:
        rows=[p for p in memory_payments if p.get("customer_id")==customer_id]
    else:
        with db() as conn:
            rows=[dict(r) for r in conn.execute("SELECT * FROM payment_transactions WHERE customer_id=%s ORDER BY created_at DESC",(customer_id,)).fetchall()]
    return {"payments":rows}

@app.get("/api/customers/{customer_id}/profile")
def get_customer_profile(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    customer = get_customer(customer_id, x_session_token)
    values = get_order_values()
    orders = [o for o in values if o.get("customer",{}).get("id") == customer_id]
    orders.sort(key=lambda o: o.get("created_at",""), reverse=True)
    rewards = customer_rewards(customer_id, x_session_token)
    referrals = customer_referrals(customer_id, x_session_token)
    return {
        "customer": customer,
        "orders": orders[:50],
        "rewards": rewards,
        "referrals": referrals,
        "capabilities": {
            "rewards_enabled": capability_enabled("rewards_enabled", True),
            "referrals_enabled": capability_enabled("referrals_enabled", True),
            "subscriptions_enabled": capability_enabled("subscriptions_enabled", True),
            "ai_assistance_enabled": capability_enabled("ai_assistance_enabled", True),
        },
        "summary": {
            "order_count": len(orders),
            "lifetime_value": round(sum(float(o.get("total",0)) for o in orders),2),
            "open_orders": len([o for o in orders if o.get("status") not in ("completed","collected")]),
            "paid_orders": len([o for o in orders if o.get("payment_status") == "paid"]),
        }
    }

@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not DATABASE_URL:
        customer = memory_customers.get(customer_id)
        if not customer:
            raise HTTPException(404, "Customer not found")
        return customer
    with db() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id=%s", (customer_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Customer not found")
    return customer_row_to_dict(row)

@app.post("/api/customers")
def create_customer(payload: CustomerCreate, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    return create_customer_record(payload)

@app.put("/api/customers/{customer_id}")
def update_customer(customer_id: str, payload: CustomerCreate, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not DATABASE_URL:
        if customer_id not in memory_customers:
            raise HTTPException(404, "Customer not found")
        for cid, existing in memory_customers.items():
            if cid != customer_id and existing.phone == payload.phone.strip():
                raise HTTPException(409, "Another customer already uses this phone number")
        customer = Customer(id=customer_id, **payload.model_dump())
        memory_customers[customer_id] = customer
        return customer
    with db() as conn:
        duplicate = conn.execute("SELECT id FROM customers WHERE phone=%s AND id<>%s LIMIT 1", (payload.phone.strip(), customer_id)).fetchone()
        if duplicate:
            raise HTTPException(409, "Another customer already uses this phone number")
        row = conn.execute(
            """
            UPDATE customers
            SET business_id=%s, location_id=%s, name=%s, phone=%s, email=%s, notes=%s, updated_at=NOW()
            WHERE id=%s RETURNING *
            """,
            (
                payload.business_id, payload.location_id, payload.name.strip(), payload.phone.strip(),
                payload.email.strip(), payload.notes.strip(), customer_id
            ),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Customer not found")
    return customer_row_to_dict(row)

@app.get("/api/customers/{customer_id}/rewards")
def customer_rewards(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not capability_enabled("rewards_enabled", True): return {"enabled":False,"balance":0,"transactions":[]}
    if not DATABASE_URL: return {"enabled":True,"balance": reward_balance(customer_id), "transactions": []}
    with db() as conn:
        rows = conn.execute("SELECT * FROM reward_transactions WHERE customer_id=%s ORDER BY created_at DESC LIMIT 100", (customer_id,)).fetchall()
    return {"enabled":True,"balance": reward_balance(customer_id), "transactions": [dict(r) for r in rows]}

@app.post("/api/customers/{customer_id}/rewards")
def add_reward_transaction(customer_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    require_capability("rewards_enabled", "Rewards")
    points = int(payload.get("points", 0) or 0)
    if points == 0: raise HTTPException(400, "Points cannot be zero")
    tid = str(uuid.uuid4())
    if not DATABASE_URL: return {"id": tid, "customer_id": customer_id, "points": points}
    with db() as conn:
        row = conn.execute("INSERT INTO reward_transactions (id,customer_id,order_id,transaction_type,points,description) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
            (tid,customer_id,payload.get("order_id"),str(payload.get("transaction_type","adjustment")),points,str(payload.get("description","")))).fetchone()
    return dict(row)

@app.get("/api/customers/{customer_id}/referrals")
def customer_referrals(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not capability_enabled("referrals_enabled", True): return {"enabled":False,"referral_code":"","referrals":[]}
    code = get_or_create_referral_code(customer_id)
    if not DATABASE_URL: return {"enabled":True,"referral_code": code, "referrals": []}
    with db() as conn:
        rows = conn.execute("SELECT * FROM referrals WHERE referrer_customer_id=%s ORDER BY created_at DESC", (customer_id,)).fetchall()
    return {"enabled":True,"referral_code": code, "referrals": [dict(r) for r in rows]}

@app.post("/api/referrals/claim")
def claim_referral(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    require_capability("referrals_enabled", "Referrals")
    code = str(payload.get("code", "")).strip().upper()
    referred_customer_id = str(payload.get("referred_customer_id", "")).strip()
    if not code or not referred_customer_id: raise HTTPException(400, "Referral code and customer are required")
    if not DATABASE_URL: return {"status": "claimed"}
    with db() as conn:
        row = conn.execute("SELECT * FROM referrals WHERE referral_code=%s", (code,)).fetchone()
        if not row: raise HTTPException(404, "Referral code not found")
        if row["referrer_customer_id"] == referred_customer_id: raise HTTPException(400, "Customer cannot refer themselves")
        updated = conn.execute("UPDATE referrals SET referred_customer_id=%s,status='claimed' WHERE id=%s RETURNING *", (referred_customer_id,row["id"])).fetchone()
    return dict(updated)

@app.get("/api/orders")
def list_orders(x_session_token: str | None = Header(default=None)):
    staff = require_permission("orders", x_session_token)
    values = get_order_values()
    if staff.get("role") == "owner":
        return {"orders": values, "scope": "all"}
    return {"orders": values, "scope": "operational"}

@app.get("/api/orders/{identifier}")
def get_order(identifier: str, x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    if not DATABASE_URL:
        for order in memory_orders.values():
            if identifier in (order.id, order.order_number, order.barcode_value):
                return order
            if any(item.barcode_value == identifier for item in order.items):
                return order
        raise HTTPException(404, "Order not found")
    with db() as conn:
        rows = conn.execute("SELECT payload FROM orders ORDER BY created_at DESC").fetchall()
        for row in rows:
            order = row["payload"]
            if identifier in (order.get("id"), order.get("order_number"), order.get("barcode_value")):
                return order
            if any(item.get("barcode_value") == identifier for item in order.get("items", [])):
                return order
    raise HTTPException(404, "Order not found")

@app.post("/api/orders")
def create_order(payload: OrderCreate, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    if not payload.quick_dropoff and not payload.items:
        raise HTTPException(400, "At least one service is required unless this is a quick drop-off")
    if payload.quick_dropoff and payload.bag_count < 1:
        raise HTTPException(400, "Quick drop-off requires at least one bag")
    order_id = str(uuid.uuid4())
    if DATABASE_URL:
        with db() as conn:
            row = conn.execute("SELECT COALESCE(MAX(CAST(SUBSTRING(order_number FROM 4) AS INTEGER)), 1000) AS max_seq FROM orders").fetchone()
            sequence = int(row["max_seq"]) + 1
    else:
        sequence = 1001 + len(memory_orders)
    order_number = "FC-" + str(sequence)
    order_barcode = order_number.replace("-", "")

    customer = None
    if payload.customer_id:
        if not DATABASE_URL:
            customer = memory_customers.get(payload.customer_id)
        else:
            with db() as conn:
                row = conn.execute("SELECT * FROM customers WHERE id=%s", (payload.customer_id,)).fetchone()
            customer = customer_row_to_dict(row) if row else None
        if not customer:
            raise HTTPException(404, "Selected customer not found")
    else:
        customer = find_customer_by_phone(payload.customer_phone)
        if not customer:
            customer = create_customer_record(CustomerCreate(
                name=payload.customer_name,
                phone=payload.customer_phone,
                email=payload.customer_email,
            ))
    if isinstance(customer, dict):
        customer = Customer(**customer)

    subtotal = round(sum(item.unit_price * item.quantity for item in payload.items), 2)
    applied_offer = None
    discount = float(payload.discount or 0)
    if payload.promo_code and not capability_enabled("offers_enabled", True):
        raise HTTPException(400, "Offers are disabled in Admin")
    if payload.promo_code:
        applied_offer, discount = find_valid_offer(payload.promo_code, subtotal, customer.id)
        if not applied_offer:
            raise HTTPException(400, "Promo code is not active or not eligible for this order")
    delivery_fee = float(payload.delivery_fee or 0)
    if payload.fulfillment_type != "walk_in":
        needs_pickup = payload.fulfillment_type in ("pickup_only","pickup_and_delivery")
        needs_delivery = payload.fulfillment_type in ("delivery_only","pickup_and_delivery")
        if needs_pickup and not capability_enabled("pickup_enabled", False):
            raise HTTPException(400, "Pickup is disabled in Admin")
        if needs_delivery and not capability_enabled("delivery_enabled", False):
            raise HTTPException(400, "Delivery is disabled in Admin")
        today=datetime.now(timezone.utc).date().isoformat()
        if needs_pickup and (not payload.pickup_date.strip() or not payload.pickup_slot_id):
            raise HTTPException(400, "Pickup date and pickup time slot are required")
        if needs_delivery and (not payload.delivery_date.strip() or not payload.delivery_slot_id):
            raise HTTPException(400, "Delivery date and delivery time slot are required")
        if needs_pickup and payload.pickup_date < today:
            raise HTTPException(400, "Pickup date cannot be in the past")
        if payload.fulfillment_type=="pickup_and_delivery" and payload.delivery_date <= payload.pickup_date:
            raise HTTPException(400, "Delivery date must be after the pickup date")
        if payload.fulfillment_type=="delivery_only" and payload.delivery_date <= today:
            raise HTTPException(400, "Delivery date must be after the Walk-In date")
        if DATABASE_URL:
            pickup_slot = None
            delivery_slot = None
            with db() as conn:
                if needs_pickup:
                    pickup_slot = conn.execute("SELECT * FROM delivery_slots WHERE id=%s AND active=TRUE", (payload.pickup_slot_id,)).fetchone()
                if needs_delivery:
                    delivery_slot = conn.execute("SELECT * FROM delivery_slots WHERE id=%s AND active=TRUE", (payload.delivery_slot_id,)).fetchone()
            if needs_pickup and (not pickup_slot or not pickup_slot["pickup_enabled"]):
                raise HTTPException(400, "Selected pickup time slot is unavailable")
            if needs_delivery and (not delivery_slot or not delivery_slot["delivery_enabled"]):
                raise HTTPException(400, "Selected delivery time slot is unavailable")
    total = round(subtotal - discount + payload.tax + delivery_fee, 2)
    finalized_items = []
    for index, item in enumerate(payload.items, 1):
        data = item.model_dump()
        data["barcode_value"] = order_barcode + "-" + str(index).zfill(3)
        finalized_items.append(type(item)(**data))

    order = Order(
        id=order_id,
        order_number=order_number,
        barcode_value=order_barcode,
        customer=customer,
        fulfillment_type=payload.fulfillment_type,
        items=finalized_items,
        subtotal=subtotal,
        discount=discount,
        tax=payload.tax,
        total=total,
        payment_method=payload.payment_method,
        payment_status=payload.payment_status,
        notes=payload.notes,
        quick_dropoff=payload.quick_dropoff,
        bag_count=payload.bag_count,
        due_at=payload.due_at,
        pricing_status=payload.pricing_status,
        service_area_id=payload.service_area_id,
        service_area_name=payload.service_area_name,
        scheduled_slot_id=payload.pickup_slot_id or payload.scheduled_slot_id,
        scheduled_slot_label=payload.pickup_slot_label or payload.scheduled_slot_label,
        pickup_date=payload.pickup_date,
        pickup_slot_id=payload.pickup_slot_id,
        pickup_slot_label=payload.pickup_slot_label,
        delivery_date=payload.delivery_date,
        delivery_slot_id=payload.delivery_slot_id,
        delivery_slot_label=payload.delivery_slot_label,
        service_address=payload.service_address,
        service_postal_code=payload.service_postal_code,
        delivery_fee=delivery_fee,
        promo_code=payload.promo_code.strip().upper() if payload.promo_code else "",
        offer_id=applied_offer.get("id") if applied_offer else None,
        status="inspection" if payload.quick_dropoff else "received",
    )

    if not DATABASE_URL:
        memory_orders[order_id] = order
        ensure_order_garments(order_id)
        return order

    data = order.model_dump(mode="json")
    with db() as conn:
        conn.execute(
            "INSERT INTO orders (id, order_number, barcode_value, payload) VALUES (%s, %s, %s, %s::jsonb)",
            (order.id, order.order_number, order.barcode_value, json.dumps(data)),
        )
        conn.execute("UPDATE customers SET updated_at=NOW() WHERE id=%s", (customer.id,))
        if applied_offer:
            conn.execute("UPDATE offers SET usage_count=usage_count+1 WHERE id=%s", (applied_offer["id"],))
    record_order_event(order.id, "order_created", None, order.status, metadata={"order_number": order.order_number, "quick_dropoff": order.quick_dropoff, "staff_id": staff.get("id"), "staff_name": staff.get("name")})
    if applied_offer:
        record_order_event(order.id, "promo_applied", None, order.promo_code, metadata={"offer_id": order.offer_id, "discount": order.discount})
    if order.fulfillment_type != "walk_in":
        record_order_event(order.id, "service_scheduled", None, order.pickup_slot_label or order.delivery_slot_label, metadata={"fulfillment_type": order.fulfillment_type, "pickup_mode": "walk_in" if order.fulfillment_type=="delivery_only" else "scheduled", "pickup_date": order.pickup_date, "pickup_slot": order.pickup_slot_label, "delivery_mode": "walk_in" if order.fulfillment_type=="pickup_only" else "scheduled", "delivery_date": order.delivery_date, "delivery_slot": order.delivery_slot_label})
    ensure_order_garments(order.id)
    send_critical_order_notifications(order.model_dump(mode="json"), "order_received", staff)
    return order

def payment_totals(order_id: str, order_total: float):
    if not DATABASE_URL:
        rows=[p for p in memory_payments if p.get("order_id")==order_id]
    else:
        with db() as conn:
            rows=conn.execute("SELECT * FROM payment_transactions WHERE order_id=%s ORDER BY created_at",(order_id,)).fetchall()
    rows=[dict(r) for r in rows]
    paid=round(sum(float(r.get("amount",0) or 0) for r in rows),2)
    balance=round(max(0,float(order_total or 0)-paid),2)
    return rows,paid,balance

@app.get("/api/orders/{order_id}/payments")
def list_order_payments(order_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    order=get_order(order_id,x_session_token)
    data=order.model_dump(mode="json") if hasattr(order,"model_dump") else dict(order)
    rows,paid,balance=payment_totals(order_id,float(data.get("total",0) or 0))
    return {"payments":rows,"paid_total":paid,"balance_due":balance,"order_total":float(data.get("total",0) or 0)}

@app.get("/api/orders/{order_id}/receipt")
def order_receipt(order_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    order=get_order(order_id,x_session_token)
    data=order.model_dump(mode="json") if hasattr(order,"model_dump") else dict(order)
    rows,paid,balance=payment_totals(order_id,float(data.get("total",0) or 0))
    latest=rows[-1] if rows else None
    return {"business_name":get_settings_value().get("business_name","FabClean"),"order":data,"payments":rows,"paid_total":paid,"balance_due":balance,"receipt_number":latest.get("receipt_number") if latest else None}

@app.get("/api/financial/daily")
def daily_financial_summary(date: str | None = None, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    target=date or datetime.now(timezone.utc).date().isoformat()
    if not DATABASE_URL:
        rows=[p for p in memory_payments if str(p.get("created_at",""))[:10]==target]
    else:
        with db() as conn:
            rows=[dict(r) for r in conn.execute("SELECT * FROM payment_transactions WHERE created_at::date=%s::date ORDER BY created_at",(target,)).fetchall()]
    cash=round(sum(float(r.get("amount",0) or 0) for r in rows if r.get("payment_method")=="cash"),2)
    card=round(sum(float(r.get("amount",0) or 0) for r in rows if r.get("payment_method")=="card"),2)
    other=round(sum(float(r.get("amount",0) or 0) for r in rows if r.get("payment_method")=="other"),2)
    refunds=round(sum(abs(float(r.get("amount",0) or 0)) for r in rows if r.get("transaction_type")=="refund"),2)
    net=round(sum(float(r.get("amount",0) or 0) for r in rows),2)
    return {"date":target,"cash":cash,"card":card,"other":other,"refunds":refunds,"net_collected":net,"transaction_count":len(rows),"transactions":rows}

def sync_order_payment_status(order_id: str, order_total: float):
    _,paid,balance=payment_totals(order_id,order_total)
    status="paid" if float(order_total or 0)>0 and balance<=0 else ("partial" if paid>0 else "unpaid")
    if not DATABASE_URL:
        if order_id in memory_orders:
            data=memory_orders[order_id].model_dump(mode="json")
            data["payment_status"]=status
            memory_orders[order_id]=Order(**data)
        return status
    with db() as conn:
        row=conn.execute("SELECT payload FROM orders WHERE id=%s",(order_id,)).fetchone()
        if row:
            data=dict(row["payload"])
            data["payment_status"]=status
            conn.execute("UPDATE orders SET payload=%s::jsonb WHERE id=%s",(json.dumps(data),order_id))
    return status

@app.post("/api/orders/{order_id}/payments")
def create_order_payment(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    order=get_order(order_id,x_session_token)
    data=order.model_dump(mode="json") if hasattr(order,"model_dump") else dict(order)
    order_total=float(data.get("total",0) or 0)
    amount=float(payload.get("amount",0) or 0)
    kind=str(payload.get("transaction_type","payment")).lower()
    if kind not in ("payment","refund","adjustment"):
        raise HTTPException(400,"Invalid transaction type")
    if kind=="payment" and amount<=0:
        raise HTTPException(400,"Payment amount must be greater than zero")
    if kind=="refund":
        if amount<=0:
            raise HTTPException(400,"Refund amount must be greater than zero")
        amount=-amount
    method=str(payload.get("payment_method","cash")).lower()
    if method not in ("cash","card","other"):
        raise HTTPException(400,"Invalid payment method")
    customer=data.get("customer") or {}
    pid=str(uuid.uuid4())
    receipt="FCR-"+datetime.now(timezone.utc).strftime("%Y%m%d")+"-"+uuid.uuid4().hex[:6].upper()
    item={"id":pid,"receipt_number":receipt,"order_id":order_id,"customer_id":customer.get("id"),"transaction_type":kind,"payment_method":method,"amount":round(amount,2),"reference_number":str(payload.get("reference_number","")),"notes":str(payload.get("notes","")),"staff_id":staff.get("id"),"staff_name":staff.get("name","")}
    if not DATABASE_URL:
        item["created_at"]=datetime.now(timezone.utc).isoformat()
        memory_payments.append(item)
    else:
        with db() as conn:
            row=conn.execute("INSERT INTO payment_transactions (id,receipt_number,order_id,customer_id,transaction_type,payment_method,amount,reference_number,notes,staff_id,staff_name) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",(pid,receipt,order_id,customer.get("id"),kind,method,amount,item["reference_number"],item["notes"],staff.get("id"),staff.get("name",""))).fetchone()
            item=dict(row)
    status=sync_order_payment_status(order_id,order_total)
    record_order_event(order_id,"payment_recorded",None,amount,f"{kind.title()} via {method}",{"receipt_number":receipt,"staff_id":staff.get("id"),"staff_name":staff.get("name","")})
    _,paid,balance=payment_totals(order_id,order_total)
    return {"payment":item,"paid_total":paid,"balance_due":balance,"payment_status":status}

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    allowed = {
        "items", "notes", "discount", "tax", "payment_method", "payment_status",
        "due_at", "pricing_status", "quick_dropoff", "bag_count", "status",
        "service_area_id", "service_area_name", "scheduled_slot_id", "scheduled_slot_label",
        "pickup_date", "pickup_slot_id", "pickup_slot_label", "delivery_date", "delivery_slot_id", "delivery_slot_label",
        "service_address", "service_postal_code", "delivery_fee", "fulfillment_type"
    }
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "No supported order fields supplied")

    requested_status=updates.get("status")
    if requested_status in ("ready_for_pickup","collected","completed") and DATABASE_URL:
        with db() as conn:
            garment_rows=conn.execute("SELECT assembled FROM order_garments WHERE order_id=%s",(order_id,)).fetchall()
        if garment_rows and any(not bool(g["assembled"]) for g in garment_rows):
            raise HTTPException(400,"Assembly is incomplete. Scan all garment tags before Ready for Pickup.")

    def apply(order):
        before = dict(order)
        for key, value in updates.items():
            order[key] = value
        items = order.get("items", [])
        base_barcode = order.get("barcode_value", order.get("order_number", "").replace("-", ""))
        for index, item in enumerate(items, 1):
            if not item.get("barcode_value"):
                item["barcode_value"] = base_barcode + "-" + str(index).zfill(3)
        order["items"] = items
        order["subtotal"] = round(sum(float(i.get("unit_price", 0)) * float(i.get("quantity", 0)) for i in items), 2)
        order["total"] = round(order["subtotal"] - float(order.get("discount", 0)) + float(order.get("tax", 0)) + float(order.get("delivery_fee", 0)), 2)
        return before, order

    if not DATABASE_URL:
        order_obj = memory_orders.get(order_id)
        if not order_obj:
            raise HTTPException(404, "Order not found")
        _, data = apply(order_obj.model_dump(mode="json"))
        updated = Order(**data)
        memory_orders[order_id] = updated
        return updated

    with db() as conn:
        row = conn.execute("SELECT payload FROM orders WHERE id=%s", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Order not found")
        before, order = apply(row["payload"])
        conn.execute("UPDATE orders SET payload=%s::jsonb WHERE id=%s", (json.dumps(order), order_id))
    if before.get("status") != order.get("status"):
        record_order_event(order_id, "status_changed", before.get("status"), order.get("status"), metadata={"staff_id": staff.get("id"), "staff_name": staff.get("name")})
        if order.get("status") == "ready_for_pickup":
            send_critical_order_notifications(order, "ready_for_pickup", staff)
    if before.get("payment_status") != order.get("payment_status"):
        record_order_event(order_id, "payment_changed", before.get("payment_status"), order.get("payment_status"))
    if before.get("pricing_status") != order.get("pricing_status"):
        record_order_event(order_id, "pricing_changed", before.get("pricing_status"), order.get("pricing_status"))
    if before.get("due_at") != order.get("due_at"):
        record_order_event(order_id, "due_date_changed", before.get("due_at"), order.get("due_at"))
    if before.get("items") != order.get("items"):
        record_order_event(order_id, "items_changed", str(len(before.get("items", []))), str(len(order.get("items", []))), metadata={"item_count": len(order.get("items", []))})
    if before.get("notes") != order.get("notes"):
        record_order_event(order_id, "notes_changed", None, None)
    return order

GARMENT_STAGES = {"tagged","inspection","cleaning","quality_check","assembly","ready"}

def garment_piece_count(item: dict):
    qty=float(item.get("quantity",1) or 1)
    unit=str(item.get("unit_label","item") or "item").lower()
    if unit in ("lb","lbs","pound","pounds","kg","kgs","kilogram","kilograms"):
        return 1
    rounded=int(round(qty))
    return max(1,rounded) if abs(qty-rounded) < 0.001 else 1

def ensure_order_garments(order_id: str):
    if not DATABASE_URL:
        order_obj=memory_orders.get(order_id)
        if not order_obj:
            raise HTTPException(404,"Order not found")
        order=order_obj.model_dump(mode="json")
        rows=memory_garments.setdefault(order_id,[])
        next_index=max([g.get("garment_index",0) for g in rows],default=0)+1
        for line_index,item in enumerate(order.get("items",[]),1):
            pieces=garment_piece_count(item)
            current_for_line=sum(1 for g in rows if g.get("service_line_index")==line_index)
            for _ in range(current_for_line,pieces):
                code=order["order_number"].replace("-","")+"-"+str(next_index).zfill(3)
                rows.append({"id":str(uuid.uuid4()),"order_id":order_id,"garment_code":code,"garment_index":next_index,"service_line_index":line_index,"service_name":item.get("service_name","Garment"),"service_line_barcode":item.get("barcode_value") or "","last_stage":"tagged","assembled":False,"tag_print_count":0,"created_at":datetime.now(timezone.utc).isoformat(),"updated_at":datetime.now(timezone.utc).isoformat()})
                next_index+=1
        return rows
    with db() as conn:
        row=conn.execute("SELECT payload FROM orders WHERE id=%s",(order_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Order not found")
        order=dict(row["payload"])
        existing=[dict(r) for r in conn.execute("SELECT * FROM order_garments WHERE order_id=%s ORDER BY garment_index",(order_id,)).fetchall()]
        next_index=max([g["garment_index"] for g in existing],default=0)+1
        for line_index,item in enumerate(order.get("items",[]),1):
            pieces=garment_piece_count(item)
            current_for_line=sum(1 for g in existing if g.get("service_line_index")==line_index)
            for _ in range(current_for_line,pieces):
                code=order["order_number"].replace("-","")+"-"+str(next_index).zfill(3)
                garment=conn.execute(
                    "INSERT INTO order_garments (id,order_id,garment_code,garment_index,service_line_index,service_name,service_line_barcode) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (str(uuid.uuid4()),order_id,code,next_index,line_index,item.get("service_name","Garment"),item.get("barcode_value") or "")
                ).fetchone()
                existing.append(dict(garment)); next_index+=1
        return [dict(r) for r in conn.execute("SELECT * FROM order_garments WHERE order_id=%s ORDER BY garment_index",(order_id,)).fetchall()]

@app.get("/api/orders/{order_id}/garments")
def list_order_garments(order_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    rows=ensure_order_garments(order_id)
    assembled=sum(1 for g in rows if g.get("assembled"))
    return {"garments":rows,"expected_count":len(rows),"assembled_count":assembled,"assembly_complete":bool(rows) and assembled==len(rows)}

@app.get("/api/garments/{garment_code}")
def find_garment(garment_code: str, x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    code=garment_code.strip().upper()
    if not DATABASE_URL:
        for rows in memory_garments.values():
            for garment in rows:
                if garment.get("garment_code","").upper()==code:
                    order=memory_orders.get(garment["order_id"])
                    return {"garment":garment,"order":order.model_dump(mode="json") if order else None}
        raise HTTPException(404,"Garment not found")
    with db() as conn:
        garment=conn.execute("SELECT * FROM order_garments WHERE UPPER(garment_code)=UPPER(%s)",(code,)).fetchone()
        if not garment: raise HTTPException(404,"Garment not found")
        order=conn.execute("SELECT payload FROM orders WHERE id=%s",(garment["order_id"],)).fetchone()
    return {"garment":dict(garment),"order":dict(order["payload"]) if order else None}

@app.post("/api/orders/{order_id}/garments/{garment_code}/scan")
def scan_garment(order_id: str, garment_code: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    stage=str(payload.get("stage","assembly")).lower()
    if stage not in GARMENT_STAGES:
        raise HTTPException(400,"Invalid garment stage")
    ensure_order_garments(order_id)
    if not DATABASE_URL:
        rows=memory_garments.get(order_id,[])
        garment=next((g for g in rows if g.get("garment_code","").upper()==garment_code.upper()),None)
        if not garment: raise HTTPException(404,"Garment not found for this order")
        garment["last_stage"]=stage; garment["assembled"]=stage in ("assembly","ready"); garment["updated_at"]=datetime.now(timezone.utc).isoformat()
    else:
        with db() as conn:
            garment=conn.execute("SELECT * FROM order_garments WHERE order_id=%s AND UPPER(garment_code)=UPPER(%s)",(order_id,garment_code)).fetchone()
            if not garment: raise HTTPException(404,"Garment not found for this order")
            garment=conn.execute("UPDATE order_garments SET last_stage=%s,assembled=%s,updated_at=NOW() WHERE id=%s RETURNING *",(stage,stage in ("assembly","ready"),garment["id"])).fetchone()
            garment=dict(garment)
    record_order_event(order_id,"garment_scanned",garment_code,stage,metadata={"garment_code":garment_code,"stage":stage,"staff_id":staff.get("id"),"staff_name":staff.get("name","")})
    return garment

@app.post("/api/orders/{order_id}/garments/{garment_code}/reprint")
def reprint_garment_tag(order_id: str, garment_code: str, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    ensure_order_garments(order_id)
    if not DATABASE_URL:
        rows=memory_garments.get(order_id,[])
        garment=next((g for g in rows if g.get("garment_code","").upper()==garment_code.upper()),None)
        if not garment: raise HTTPException(404,"Garment not found for this order")
        garment["tag_print_count"]=int(garment.get("tag_print_count",0))+1
    else:
        with db() as conn:
            garment=conn.execute("UPDATE order_garments SET tag_print_count=tag_print_count+1,updated_at=NOW() WHERE order_id=%s AND UPPER(garment_code)=UPPER(%s) RETURNING *",(order_id,garment_code)).fetchone()
            if not garment: raise HTTPException(404,"Garment not found for this order")
            garment=dict(garment)
    record_order_event(order_id,"garment_tag_reprinted",garment_code,str(garment.get("tag_print_count",0)),metadata={"garment_code":garment_code,"staff_id":staff.get("id"),"staff_name":staff.get("name","")})
    return garment

@app.post("/api/orders/{order_id}/assembly/complete")
def complete_garment_assembly(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    rows=ensure_order_garments(order_id)
    missing=[g for g in rows if not g.get("assembled")]
    override=bool(payload.get("override",False))
    if missing and not override:
        raise HTTPException(400,f"{len(missing)} garment(s) are still missing from assembly")
    if missing and override and staff.get("role") not in ("owner","manager"):
        raise HTTPException(403,"Only Owner or Manager can override incomplete assembly")
    if DATABASE_URL:
        with db() as conn:
            row=conn.execute("SELECT payload FROM orders WHERE id=%s",(order_id,)).fetchone()
            if not row: raise HTTPException(404,"Order not found")
            order=dict(row["payload"]); before=order.get("status"); order["status"]="ready_for_pickup"
            conn.execute("UPDATE orders SET payload=%s::jsonb WHERE id=%s",(json.dumps(order),order_id))
    else:
        order_obj=memory_orders.get(order_id)
        if not order_obj: raise HTTPException(404,"Order not found")
        order=order_obj.model_dump(mode="json"); before=order.get("status"); order["status"]="ready_for_pickup"; memory_orders[order_id]=Order(**order)
    record_order_event(order_id,"assembly_completed",str(len(rows)-len(missing)),str(len(rows)),metadata={"override":override,"missing_count":len(missing),"staff_id":staff.get("id"),"staff_name":staff.get("name","")})
    if before!="ready_for_pickup":
        record_order_event(order_id,"status_changed",before,"ready_for_pickup",metadata={"staff_id":staff.get("id"),"staff_name":staff.get("name","")})
        send_critical_order_notifications(order,"ready_for_pickup",staff)
    return {"order":order,"garments":rows,"missing_count":len(missing),"override":override}

@app.get("/api/orders/{order_id}/events")
def list_order_events(order_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    return {"events": get_order_events(order_id)}

@app.get("/api/orders/{order_id}/inspection")
def get_order_inspection(order_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("processing",x_session_token)
    if not DATABASE_URL:
        return {"items": [], "photos": []}
    with db() as conn:
        item_rows = conn.execute("SELECT * FROM order_item_inspections WHERE order_id=%s ORDER BY item_barcode", (order_id,)).fetchall()
        photo_rows = conn.execute("SELECT id, order_id, item_barcode, phase, filename, content_type, created_at FROM order_photos WHERE order_id=%s ORDER BY created_at", (order_id,)).fetchall()
    return {
        "items": [{**dict(row), "tags": list(row.get("tags") or [])} for row in item_rows],
        "photos": [dict(row) for row in photo_rows],
    }

@app.put("/api/orders/{order_id}/inspection/{item_barcode}")
def update_item_inspection(order_id: str, item_barcode: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("processing",x_session_token)
    tags = list(payload.get("tags") or [])
    notes = str(payload.get("condition_notes", ""))
    status = str(payload.get("condition_status", "inspected"))
    if not DATABASE_URL:
        return {"order_id": order_id, "item_barcode": item_barcode, "tags": tags, "condition_notes": notes, "condition_status": status}
    with db() as conn:
        row = conn.execute(
            """INSERT INTO order_item_inspections (order_id, item_barcode, tags, condition_notes, condition_status)
               VALUES (%s,%s,%s::jsonb,%s,%s)
               ON CONFLICT (order_id, item_barcode) DO UPDATE
               SET tags=EXCLUDED.tags, condition_notes=EXCLUDED.condition_notes, condition_status=EXCLUDED.condition_status, updated_at=NOW()
               RETURNING *""",
            (order_id, item_barcode, json.dumps(tags), notes, status)
        ).fetchone()
    record_order_event(order_id, "inspection_updated", None, item_barcode, notes=notes, metadata={"tags": tags, "condition_status": status, "staff_id": staff.get("id"), "staff_name": staff.get("name")})
    data = dict(row); data["tags"] = list(data.get("tags") or [])
    return data

@app.post("/api/orders/{order_id}/photos")
def add_order_photo(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("processing",x_session_token)
    encoded = str(payload.get("data_base64", ""))
    if not encoded:
        raise HTTPException(400, "Photo data is required")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        raise HTTPException(400, "Invalid photo data")
    if len(raw) > 4 * 1024 * 1024:
        raise HTTPException(413, "Photo must be 4 MB or smaller")
    photo_id = str(uuid.uuid4())
    phase = str(payload.get("phase", "inspection"))
    if phase not in ("before", "inspection", "after"):
        raise HTTPException(400, "Invalid photo phase")
    item_barcode = payload.get("item_barcode")
    filename = str(payload.get("filename", "inspection-photo.jpg"))
    content_type = str(payload.get("content_type", "image/jpeg"))
    if not DATABASE_URL:
        return {"id": photo_id, "order_id": order_id, "item_barcode": item_barcode, "phase": phase, "filename": filename, "content_type": content_type}
    with db() as conn:
        row = conn.execute(
            "INSERT INTO order_photos (id, order_id, item_barcode, phase, filename, content_type, data) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,order_id,item_barcode,phase,filename,content_type,created_at",
            (photo_id, order_id, item_barcode, phase, filename, content_type, raw)
        ).fetchone()
    record_order_event(order_id, "photo_added", None, phase, metadata={"photo_id": photo_id, "item_barcode": item_barcode, "staff_id": staff.get("id"), "staff_name": staff.get("name")})
    return dict(row)

@app.get("/api/orders/{order_id}/photos/{photo_id}")
def get_order_photo(order_id: str, photo_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("processing",x_session_token)
    if not DATABASE_URL:
        raise HTTPException(404, "Photo not found")
    with db() as conn:
        row = conn.execute("SELECT content_type, data FROM order_photos WHERE id=%s AND order_id=%s", (photo_id, order_id)).fetchone()
    if not row:
        raise HTTPException(404, "Photo not found")
    return Response(content=bytes(row["data"]), media_type=row["content_type"])

@app.delete("/api/orders/{order_id}/photos/{photo_id}")
def delete_order_photo(order_id: str, photo_id: str, x_session_token: str | None = Header(default=None)):
    staff=require_permission("processing",x_session_token)
    if not DATABASE_URL:
        return {"deleted": True}
    with db() as conn:
        row = conn.execute("DELETE FROM order_photos WHERE id=%s AND order_id=%s RETURNING id", (photo_id, order_id)).fetchone()
    if not row:
        raise HTTPException(404, "Photo not found")
    record_order_event(order_id, "photo_deleted", photo_id, None, metadata={"staff_id": staff.get("id"), "staff_name": staff.get("name")})
    return {"deleted": True}

@app.put("/api/orders/{order_id}/status")
def update_order_status(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    if not DATABASE_URL:
        order = memory_orders.get(order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        previous = order.status
        order.status = payload.get("status", order.status)
        if previous != order.status:
            record_order_event(order_id, "status_changed", previous, order.status, notes=str(payload.get("notes", "")))
        return order
    with db() as conn:
        row = conn.execute("SELECT payload FROM orders WHERE id=%s", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Order not found")
        order = row["payload"]
        previous = order.get("status", "received")
        order["status"] = payload.get("status", previous)
        conn.execute("UPDATE orders SET payload=%s::jsonb WHERE id=%s", (json.dumps(order), order_id))
    if previous != order["status"]:
        record_order_event(order_id, "status_changed", previous, order["status"], notes=str(payload.get("notes", "")), metadata={"staff_id": staff.get("id"), "staff_name": staff.get("name")})
    return order

def record_platform_audit(actor: dict, action: str, brand_id: str | None = None, store_id: str | None = None, metadata: dict | None = None):
    if not DATABASE_URL: return
    with db() as conn:
        conn.execute(
            "INSERT INTO platform_audit (id,actor_user_id,action,brand_id,store_id,metadata) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (str(uuid.uuid4()),actor.get("id",""),action,brand_id,store_id,json.dumps(metadata or {})),
        )

@app.get("/api/context")
def get_context(x_session_token: str | None = Header(default=None)):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    if not DATABASE_URL:
        return {
            "staff":staff,
            "permissions":sorted(effective_permissions(staff)),
            "assignments":staff.get("assignments",[]),
            "active_brand":{"id":"fabclean","name":"FabClean","slug":"fabclean"},
            "active_store":{"id":"main","brand_id":"fabclean","name":"Main Store","store_code":"MAIN"},
            "brands":[{"id":"fabclean","name":"FabClean","slug":"fabclean"}],
            "stores":[{"id":"main","brand_id":"fabclean","name":"Main Store","store_code":"MAIN"}],
            "is_super_admin":True,
        }
    brand_ids=accessible_brand_ids(staff)
    with db() as conn:
        if brand_ids is None:
            brands=conn.execute("SELECT * FROM brands ORDER BY name").fetchall()
        elif brand_ids:
            brands=conn.execute("SELECT * FROM brands WHERE id=ANY(%s) ORDER BY name",(list(brand_ids),)).fetchall()
        else:
            brands=[]
        store_ids=accessible_store_ids(staff)
        if store_ids is None:
            if brand_ids is None:
                stores=conn.execute("SELECT * FROM stores WHERE active=TRUE ORDER BY brand_id,name").fetchall()
            elif brand_ids:
                stores=conn.execute("SELECT * FROM stores WHERE active=TRUE AND brand_id=ANY(%s) ORDER BY brand_id,name",(list(brand_ids),)).fetchall()
            else:
                stores=[]
        elif store_ids:
            stores=conn.execute("SELECT * FROM stores WHERE active=TRUE AND id=ANY(%s) ORDER BY brand_id,name",(list(store_ids),)).fetchall()
        else:
            stores=[]
    # Only resolve stores belonging to the active brand; never silently cross tenants.
    requested_brand_id=staff.get("active_brand_id") or staff.get("business_id")
    active_brand=next((dict(x) for x in brands if x["id"]==requested_brand_id),dict(brands[0]) if brands else None)
    active_brand_id=active_brand["id"] if active_brand else None
    brand_stores=[dict(x) for x in stores if x["brand_id"]==active_brand_id]
    requested_store_id=staff.get("active_store_id")
    if requested_store_id is None and staff.get("active_brand_id") is None:
        requested_store_id=staff.get("location_id")
    active_store=next((x for x in brand_stores if x["id"]==requested_store_id),None)
    if not active_store and staff.get("active_brand_id") is None:
        active_store=brand_stores[0] if brand_stores else None
    safe_staff=dict(staff); safe_staff.pop("password_hash",None); safe_staff.pop("password_salt",None)
    return {
        "staff":safe_staff,
        "permissions":sorted(effective_permissions(staff)),
        "assignments":staff.get("assignments",[]),
        "active_brand":active_brand,
        "active_store":active_store,
        "brands":[dict(x) for x in brands],
        "stores":[dict(x) for x in stores],
        "is_super_admin":has_role(staff,"super_admin"),
    }

@app.put("/api/context")
def update_context(payload: dict, x_session_token: str | None = Header(default=None)):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    brand_id=str(payload.get("brand_id") or staff.get("active_brand_id") or staff.get("business_id") or "").strip()
    store_id=str(payload.get("store_id") or "").strip() or None
    brand_ids=accessible_brand_ids(staff)
    if brand_ids is not None and brand_id not in brand_ids: raise HTTPException(403,"Brand is not accessible")
    if not DATABASE_URL: return {"active_brand_id":brand_id,"active_store_id":store_id}
    with db() as conn:
        brand=conn.execute("SELECT id FROM brands WHERE id=%s AND status='active'",(brand_id,)).fetchone()
        if not brand: raise HTTPException(404,"Brand not found")
        if store_id:
            store=conn.execute("SELECT id FROM stores WHERE id=%s AND brand_id=%s AND active=TRUE",(store_id,brand_id)).fetchone()
            if not store: raise HTTPException(404,"Store not found in this brand")
            store_ids=accessible_store_ids(staff,brand_id)
            if store_ids is not None and store_id not in store_ids: raise HTTPException(403,"Store is not accessible")
        updated=conn.execute("UPDATE staff_sessions SET active_brand_id=%s,active_store_id=%s WHERE token=%s AND expires_at>NOW() RETURNING token",(brand_id,store_id,x_session_token)).fetchone()
        if not updated: raise HTTPException(401,"Session expired; sign in again")
    record_platform_audit(staff,"context_switched",brand_id=brand_id,store_id=store_id)
    # Read the persisted session through the same path used by subsequent screens.
    return get_context(x_session_token)

@app.get("/api/platform/brands")
def list_brands(x_session_token: str | None = Header(default=None)):
    require_super_admin(x_session_token)
    if not DATABASE_URL: return {"brands":[{"id":"fabclean","name":"FabClean","slug":"fabclean","status":"active"}]}
    with db() as conn:
        rows=conn.execute("SELECT b.*,COUNT(s.id) AS store_count FROM brands b LEFT JOIN stores s ON s.brand_id=b.id GROUP BY b.id ORDER BY b.name").fetchall()
    return {"brands":[dict(r) for r in rows]}

@app.post("/api/platform/brands")
def create_brand(payload: dict, x_session_token: str | None = Header(default=None)):
    actor=require_super_admin(x_session_token)
    name=str(payload.get("name","")).strip()
    slug=str(payload.get("slug","")).strip().lower().replace(" ","-")
    if not name or not slug: raise HTTPException(400,"Brand name and slug are required")
    if not DATABASE_URL: return {"id":slug,"name":name,"slug":slug,"status":"active"}
    brand_id=str(uuid.uuid4())
    with db() as conn:
        try:
            row=conn.execute(
                """INSERT INTO brands (id,name,slug,legal_name,status,primary_email,primary_phone,country,timezone,currency,logo_url)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (brand_id,name,slug,str(payload.get("legal_name","")),str(payload.get("status","active")),str(payload.get("primary_email","")),str(payload.get("primary_phone","")),str(payload.get("country","US")),str(payload.get("timezone","America/Chicago")),str(payload.get("currency","USD")),str(payload.get("logo_url",""))),
            ).fetchone()
        except Exception:
            raise HTTPException(409,"Brand slug already exists")
    record_platform_audit(actor,"brand_created",brand_id=brand_id,metadata={"name":name,"slug":slug})
    return dict(row)

@app.put("/api/platform/brands/{brand_id}")
def update_brand(brand_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    actor=require_super_admin(x_session_token)
    if not DATABASE_URL: return {"id":brand_id,**payload}
    with db() as conn:
        current=conn.execute("SELECT * FROM brands WHERE id=%s",(brand_id,)).fetchone()
        if not current: raise HTTPException(404,"Brand not found")
        d=dict(current); d.update(payload)
        row=conn.execute(
            """UPDATE brands SET name=%s,slug=%s,legal_name=%s,status=%s,primary_email=%s,primary_phone=%s,country=%s,timezone=%s,currency=%s,logo_url=%s,updated_at=NOW()
               WHERE id=%s RETURNING *""",
            (str(d["name"]).strip(),str(d["slug"]).strip().lower(),str(d.get("legal_name","")),str(d.get("status","active")),str(d.get("primary_email","")),str(d.get("primary_phone","")),str(d.get("country","US")),str(d.get("timezone","America/Chicago")),str(d.get("currency","USD")),str(d.get("logo_url","")),brand_id),
        ).fetchone()
    record_platform_audit(actor,"brand_updated",brand_id=brand_id)
    return dict(row)

def require_brand_admin_for(brand_id: str, x_session_token: str | None):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    if has_role(staff,"super_admin") or has_role(staff,"brand_admin",brand_id=brand_id):
        return staff
    raise HTTPException(403,"Brand Admin access required")

@app.get("/api/brand/stores")
def list_brand_stores(brand_id: str = "", include_inactive: bool = True, x_session_token: str | None = Header(default=None)):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    requested=brand_id or staff.get("business_id") or "fabclean"
    require_brand_admin_for(requested,x_session_token)
    if not DATABASE_URL: return {"stores":[{"id":"main","brand_id":requested,"store_code":"MAIN","name":"Main Store","store_type":"regular","active":True}]}
    with db() as conn:
        sql="SELECT * FROM stores WHERE brand_id=%s"+("" if include_inactive else " AND active=TRUE")+" ORDER BY name"
        rows=conn.execute(sql,(requested,)).fetchall()
    return {"stores":[dict(r) for r in rows]}

@app.post("/api/brand/stores")
def create_store(payload: dict, x_session_token: str | None = Header(default=None)):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    requested_brand=str(payload.get("brand_id") or staff.get("business_id") or "").strip()
    require_brand_admin_for(requested_brand,x_session_token)
    name=str(payload.get("name","")).strip(); code=str(payload.get("store_code","")).strip().upper()
    if not requested_brand or not name or not code: raise HTTPException(400,"Brand, store name and store code are required")
    parent_id=payload.get("parent_store_id") or None
    if not DATABASE_URL: return {"id":str(uuid.uuid4()),"brand_id":requested_brand,"store_code":code,"name":name,**payload}
    store_id=str(uuid.uuid4())
    with db() as conn:
        if parent_id:
            parent=conn.execute("SELECT id FROM stores WHERE id=%s AND brand_id=%s",(parent_id,requested_brand)).fetchone()
            if not parent: raise HTTPException(400,"Parent store must belong to the same brand")
        try:
            row=conn.execute(
                """INSERT INTO stores (id,brand_id,store_code,name,parent_store_id,store_type,address_line1,address_line2,city,state,postal_code,country,latitude,longitude,timezone,phone,email,active)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (store_id,requested_brand,code,name,parent_id,str(payload.get("store_type","regular")),str(payload.get("address_line1","")),str(payload.get("address_line2","")),str(payload.get("city","")),str(payload.get("state","")),str(payload.get("postal_code","")),str(payload.get("country","US")),payload.get("latitude"),payload.get("longitude"),str(payload.get("timezone","America/Chicago")),str(payload.get("phone","")),str(payload.get("email","")),bool(payload.get("active",True))),
            ).fetchone()
        except Exception:
            raise HTTPException(409,"Store code already exists in this brand")
    record_platform_audit(staff,"store_created",brand_id=requested_brand,store_id=store_id,metadata={"name":name,"store_code":code})
    return dict(row)

@app.put("/api/brand/stores/{store_id}")
def update_store(store_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    if not DATABASE_URL: return {"id":store_id,**payload}
    with db() as conn:
        current=conn.execute("SELECT * FROM stores WHERE id=%s",(store_id,)).fetchone()
        if not current: raise HTTPException(404,"Store not found")
        require_brand_admin_for(current["brand_id"],x_session_token)
        d=dict(current); d.update(payload)
        parent_id=d.get("parent_store_id") or None
        if parent_id:
            parent=conn.execute("SELECT id FROM stores WHERE id=%s AND brand_id=%s",(parent_id,current["brand_id"])).fetchone()
            if not parent or parent_id==store_id: raise HTTPException(400,"Invalid parent store")
        row=conn.execute(
            """UPDATE stores SET store_code=%s,name=%s,parent_store_id=%s,store_type=%s,address_line1=%s,address_line2=%s,city=%s,state=%s,postal_code=%s,country=%s,latitude=%s,longitude=%s,timezone=%s,phone=%s,email=%s,active=%s,updated_at=NOW()
               WHERE id=%s RETURNING *""",
            (str(d["store_code"]).strip().upper(),str(d["name"]).strip(),parent_id,str(d.get("store_type","regular")),str(d.get("address_line1","")),str(d.get("address_line2","")),str(d.get("city","")),str(d.get("state","")),str(d.get("postal_code","")),str(d.get("country","US")),d.get("latitude"),d.get("longitude"),str(d.get("timezone","America/Chicago")),str(d.get("phone","")),str(d.get("email","")),bool(d.get("active",True)),store_id),
        ).fetchone()
    record_platform_audit(staff,"store_updated",brand_id=current["brand_id"],store_id=store_id)
    return dict(row)

@app.get("/api/admin/staff/{staff_id}/roles")
def list_staff_roles(staff_id: str, x_session_token: str | None = Header(default=None)):
    actor=require_permission("admin",x_session_token)
    if not DATABASE_URL: return {"assignments":[]}
    with db() as conn:
        target=conn.execute("SELECT * FROM staff_users WHERE id=%s",(staff_id,)).fetchone()
        if not target: raise HTTPException(404,"Staff user not found")
        if not has_role(actor,"super_admin") and target["business_id"]!=actor.get("business_id"):
            raise HTTPException(403,"Cannot manage staff outside your brand")
        rows=conn.execute("SELECT * FROM user_role_assignments WHERE user_id=%s ORDER BY scope_type,role",(staff_id,)).fetchall()
    return {"assignments":[dict(r) for r in rows]}

@app.put("/api/admin/staff/{staff_id}/roles")
def replace_staff_roles(staff_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    actor=require_permission("admin",x_session_token)
    assignments=list(payload.get("assignments") or [])
    allowed_roles={"super_admin","brand_admin","store_manager","counter","processing","driver"}
    if not DATABASE_URL: return {"assignments":assignments}
    with db() as conn:
        target=conn.execute("SELECT * FROM staff_users WHERE id=%s",(staff_id,)).fetchone()
        if not target: raise HTTPException(404,"Staff user not found")
        target_brand=target.get("business_id")
        if not has_role(actor,"super_admin") and target_brand!=actor.get("business_id"):
            raise HTTPException(403,"Cannot manage staff outside your brand")
        for a in assignments:
            role=str(a.get("role",""))
            scope=str(a.get("scope_type",""))
            brand_id=a.get("brand_id") or None
            store_id=a.get("store_id") or None
            if role not in allowed_roles or scope not in ("platform","brand","store"): raise HTTPException(400,"Invalid role assignment")
            if role=="super_admin" and not has_role(actor,"super_admin"): raise HTTPException(403,"Only SuperAdmin can assign SuperAdmin")
            if scope=="platform" and role!="super_admin": raise HTTPException(400,"Only SuperAdmin can use platform scope")
            if not has_role(actor,"super_admin") and brand_id!=actor.get("business_id"): raise HTTPException(403,"Cannot assign another brand")
            if store_id:
                store=conn.execute("SELECT brand_id FROM stores WHERE id=%s",(store_id,)).fetchone()
                if not store or store["brand_id"]!=brand_id: raise HTTPException(400,"Store must belong to assigned brand")
        conn.execute("DELETE FROM user_role_assignments WHERE user_id=%s",(staff_id,))
        saved=[]
        for a in assignments:
            aid=str(uuid.uuid4())
            row=conn.execute(
                "INSERT INTO user_role_assignments (id,user_id,role,scope_type,brand_id,store_id,active) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (aid,staff_id,str(a["role"]),str(a["scope_type"]),a.get("brand_id") or None,a.get("store_id") or None,bool(a.get("active",True))),
            ).fetchone()
            saved.append(dict(row))
    record_platform_audit(actor,"roles_replaced",brand_id=target_brand,metadata={"target_user_id":staff_id,"roles":[x["role"] for x in saved]})
    return {"assignments":saved}

@app.get("/api/admin/staff")
def list_staff(include_inactive: bool = True, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not DATABASE_URL: return {"staff":[]}
    with db() as conn:
        rows = conn.execute("SELECT * FROM staff_users ORDER BY name").fetchall() if include_inactive else conn.execute("SELECT * FROM staff_users WHERE active=TRUE ORDER BY name").fetchall()
    return {"staff":[dict(r) for r in rows]}

@app.post("/api/admin/staff")
def create_staff(payload: dict, x_session_token: str | None = Header(default=None)):
    actor=require_permission("admin",x_session_token)
    name=str(payload.get("name","")).strip(); email=str(payload.get("email","")).strip().lower(); role=str(payload.get("role","counter")).strip().lower(); password=str(payload.get("password",""))
    business_id=str(payload.get("business_id") or actor.get("active_brand_id") or actor.get("business_id") or "fabclean")
    location_id=str(payload.get("location_id") or actor.get("active_store_id") or actor.get("location_id") or "main")
    brand_ids=accessible_brand_ids(actor)
    if brand_ids is not None and business_id not in brand_ids: raise HTTPException(403,"Cannot create staff outside your brand")
    store_ids=accessible_store_ids(actor,business_id)
    if store_ids is not None and location_id not in store_ids: raise HTTPException(403,"Cannot assign an inaccessible store")
    if not name or not email: raise HTTPException(400,"Name and email are required")
    if len(password)<8: raise HTTPException(400,"Password must be at least 8 characters")
    if role not in ("owner","manager","counter","processing","driver"): raise HTTPException(400,"Invalid role")
    sid=str(uuid.uuid4()); salt=secrets.token_hex(16); pw_hash=hash_password(password,salt)
    if not DATABASE_URL: return {"id":sid,"name":name,"email":email,"role":role,"active":bool(payload.get("active",True))}
    with db() as conn:
        try:
            row=conn.execute("INSERT INTO staff_users (id,name,email,role,active,business_id,location_id,password_salt,password_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",(sid,name,email,role,bool(payload.get("active",True)),business_id,location_id,salt,pw_hash)).fetchone()
        except Exception:
            raise HTTPException(409,"A staff user with this email already exists")
    return dict(row)

@app.put("/api/admin/staff/{staff_id}")
def update_staff(staff_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    actor=require_permission("admin",x_session_token)
    role=str(payload.get("role","counter")).strip().lower(); password=str(payload.get("password",""))
    if role not in ("owner","manager","counter","processing","driver"): raise HTTPException(400,"Invalid role")
    if not DATABASE_URL: return {"id":staff_id,**payload}
    with db() as conn:
        current=conn.execute("SELECT * FROM staff_users WHERE id=%s",(staff_id,)).fetchone()
        if not current: raise HTTPException(404,"Staff user not found")
        if not has_role(actor,"super_admin") and current.get("business_id")!=actor.get("business_id"): raise HTTPException(403,"Cannot manage staff outside your brand")
        data=dict(current); data.update(payload)
        if password:
            if len(password)<8: raise HTTPException(400,"Password must be at least 8 characters")
            salt=secrets.token_hex(16); pw_hash=hash_password(password,salt)
            row=conn.execute("UPDATE staff_users SET name=%s,email=%s,role=%s,active=%s,location_id=%s,password_salt=%s,password_hash=%s,updated_at=NOW() WHERE id=%s RETURNING *",(str(data["name"]).strip(),str(data["email"]).strip().lower(),role,bool(data.get("active",True)),str(data.get("location_id","main")),salt,pw_hash,staff_id)).fetchone()
        else:
            row=conn.execute("UPDATE staff_users SET name=%s,email=%s,role=%s,active=%s,location_id=%s,updated_at=NOW() WHERE id=%s RETURNING *",(str(data["name"]).strip(),str(data["email"]).strip().lower(),role,bool(data.get("active",True)),str(data.get("location_id","main")),staff_id)).fetchone()
    return dict(row)

@app.post("/api/auth/bootstrap")
def bootstrap_owner(payload: dict):
    if not DATABASE_URL: return {"staff":{"id":"demo-owner","name":"Demo Owner","email":payload.get("email","demo@example.com"),"role":"owner"}}
    password=str(payload.get("password",""))
    email=str(payload.get("email","")).strip().lower()
    name=str(payload.get("name","Owner")).strip()
    if len(password)<8 or not email: raise HTTPException(400,"Email and password of at least 8 characters are required")
    with db() as conn:
        existing=conn.execute("SELECT 1 FROM staff_users WHERE password_hash IS NOT NULL LIMIT 1").fetchone()
        if existing: raise HTTPException(409,"Owner bootstrap is already complete")
        salt=secrets.token_hex(16); pw_hash=hash_password(password,salt); sid=str(uuid.uuid4())
        row=conn.execute("INSERT INTO staff_users (id,name,email,role,active,business_id,location_id,password_salt,password_hash) VALUES (%s,%s,%s,'owner',TRUE,'fabclean','main',%s,%s) RETURNING *",(sid,name,email,salt,pw_hash)).fetchone()
        conn.execute("INSERT INTO user_role_assignments (id,user_id,role,scope_type,brand_id,store_id,active) VALUES (%s,%s,'super_admin','platform',NULL,NULL,TRUE) ON CONFLICT DO NOTHING",(f"platform-super-{sid}",sid))
        conn.execute("INSERT INTO user_role_assignments (id,user_id,role,scope_type,brand_id,store_id,active) VALUES (%s,%s,'brand_admin','brand','fabclean',NULL,TRUE) ON CONFLICT DO NOTHING",(f"brand-admin-{sid}",sid))
    staff=dict(row); staff["assignments"]=get_user_assignments(sid)
    return {"staff":staff}

@app.post("/api/auth/sign-in")
def staff_sign_in(payload: dict, request: Request):
    email=str(payload.get("email","")).strip().lower(); password=str(payload.get("password",""))
    if not email or not password: raise HTTPException(400,"Email and password are required")
    if not DATABASE_URL: return {"staff":{"id":"demo-owner","name":"Demo Owner","email":email,"role":"owner","active":True},"token":"demo-token"}
    with db() as conn:
        row=conn.execute("SELECT * FROM staff_users WHERE email=%s AND active=TRUE",(email,)).fetchone()
        if not row or not row.get("password_hash") or hash_password(password,row["password_salt"]) != row["password_hash"]:
            raise HTTPException(401,"Invalid email or password")
        token=secrets.token_urlsafe(32)
        conn.execute("INSERT INTO staff_sessions (token,staff_id,active_brand_id,active_store_id) VALUES (%s,%s,%s,%s)",(token,row["id"],row.get("business_id") or "fabclean",row.get("location_id") or "main"))
    staff=dict(row); staff.pop("password_hash",None); staff.pop("password_salt",None); staff["assignments"]=get_user_assignments(staff["id"])
    record_login_audit(staff, request)
    return {"staff":staff,"token":token,"permissions":sorted(effective_permissions(staff))}

@app.post("/api/auth/sign-out")
def staff_sign_out(x_session_token: str | None = Header(default=None)):
    if DATABASE_URL and x_session_token:
        with db() as conn: conn.execute("DELETE FROM staff_sessions WHERE token=%s",(x_session_token,))
    return {"signed_out":True}

@app.get("/api/auth/me")
def auth_me(x_session_token: str | None = Header(default=None)):
    staff=get_current_staff(x_session_token)
    if not staff: raise HTTPException(401,"Staff sign-in required")
    staff=dict(staff); staff.pop("password_hash",None); staff.pop("password_salt",None)
    return {"staff":staff,"permissions":sorted(effective_permissions(staff)),"assignments":staff.get("assignments",[]),"is_super_admin":has_role(staff,"super_admin")}

@app.get("/api/admin/login-audit")
def login_audit_history(limit: int = 100, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    safe_limit=max(1,min(int(limit or 100),500))
    if not DATABASE_URL:
        return {"logins":[]}
    with db() as conn:
        rows=conn.execute(
            "SELECT id,staff_id,staff_name,staff_email,staff_role,ip_address,city,region,country,timezone,user_agent,login_at FROM login_audit ORDER BY login_at DESC LIMIT %s",
            (safe_limit,),
        ).fetchall()
    return {"logins":[dict(r) for r in rows]}

@app.get("/api/subscriptions/plans")
def list_subscription_plans(include_inactive: bool = False, x_session_token: str | None = Header(default=None)):
    if include_inactive: require_permission("admin",x_session_token)
    elif not capability_enabled("subscriptions_enabled", True): return {"plans":[],"enabled":False}
    if not DATABASE_URL: return {"plans":[]}
    with db() as conn:
        rows=conn.execute("SELECT * FROM subscription_plans ORDER BY name").fetchall() if include_inactive else conn.execute("SELECT * FROM subscription_plans WHERE active=TRUE ORDER BY name").fetchall()
    return {"plans":[{**dict(r),"eligible_service_ids":list(r.get("eligible_service_ids") or [])} for r in rows]}

@app.post("/api/subscriptions/plans")
def create_subscription_plan(payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    frequency=str(payload.get("frequency","weekly"))
    if frequency not in ("weekly","biweekly","monthly"): raise HTTPException(400,"Invalid frequency")
    pid=str(uuid.uuid4())
    if not DATABASE_URL: return {"id":pid,**payload}
    with db() as conn:
        row=conn.execute("INSERT INTO subscription_plans (id,name,description,frequency,discount_percent,minimum_order,eligible_service_ids,active) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *",(pid,str(payload.get("name","")).strip(),str(payload.get("description","")),frequency,float(payload.get("discount_percent",0) or 0),float(payload.get("minimum_order",0) or 0),json.dumps(list(payload.get("eligible_service_ids") or [])),bool(payload.get("active",True)))).fetchone()
    out=dict(row); out["eligible_service_ids"]=list(out.get("eligible_service_ids") or []); return out

@app.get("/api/customers/{customer_id}/subscriptions")
def customer_subscriptions(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not capability_enabled("subscriptions_enabled", True): return {"subscriptions":[],"enabled":False}
    if not DATABASE_URL: return {"subscriptions":[],"enabled":True}
    with db() as conn:
        rows=conn.execute("SELECT cs.*, sp.name AS plan_name, sp.frequency, sp.discount_percent FROM customer_subscriptions cs JOIN subscription_plans sp ON sp.id=cs.plan_id WHERE cs.customer_id=%s ORDER BY cs.created_at DESC",(customer_id,)).fetchall()
    return {"subscriptions":[dict(r) for r in rows]}

@app.post("/api/customers/{customer_id}/subscriptions")
def create_customer_subscription(customer_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("customers",x_session_token)
    require_capability("subscriptions_enabled", "Subscriptions")
    sid=str(uuid.uuid4()); start=str(payload.get("start_date") or datetime.now(timezone.utc).date().isoformat())
    if not DATABASE_URL: return {"id":sid,"customer_id":customer_id,**payload,"status":"active","start_date":start}
    with db() as conn:
        plan=conn.execute("SELECT * FROM subscription_plans WHERE id=%s AND active=TRUE",(payload.get("plan_id"),)).fetchone()
        if not plan: raise HTTPException(400,"Subscription plan is not available")
        row=conn.execute("INSERT INTO customer_subscriptions (id,customer_id,plan_id,status,start_date,next_pickup_date,service_area_id,scheduled_slot_id,service_address,service_postal_code) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",(sid,customer_id,payload.get("plan_id"),"active",start,payload.get("next_pickup_date") or start,payload.get("service_area_id"),payload.get("scheduled_slot_id"),str(payload.get("service_address","")),str(payload.get("service_postal_code","")))).fetchone()
    return dict(row)

@app.put("/api/subscriptions/{subscription_id}")
def update_customer_subscription(subscription_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    require_capability("subscriptions_enabled", "Subscriptions")
    if not DATABASE_URL: return {"id":subscription_id,**payload}
    with db() as conn:
        current=conn.execute("SELECT * FROM customer_subscriptions WHERE id=%s",(subscription_id,)).fetchone()
        if not current: raise HTTPException(404,"Subscription not found")
        data=dict(current); data.update(payload)
        row=conn.execute("UPDATE customer_subscriptions SET status=%s,next_pickup_date=%s,service_area_id=%s,scheduled_slot_id=%s,service_address=%s,service_postal_code=%s,updated_at=NOW() WHERE id=%s RETURNING *",(data.get("status","active"),data.get("next_pickup_date"),data.get("service_area_id"),data.get("scheduled_slot_id"),data.get("service_address",""),data.get("service_postal_code",""),subscription_id)).fetchone()
    return dict(row)

@app.get("/api/subscriptions/upcoming")
def upcoming_subscriptions(days: int = 7, x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    if not capability_enabled("subscriptions_enabled", True): return {"upcoming":[],"enabled":False}
    if not DATABASE_URL: return {"upcoming":[]}
    with db() as conn:
        rows=conn.execute("SELECT cs.*, c.name AS customer_name, c.phone, sp.name AS plan_name, sp.frequency FROM customer_subscriptions cs JOIN customers c ON c.id=cs.customer_id JOIN subscription_plans sp ON sp.id=cs.plan_id WHERE cs.status='active' AND cs.next_pickup_date BETWEEN CURRENT_DATE AND CURRENT_DATE + %s ORDER BY cs.next_pickup_date",(days,)).fetchall()
    return {"upcoming":[dict(r) for r in rows]}

def next_subscription_date(current_date: str, frequency: str):
    base=datetime.fromisoformat(str(current_date)).date()
    days={"weekly":7,"biweekly":14,"monthly":30}.get(frequency,7)
    return (base+timedelta(days=days)).isoformat()

@app.post("/api/subscriptions/{subscription_id}/generate-order")
def generate_subscription_order(subscription_id: str, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    require_capability("subscriptions_enabled", "Subscriptions")
    if not DATABASE_URL: raise HTTPException(400,"Recurring order generation requires database mode")
    with db() as conn:
        sub=conn.execute("SELECT cs.*, sp.name AS plan_name, sp.frequency, sp.discount_percent, c.name AS customer_name, c.phone AS customer_phone, c.email AS customer_email FROM customer_subscriptions cs JOIN subscription_plans sp ON sp.id=cs.plan_id JOIN customers c ON c.id=cs.customer_id WHERE cs.id=%s",(subscription_id,)).fetchone()
        if not sub: raise HTTPException(404,"Subscription not found")
        if sub["status"]!="active": raise HTTPException(400,"Subscription is not active")
        pickup_date=str(sub["next_pickup_date"] or "")
        if not pickup_date: raise HTTPException(400,"Next pickup date is not set")
        existing=conn.execute("SELECT order_id FROM recurring_order_runs WHERE subscription_id=%s AND pickup_date=%s::date",(subscription_id,pickup_date)).fetchone()
        if existing: return {"created":False,"order_id":existing["order_id"],"reason":"already_generated"}
    customer_orders=[o for o in get_order_values() if o.get("customer",{}).get("id")==sub["customer_id"] and o.get("items")]
    customer_orders.sort(key=lambda o:o.get("created_at",""),reverse=True)
    if not customer_orders: raise HTTPException(400,"Customer needs at least one previous itemized order before recurring generation")
    template=customer_orders[0]
    discount_percent=float(sub.get("discount_percent",0) or 0)
    template_subtotal=sum(float(i.get("unit_price",0) or 0)*float(i.get("quantity",0) or 0) for i in template.get("items",[]))
    discount=round(template_subtotal*discount_percent/100,2)
    has_schedule=bool(sub.get("service_area_id") and sub.get("scheduled_slot_id") and str(sub.get("service_address","")).strip() and str(sub.get("service_postal_code","")).strip())
    payload=OrderCreate(
        customer_id=sub["customer_id"],
        customer_name=sub["customer_name"],
        customer_phone=sub["customer_phone"],
        customer_email=sub["customer_email"] or "",
        fulfillment_type="pickup_only" if has_schedule else "walk_in",
        items=template.get("items",[]),
        notes=f"Recurring subscription: {sub['plan_name']}",
        discount=discount,
        payment_status="unpaid",
        pricing_status="estimated",
        service_area_id=sub.get("service_area_id") if has_schedule else None,
        pickup_date=pickup_date if has_schedule else "",
        pickup_slot_id=sub.get("scheduled_slot_id") if has_schedule else None,
        scheduled_slot_id=sub.get("scheduled_slot_id") if has_schedule else None,
        service_address=sub.get("service_address","") if has_schedule else "",
        service_postal_code=sub.get("service_postal_code","") if has_schedule else "",
    )
    order=create_order(payload,x_session_token)
    order_data=order.model_dump(mode="json") if hasattr(order,"model_dump") else dict(order)
    next_date=next_subscription_date(pickup_date,sub["frequency"])
    with db() as conn:
        conn.execute("INSERT INTO recurring_order_runs (id,subscription_id,pickup_date,order_id) VALUES (%s,%s,%s::date,%s)",(str(uuid.uuid4()),subscription_id,pickup_date,order_data["id"]))
        conn.execute("UPDATE customer_subscriptions SET next_pickup_date=%s::date,updated_at=NOW() WHERE id=%s",(next_date,subscription_id))
    return {"created":True,"order":order_data,"next_pickup_date":next_date}

@app.get("/api/notifications/provider-status")
def notification_provider_status(x_session_token: str | None = Header(default=None)):
    require_permission("admin",x_session_token)
    return {
        "sms_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER),
        "email_configured": bool(SENDGRID_API_KEY and SENDGRID_FROM_EMAIL),
        "sms_provider": "Twilio",
        "email_provider": "Twilio SendGrid",
        "automatic_stages": ["order_received","ready_for_pickup"],
    }

CRITICAL_NOTIFICATION_TEMPLATES = {
    "order_received": {
        "subject": "FabClean order received",
        "message": "Hi {name}, we received your FabClean order {order_number}. We’ll let you know when it is ready for pickup."
    },
    "ready_for_pickup": {
        "subject": "Your FabClean order is ready",
        "message": "Hi {name}, your FabClean order {order_number} is ready for pickup."
    },
}

def notification_already_sent(order_id: str, notification_type: str, channel: str):
    if not DATABASE_URL: return False
    with db() as conn:
        row=conn.execute("SELECT 1 FROM customer_notifications WHERE order_id=%s AND notification_type=%s AND channel=%s AND status='sent' LIMIT 1",(order_id,notification_type,channel)).fetchone()
    return bool(row)

def log_customer_message(order: dict, notification_type: str, channel: str, message: str, status: str, staff: dict | None = None, provider_message_id: str = "", error_message: str = ""):
    if not DATABASE_URL: return
    customer=order.get("customer") or {}
    with db() as conn:
        conn.execute("INSERT INTO customer_notifications (id,customer_id,order_id,notification_type,channel,message,status,staff_id,staff_name,provider_message_id,error_message,sent_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s='sent' THEN NOW() ELSE NULL END)",
            (str(uuid.uuid4()),customer.get("id"),order.get("id"),notification_type,channel,message,status,(staff or {}).get("id"),(staff or {}).get("name",""),provider_message_id,error_message,status))

def send_critical_order_notifications(order: dict, notification_type: str, staff: dict | None = None):
    template=CRITICAL_NOTIFICATION_TEMPLATES.get(notification_type)
    if not template: return
    customer=order.get("customer") or {}
    name=customer.get("name") or "Customer"
    order_number=order.get("order_number") or ""
    message=template["message"].format(name=name,order_number=order_number)
    subject=template["subject"]

    email=(customer.get("email") or "").strip()
    if email and SENDGRID_API_KEY and SENDGRID_FROM_EMAIL and not notification_already_sent(order.get("id"),notification_type,"email"):
        try:
            mail=Mail(from_email=SENDGRID_FROM_EMAIL,to_emails=email,subject=subject,plain_text_content=message)
            response=SendGridAPIClient(SENDGRID_API_KEY).send(mail)
            if 200 <= int(response.status_code) < 300:
                log_customer_message(order,notification_type,"email",message,"sent",staff,str(response.headers.get("X-Message-Id","")))
            else:
                log_customer_message(order,notification_type,"email",message,"failed",staff,"",f"SendGrid status {response.status_code}")
        except Exception as exc:
            log_customer_message(order,notification_type,"email",message,"failed",staff,"",str(exc)[:300])

    phone=(customer.get("phone") or "").strip()
    if phone and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER and not notification_already_sent(order.get("id"),notification_type,"sms"):
        if not phone.startswith("+"):
            log_customer_message(order,notification_type,"sms",message,"failed",staff,"","Phone must be in E.164 format, for example +12244334497")
        else:
            try:
                sms=TwilioClient(TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN).messages.create(body=message,from_=TWILIO_FROM_NUMBER,to=phone)
                log_customer_message(order,notification_type,"sms",message,"sent",staff,str(sms.sid or ""))
            except Exception as exc:
                log_customer_message(order,notification_type,"sms",message,"failed",staff,"",str(exc)[:300])

NOTIFICATION_TEMPLATES = {
    "pickup_reminder":"Hi {name}, this is a reminder about your upcoming FabClean pickup.",
    "order_received":"Hi {name}, we received your FabClean order {order_number}.",
    "ready_for_pickup":"Hi {name}, your FabClean order {order_number} is ready for pickup.",
    "delivery_scheduled":"Hi {name}, your FabClean delivery is scheduled.",
    "payment_due":"Hi {name}, a balance is due on FabClean order {order_number}.",
}

@app.post("/api/notifications/prepare")
def prepare_notification(payload: dict, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    kind=str(payload.get("notification_type","order_received"))
    if kind not in NOTIFICATION_TEMPLATES: raise HTTPException(400,"Unsupported notification type")
    customer_id=payload.get("customer_id"); order_id=payload.get("order_id"); subscription_id=payload.get("subscription_id")
    name=str(payload.get("customer_name","Customer")); order_number=str(payload.get("order_number",""))
    default=NOTIFICATION_TEMPLATES[kind].format(name=name,order_number=order_number)
    message=str(payload.get("message") or default)
    nid=str(uuid.uuid4())
    if DATABASE_URL:
        with db() as conn:
            row=conn.execute("INSERT INTO customer_notifications (id,customer_id,order_id,subscription_id,notification_type,channel,message,status,staff_id,staff_name) VALUES (%s,%s,%s,%s,%s,%s,%s,'prepared',%s,%s) RETURNING *",(nid,customer_id,order_id,subscription_id,kind,str(payload.get("channel","manual")),message,staff.get("id"),staff.get("name",""))).fetchone()
        return dict(row)
    return {"id":nid,"notification_type":kind,"message":message,"status":"prepared"}

@app.get("/api/customers/{customer_id}/notifications")
def customer_notifications(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_permission("customers",x_session_token)
    if not DATABASE_URL: return {"notifications":[]}
    with db() as conn:
        rows=conn.execute("SELECT * FROM customer_notifications WHERE customer_id=%s ORDER BY created_at DESC",(customer_id,)).fetchall()
    return {"notifications":[dict(r) for r in rows]}

@app.post("/api/notifications/{notification_id}/resend")
def resend_notification(notification_id: str, x_session_token: str | None = Header(default=None)):
    staff=require_permission("orders",x_session_token)
    if not DATABASE_URL: raise HTTPException(400,"Notification history requires database mode")
    with db() as conn:
        current=conn.execute("SELECT * FROM customer_notifications WHERE id=%s",(notification_id,)).fetchone()
        if not current: raise HTTPException(404,"Notification not found")
        nid=str(uuid.uuid4())
        row=conn.execute("INSERT INTO customer_notifications (id,customer_id,order_id,subscription_id,notification_type,channel,message,status,staff_id,staff_name) VALUES (%s,%s,%s,%s,%s,%s,%s,'prepared',%s,%s) RETURNING *",(nid,current["customer_id"],current["order_id"],current["subscription_id"],current["notification_type"],current["channel"],current["message"],staff.get("id"),staff.get("name",""))).fetchone()
    return dict(row)

def log_ai_assistance(staff_id: str | None, assistance_type: str, entity_type: str, entity_id: str, metadata: dict | None = None):
    if not DATABASE_URL: return
    with db() as conn:
        conn.execute("INSERT INTO ai_assistance_log (id,staff_id,assistance_type,entity_type,entity_id,metadata) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",(str(uuid.uuid4()),staff_id,assistance_type,entity_type,entity_id,json.dumps(metadata or {})))

def openai_assist(instructions: str, input_text: str):
    if not OPENAI_API_KEY:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role":"system","content":instructions},
                {"role":"user","content":input_text},
            ],
        )
        return (response.output_text or "").strip()
    except Exception:
        return None

@app.get("/api/ai/status")
def ai_status(x_session_token: str | None = Header(default=None)):
    require_permission("orders", x_session_token)
    return {
        "enabled": ai_enabled(),
        "provider": "openai" if OPENAI_API_KEY else "demo",
        "model": OPENAI_MODEL if OPENAI_API_KEY else "built_in",
    }

def ai_enabled():
    return bool(get_settings_value().get("ai_assistance_enabled", True))

def require_ai(permission: str, x_session_token: str | None):
    staff = require_permission(permission, x_session_token)
    if not ai_enabled(): raise HTTPException(403, "AI assistance is disabled")
    return staff

@app.get("/api/ai/customers/{customer_id}/summary")
def ai_customer_summary(customer_id: str, x_session_token: str | None = Header(default=None)):
    require_ai("customers", x_session_token)
    customer = get_customer(customer_id, x_session_token)
    orders = [o for o in get_order_values() if o.get("customer",{}).get("id")==customer_id]
    orders.sort(key=lambda o: o.get("created_at",""), reverse=True)
    total = round(sum(float(o.get("total",0) or 0) for o in orders),2)
    service_counts = {}
    for order in orders:
        for item in order.get("items",[]):
            name=item.get("service_name","Service"); service_counts[name]=service_counts.get(name,0)+float(item.get("quantity",0) or 0)
    top_services = [x[0] for x in sorted(service_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    open_count = len([o for o in orders if o.get("status") not in ("completed","collected")])
    recent = orders[:3]
    parts = [f"{customer.get('name')} has {len(orders)} order(s) with lifetime value ${total:.2f}."]
    if top_services: parts.append("Most used services: " + ", ".join(top_services) + ".")
    if open_count: parts.append(f"{open_count} order(s) are still open.")
    if recent:
        last=recent[0]; parts.append(f"Most recent order {last.get('order_number','')} is {last.get('status','unknown')}.")
    if customer.get("notes"): parts.append("Customer note: " + str(customer.get("notes"))[:180])
    built_in = " ".join(parts)
    prompt = json.dumps({
        "customer": customer,
        "recent_orders": orders[:8],
        "top_services": top_services,
        "lifetime_value": total,
    }, default=str)
    generated = openai_assist(
        "You are a laundry operations assistant. Summarize this customer history in 3 concise operational sentences. Do not invent facts. Mention useful preferences or recurring patterns only when supported.",
        prompt,
    )
    result={"mode":"openai" if generated else "built_in","summary":generated or built_in,"top_services":top_services,"order_count":len(orders),"lifetime_value":total}
    staff=get_current_staff(x_session_token); log_ai_assistance(staff.get("id") if staff else None,"customer_summary","customer",customer_id,{"order_count":len(orders)})
    return result

@app.post("/api/ai/orders/{order_id}/inspection-suggest")
def ai_inspection_suggest(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_ai("processing", x_session_token)
    text = (str(payload.get("notes","")) + " " + str(payload.get("service_name",""))).lower()
    tags=[]
    rules=[("stain","stain"),("tear","tear"),("rip","tear"),("button","missing button"),("loose","loose stitching"),("damage","existing damage"),("silk","delicate material"),("wool","delicate material"),("fade","color fading risk")]
    for needle,tag in rules:
        if needle in text and tag not in tags: tags.append(tag)
    suggestions=[]
    if "stain" in tags: suggestions.append("Confirm stain location and treatment preference before cleaning.")
    if "delicate material" in tags: suggestions.append("Use delicate handling and verify service compatibility.")
    if "existing damage" in tags or "tear" in tags: suggestions.append("Document pre-existing damage before processing.")
    if not suggestions: suggestions.append("No obvious risk keywords detected; staff inspection is still required.")
    staff=get_current_staff(x_session_token); log_ai_assistance(staff.get("id") if staff else None,"inspection_suggestion","order",order_id,{"suggested_tags":tags})
    return {"mode":"built_in","suggested_tags":tags,"handling_suggestions":suggestions,"requires_staff_confirmation":True}

@app.get("/api/ai/orders/{order_id}/risks")
def ai_order_risks(order_id: str, x_session_token: str | None = Header(default=None)):
    require_ai("orders", x_session_token)
    order = get_order(order_id, x_session_token)
    risks=[]
    due=order.get("due_at") if isinstance(order,dict) else getattr(order,"due_at",None)
    status=order.get("status") if isinstance(order,dict) else getattr(order,"status","")
    discount=float(order.get("discount",0) if isinstance(order,dict) else getattr(order,"discount",0) or 0)
    subtotal=float(order.get("subtotal",0) if isinstance(order,dict) else getattr(order,"subtotal",0) or 0)
    if due:
        try:
            dt=datetime.fromisoformat(str(due).replace("Z","+00:00")); now=datetime.now(timezone.utc)
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            hours=(dt-now).total_seconds()/3600
            if hours<0 and status not in ("completed","collected"): risks.append({"severity":"high","type":"overdue","message":"Order is past its due time."})
            elif hours<=24 and status not in ("ready_for_pickup","completed","collected"): risks.append({"severity":"medium","type":"due_soon","message":"Order is due within 24 hours."})
        except Exception: pass
    if subtotal>0 and discount/subtotal>=0.25: risks.append({"severity":"medium","type":"high_discount","message":"Discount is 25% or more of subtotal."})
    events=get_order_events(order_id)
    if len([e for e in events if e.get("event_type")=="inspection_updated"])>=3: risks.append({"severity":"low","type":"repeat_inspection","message":"This order has multiple inspection updates; review condition notes."})
    staff=get_current_staff(x_session_token); log_ai_assistance(staff.get("id") if staff else None,"order_risk_review","order",order_id,{"risk_count":len(risks)})
    return {"mode":"built_in","risks":risks,"risk_count":len(risks),"requires_staff_review":True}

@app.post("/api/ai/orders/{order_id}/communication-draft")
def ai_communication_draft(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
    require_ai("orders", x_session_token)
    order=get_order(order_id, x_session_token)
    customer=order.get("customer",{}) if isinstance(order,dict) else order.customer.model_dump()
    name=customer.get("name","Customer"); order_number=order.get("order_number") if isinstance(order,dict) else order.order_number
    kind=str(payload.get("kind","ready")).lower()
    if kind=="delay": body=f"Hi {name}, your FabClean order {order_number} needs a little more time so we can complete it properly. We’ll update you as soon as it is ready. Thank you for your patience."
    elif kind=="subscription": body=f"Hi {name}, this is a reminder about your upcoming FabClean recurring pickup. Please contact us if you need to pause or change the pickup."
    elif kind=="winback": body=f"Hi {name}, we’d be happy to help with your next laundry or garment-care order. Your FabClean account is ready whenever you need us."
    else: body=f"Hi {name}, your FabClean order {order_number} is ready for pickup. Thank you for choosing FabClean."
    staff=get_current_staff(x_session_token); log_ai_assistance(staff.get("id") if staff else None,"communication_draft","order",order_id,{"kind":kind})
    generated = openai_assist(
        "Draft a short professional customer message for a laundry business. Preserve all order/customer facts supplied. Do not promise anything not stated. Return only the message text.",
        json.dumps({"kind":kind,"customer_name":name,"order_number":order_number,"fallback":body}),
    )
    return {"mode":"openai" if generated else "built_in","kind":kind,"draft":generated or body,"requires_staff_approval":True}

@app.get("/api/dashboard")
def dashboard(x_session_token: str | None = Header(default=None)):
    require_permission("orders",x_session_token)
    if DATABASE_URL:
        with db() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*)::int AS total_orders,
                    COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE)::int AS orders_today,
                    COUNT(*) FILTER (WHERE payload->>'fulfillment_type' = 'walk_in')::int AS walk_in_orders,
                    COUNT(*) FILTER (WHERE COALESCE(payload->>'fulfillment_type','walk_in') <> 'walk_in')::int AS pickup_delivery_orders,
                    COUNT(*) FILTER (WHERE payload->>'status' = 'ready_for_pickup')::int AS ready_for_pickup,
                    COUNT(*) FILTER (WHERE payload->>'status' IN ('inspection','cleaning','quality_check'))::int AS processing,
                    COUNT(*) FILTER (WHERE payload->>'payment_status' IN ('unpaid','partial'))::int AS payment_pending,
                    COALESCE(SUM(CASE WHEN payload->>'payment_status'='paid' THEN NULLIF(payload->>'total','')::numeric ELSE 0 END),0) AS revenue,
                    COALESCE(AVG(CASE WHEN payload->>'payment_status'='paid' THEN NULLIF(payload->>'total','')::numeric END),0) AS average_order_value
                FROM orders
            """).fetchone()
        d=dict(row)
        return {
            "orders_today": int(d.get("orders_today") or 0),
            "total_orders": int(d.get("total_orders") or 0),
            "walk_in_orders": int(d.get("walk_in_orders") or 0),
            "pickup_delivery_orders": int(d.get("pickup_delivery_orders") or 0),
            "ready_for_pickup": int(d.get("ready_for_pickup") or 0),
            "processing": int(d.get("processing") or 0),
            "payment_pending": int(d.get("payment_pending") or 0),
            "revenue": round(float(d.get("revenue") or 0),2),
            "average_order_value": round(float(d.get("average_order_value") or 0),2),
            "database": "postgres",
        }

    values = get_order_values()
    today = datetime.now(timezone.utc).date().isoformat()
    today_values = [o for o in values if str(o.get("created_at",""))[:10] == today]
    paid = [o for o in values if o.get("payment_status") == "paid"]
    unpaid = [o for o in values if o.get("payment_status") in ("unpaid","partial")]
    pickup_delivery = [o for o in values if o.get("fulfillment_type") != "walk_in"]
    return {
        "orders_today": len(today_values),
        "total_orders": len(values),
        "walk_in_orders": len([o for o in values if o.get("fulfillment_type") == "walk_in"]),
        "pickup_delivery_orders": len(pickup_delivery),
        "ready_for_pickup": len([o for o in values if o.get("status") == "ready_for_pickup"]),
        "processing": len([o for o in values if o.get("status") in ("inspection", "cleaning", "quality_check")]),
        "payment_pending": len(unpaid),
        "revenue": round(sum(float(o.get("total", 0)) for o in paid), 2),
        "average_order_value": round(sum(float(o.get("total",0)) for o in paid)/len(paid),2) if paid else 0,
        "database": "memory",
    }
