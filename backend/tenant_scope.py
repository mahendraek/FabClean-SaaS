"""Request scope and PostgreSQL isolation, including table-owner connections.

Authentication/platform tables intentionally stay outside operational RLS.
Only schema initialization may open a maintenance connection. HTTP handlers
never accept scope or maintenance settings from request payloads.
"""
from collections.abc import MutableMapping
from contextvars import ContextVar
from copy import deepcopy

from psycopg import sql

current_scope = ContextVar("fabclean_scope", default=None)
SCHEMA_VERSION = "tenant-isolation-v1"
OWNED_TABLES = (
    "app_settings", "services", "service_categories", "customers", "orders",
    "payment_transactions", "order_events", "order_item_inspections",
    "order_garments", "order_photos", "offers", "reward_transactions",
    "referrals", "service_areas", "delivery_slots", "delivery_blackouts",
    "subscription_plans", "customer_subscriptions", "recurring_order_runs",
    "customer_notifications", "ai_assistance_log",
)


class ScopedMemoryDict(MutableMapping):
    """Isolated demo catalogs/settings. Non-default stores start empty."""
    def __init__(self, initial=None, defaults=None):
        self.buckets = {("fabclean", "main"): deepcopy(initial or {})}
        self.defaults = defaults or {}

    def bucket(self):
        scope = current_scope.get()
        if scope is None:
            # Only local initialization/tests use this path; HTTP middleware
            # requires a real session and scope for all operational routes.
            scope = ("fabclean", "main")
        return self.buckets.setdefault(scope, deepcopy(self.defaults))

    def __getitem__(self, key): return self.bucket()[key]
    def __setitem__(self, key, value): self.bucket()[key] = value
    def __delitem__(self, key): del self.bucket()[key]
    def __iter__(self): return iter(self.bucket())
    def __len__(self): return len(self.bucket())
    def copy(self): return self.bucket().copy()


def configure_connection(conn, maintenance=False):
    role = conn.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
    ).fetchone()
    if role["rolsuper"] or role["rolbypassrls"]:
        raise RuntimeError("DATABASE_URL must use a NOSUPERUSER NOBYPASSRLS role; RLS bypass roles are unsafe")
    brand, store = current_scope.get() or ("", "")
    conn.execute(
        "SELECT set_config('app.brand_id',%s,false), set_config('app.store_id',%s,false), set_config('app.maintenance',%s,false)",
        (brand, store, "on" if maintenance else "off"),
    )


def migration_installed(conn):
    exists = conn.execute("SELECT to_regclass('fabclean_schema_migrations') AS name").fetchone()
    return bool(exists["name"] and conn.execute(
        "SELECT 1 FROM fabclean_schema_migrations WHERE version=%s", (SCHEMA_VERSION,)
    ).fetchone())


def install_isolation(conn):
    """Atomic, repeatable upgrade of the original single-store schema.

    Existing explicitly owned orders/customers retain their ownership. Unknown
    order ownership stays NULL (quarantined), never assigned to the caller.
    Original global configuration belongs only to the baseline fabclean/main.
    Child ownership is derived from its authoritative parent, not a caller.
    """
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(471004)")
        if migration_installed(conn):
            return
        for table in OWNED_TABLES:
            ident = sql.Identifier(table)
            for column in ("business_id", "location_id"):
                conn.execute(sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} TEXT").format(ident, sql.Identifier(column)))

        for table in ("orders", "services"):
            conn.execute(sql.SQL(
                "UPDATE {} SET business_id=NULLIF(payload->>'business_id',''), location_id=NULLIF(payload->>'location_id','')"
            ).format(sql.Identifier(table)))
        conn.execute("UPDATE services SET business_id=COALESCE(business_id,'__quarantined__'),location_id=COALESCE(location_id,'__quarantined__')")
        conn.execute("ALTER TABLE login_audit ADD COLUMN IF NOT EXISTS business_id TEXT")
        conn.execute("ALTER TABLE login_audit ADD COLUMN IF NOT EXISTS location_id TEXT")
        conn.execute("UPDATE login_audit l SET business_id=s.business_id,location_id=s.location_id FROM staff_users s WHERE s.id=l.staff_id")
        conn.execute("CREATE INDEX idx_login_audit_tenant_scope ON login_audit (business_id,location_id,login_at)")

        # The legacy configuration tables were single-store by definition.
        for table in ("app_settings", "service_categories", "offers", "service_areas", "delivery_slots", "delivery_blackouts", "subscription_plans"):
            conn.execute(sql.SQL("UPDATE {} SET business_id='fabclean',location_id='main'").format(sql.Identifier(table)))
        # Embedded customer IDs must resolve to an owner in the same store.
        conn.execute("UPDATE orders o SET business_id=NULL,location_id=NULL WHERE NOT EXISTS (SELECT 1 FROM customers c WHERE c.id=o.payload->'customer'->>'id' AND c.business_id=o.business_id AND c.location_id=o.location_id)")

        order_children = ("payment_transactions", "order_events", "order_item_inspections", "order_garments", "order_photos")
        for table in order_children:
            conn.execute(sql.SQL(
                "UPDATE {} child SET business_id=p.business_id,location_id=p.location_id FROM orders p WHERE p.id=child.order_id"
            ).format(sql.Identifier(table)))
        for table, key in (("referrals", "referrer_customer_id"), ("reward_transactions", "customer_id"), ("customer_subscriptions", "customer_id")):
            conn.execute(sql.SQL(
                "UPDATE {} child SET business_id=p.business_id,location_id=p.location_id FROM customers p WHERE p.id=child.{}"
            ).format(sql.Identifier(table), sql.Identifier(key)))
        conn.execute("UPDATE recurring_order_runs child SET business_id=p.business_id,location_id=p.location_id FROM customer_subscriptions p WHERE p.id=child.subscription_id")
        # Unlinked historic notifications/AI logs remain quarantined.
        conn.execute("UPDATE customer_notifications child SET business_id=p.business_id,location_id=p.location_id FROM orders p WHERE p.id=child.order_id")
        conn.execute("UPDATE customer_notifications child SET business_id=p.business_id,location_id=p.location_id FROM customers p WHERE child.order_id IS NULL AND p.id=child.customer_id")
        conn.execute("UPDATE ai_assistance_log child SET business_id=p.business_id,location_id=p.location_id FROM orders p WHERE child.entity_type='order' AND p.id=child.entity_id")
        conn.execute("UPDATE ai_assistance_log child SET business_id=p.business_id,location_id=p.location_id FROM customers p WHERE child.entity_type='customer' AND p.id=child.entity_id")

        # Settings/catalog IDs and operational barcodes are store-local.
        for table in ("app_settings", "services", "service_categories"):
            conn.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(sql.Identifier(table), sql.Identifier(table + "_pkey")))
            conn.execute(sql.SQL("ALTER TABLE {} ADD PRIMARY KEY (business_id,location_id,id)").format(sql.Identifier(table)))
        for table, column in (("service_categories", "name"), ("orders", "order_number"), ("orders", "barcode_value"), ("order_garments", "garment_code"), ("offers", "code")):
            conn.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {}").format(sql.Identifier(table), sql.Identifier(table + "_" + column + "_key")))
            conn.execute(sql.SQL("ALTER TABLE {} ADD UNIQUE (business_id,location_id,{})").format(sql.Identifier(table), sql.Identifier(column)))

        for table in OWNED_TABLES:
            ident = sql.Identifier(table)
            for column, setting in (("business_id", "app.brand_id"), ("location_id", "app.store_id")):
                conn.execute(sql.SQL("ALTER TABLE {} ALTER COLUMN {} SET DEFAULT NULLIF(current_setting({},true),'')").format(ident, sql.Identifier(column), sql.Literal(setting)))
            conn.execute(sql.SQL("CREATE INDEX {} ON {} (business_id,location_id)").format(sql.Identifier("idx_" + table + "_tenant_scope"), ident))
            conn.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(ident))
            conn.execute(sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(ident))
            predicate = "business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),'')"
            if table in ("orders", "services"):
                predicate += " AND payload->>'business_id'=business_id AND payload->>'location_id'=location_id"
            conn.execute(sql.SQL("CREATE POLICY tenant_scope ON {} USING (current_setting('app.maintenance',true)='on' OR ({})) WITH CHECK (current_setting('app.maintenance',true)='on' OR ({}))").format(ident, sql.SQL(predicate), sql.SQL(predicate)))

        # Composite references prevent writing a visible child against a
        # foreign store's ID. NOT VALID preserves quarantined legacy rows;
        # PostgreSQL still enforces these constraints on every new write.
        for parent in ("orders", "customers", "subscription_plans", "customer_subscriptions", "service_areas", "delivery_slots"):
            conn.execute(sql.SQL("ALTER TABLE {} ADD UNIQUE (id,business_id,location_id)").format(sql.Identifier(parent)))
        order_references = {"customer_id": ("customers", "NULLIF(payload->'customer'->>'id','')"), "service_area_id": ("service_areas", "NULLIF(payload->>'service_area_id','')"), "pickup_slot_id": ("delivery_slots", "NULLIF(payload->>'pickup_slot_id','')"), "delivery_slot_id": ("delivery_slots", "NULLIF(payload->>'delivery_slot_id','')"), "scheduled_slot_id": ("delivery_slots", "NULLIF(payload->>'scheduled_slot_id','')")}
        for column, (parent, expression) in order_references.items():
            conn.execute(sql.SQL("ALTER TABLE orders ADD COLUMN {} TEXT GENERATED ALWAYS AS ({}) STORED").format(sql.Identifier("scope_" + column), sql.SQL(expression)))
            conn.execute(sql.SQL("ALTER TABLE orders ADD CONSTRAINT {} FOREIGN KEY ({},business_id,location_id) REFERENCES {} (id,business_id,location_id) NOT VALID").format(sql.Identifier("fk_scope_orders_" + column), sql.Identifier("scope_" + column), sql.Identifier(parent)))
            conn.execute(sql.SQL("UPDATE orders child SET business_id=NULL,location_id=NULL WHERE child.{} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {} parent WHERE parent.id=child.{} AND parent.business_id=child.business_id AND parent.location_id=child.location_id)").format(sql.Identifier("scope_" + column), sql.Identifier(parent), sql.Identifier("scope_" + column)))
        references = [(t, "order_id", "orders") for t in order_children]
        references += [
            ("payment_transactions", "customer_id", "customers"),
            ("reward_transactions", "customer_id", "customers"),
            ("reward_transactions", "order_id", "orders"),
            ("referrals", "referrer_customer_id", "customers"),
            ("referrals", "referred_customer_id", "customers"),
            ("referrals", "qualifying_order_id", "orders"),
            ("customer_subscriptions", "customer_id", "customers"),
            ("customer_subscriptions", "plan_id", "subscription_plans"),
            ("customer_subscriptions", "service_area_id", "service_areas"),
            ("customer_subscriptions", "scheduled_slot_id", "delivery_slots"),
            ("recurring_order_runs", "subscription_id", "customer_subscriptions"),
            ("recurring_order_runs", "order_id", "orders"),
            ("customer_notifications", "customer_id", "customers"),
            ("customer_notifications", "order_id", "orders"),
            ("customer_notifications", "subscription_id", "customer_subscriptions"),
        ]
        for child, key, parent in references:
            conn.execute(sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({},business_id,location_id) REFERENCES {} (id,business_id,location_id) NOT VALID").format(sql.Identifier(child), sql.Identifier("fk_scope_" + child + "_" + key), sql.Identifier(key), sql.Identifier(parent)))
            conn.execute(sql.SQL("UPDATE {} child SET business_id=NULL,location_id=NULL WHERE child.{} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {} parent WHERE parent.id=child.{} AND parent.business_id=child.business_id AND parent.location_id=child.location_id)").format(sql.Identifier(child), sql.Identifier(key), sql.Identifier(parent), sql.Identifier(key)))
        conn.execute("CREATE TABLE IF NOT EXISTS fabclean_schema_migrations (version TEXT PRIMARY KEY,installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        conn.execute("INSERT INTO fabclean_schema_migrations (version) VALUES (%s)", (SCHEMA_VERSION,))
