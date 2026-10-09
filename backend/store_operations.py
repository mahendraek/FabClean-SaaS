"""Same-brand store hierarchy and explicit custody handoffs.

Handoffs share only a work manifest between their two stores. Order/customer/
payment ownership stays at the originating store. No maintenance connection is
used by the HTTP workflow.
"""
VERSION = "store-operations-v1"
STORE_TYPES = {"regular", "mother_store", "central_plant", "dropoff"}
TRANSITIONS = {
    "receive": ("dispatched", "received", "destination_store_id"),
    "return": ("received", "returning", "destination_store_id"),
    "complete": ("returning", "completed", "source_store_id"),
    "cancel": ("dispatched", "cancelled", "source_store_id"),
}


def validate_hierarchy(stores, store_id, parent_id):
    """Validate the entire ancestor path, including historical bad graphs."""
    if not parent_id:
        return
    seen = {store_id}
    while parent_id:
        if parent_id in seen:
            raise ValueError("A store cannot be its own ancestor")
        seen.add(parent_id)
        parent = stores.get(parent_id)
        if not parent or not parent["active"]:
            raise ValueError("Parent must be an active store in the same brand")
        parent_id = parent.get("parent_store_id")


def next_handoff_status(handoff, action, store_id):
    if action not in TRANSITIONS:
        raise ValueError("Unknown handoff action")
    before, after, side = TRANSITIONS[action]
    if handoff[side] != store_id:
        raise PermissionError("This action belongs to the other store")
    if handoff["status"] != before:
        raise RuntimeError("Handoff changed or action is no longer available; refresh")
    return after


def work_manifest(order):
    # Deliberate allowlist: no customer contacts, totals, payments, order notes,
    # photos, or internal service IDs from another store's catalog.
    return [{"service_name": item.get("service_name", ""),
             "quantity": item.get("quantity", 0), "unit_label": item.get("unit_label", "item"),
             "barcode_value": item.get("barcode_value")}
            for item in order.get("items", [])]


def install_store_operations(conn):
    if conn.execute("SELECT 1 FROM fabclean_schema_migrations WHERE version=%s", (VERSION,)).fetchone():
        return
    conn.execute("ALTER TABLE stores ADD COLUMN open_handoff_count INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE stores ADD CONSTRAINT stores_handoff_count_nonnegative CHECK (open_handoff_count>=0)")
    conn.execute("ALTER TABLE stores ADD CONSTRAINT stores_active_handoffs CHECK (active OR open_handoff_count=0)")
    conn.execute("ALTER TABLE stores ADD CONSTRAINT stores_id_brand_unique UNIQUE (id,brand_id)")
    conn.execute("ALTER TABLE stores ADD CONSTRAINT stores_parent_brand FOREIGN KEY (parent_store_id,brand_id) REFERENCES stores(id,brand_id) NOT VALID")
    conn.execute("ALTER TABLE stores ADD CONSTRAINT stores_not_own_parent CHECK (parent_store_id IS NULL OR parent_store_id<>id) NOT VALID")
    conn.execute("ALTER TABLE stores ADD CONSTRAINT stores_valid_type CHECK (store_type IN ('regular','mother_store','central_plant','dropoff')) NOT VALID")
    conn.execute("""
        CREATE TABLE store_handoffs (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source_store_id TEXT NOT NULL,
            destination_store_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            order_number TEXT NOT NULL,
            source_name TEXT NOT NULL,
            destination_name TEXT NOT NULL,
            manifest JSONB NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('dispatched','received','returning','completed','cancelled')),
            events JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK (source_store_id<>destination_store_id),
            FOREIGN KEY (source_store_id,business_id) REFERENCES stores(id,brand_id),
            FOREIGN KEY (destination_store_id,business_id) REFERENCES stores(id,brand_id),
            FOREIGN KEY (order_id,business_id,source_store_id) REFERENCES orders(id,business_id,location_id)
        )
    """)
    conn.execute("CREATE UNIQUE INDEX store_handoffs_one_open_order ON store_handoffs (business_id,order_id) WHERE status IN ('dispatched','received','returning')")
    conn.execute("CREATE INDEX store_handoffs_source ON store_handoffs(business_id,source_store_id,created_at)")
    conn.execute("CREATE INDEX store_handoffs_destination ON store_handoffs(business_id,destination_store_id,created_at)")
    conn.execute("ALTER TABLE store_handoffs ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE store_handoffs FORCE ROW LEVEL SECURITY")
    shared = "business_id=NULLIF(current_setting('app.brand_id',true),'') AND NULLIF(current_setting('app.store_id',true),'') IN (source_store_id,destination_store_id)"
    source = "business_id=NULLIF(current_setting('app.brand_id',true),'') AND source_store_id=NULLIF(current_setting('app.store_id',true),'')"
    conn.execute(f"CREATE POLICY handoff_read ON store_handoffs FOR SELECT USING ({shared})")
    conn.execute(f"CREATE POLICY handoff_create ON store_handoffs FOR INSERT WITH CHECK ({source} AND status='dispatched')")
    conn.execute(f"CREATE POLICY handoff_update ON store_handoffs FOR UPDATE USING ({shared}) WITH CHECK ({shared})")
    # No DELETE policy. Identity/manifest are immutable, and custody transitions
    # are validated even for direct SQL using the application database role.
    conn.execute("""
        CREATE FUNCTION guard_store_handoff() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.id,NEW.business_id,NEW.source_store_id,NEW.destination_store_id,NEW.order_id,NEW.order_number,NEW.source_name,NEW.destination_name,NEW.manifest,NEW.created_at)
               IS DISTINCT FROM ROW(OLD.id,OLD.business_id,OLD.source_store_id,OLD.destination_store_id,OLD.order_id,OLD.order_number,OLD.source_name,OLD.destination_name,OLD.manifest,OLD.created_at) THEN
                RAISE EXCEPTION 'Handoff identity and manifest are immutable' USING ERRCODE='23514';
            END IF;
            IF NOT (
                (OLD.status='dispatched' AND NEW.status='received' AND current_setting('app.store_id',true)=OLD.destination_store_id) OR
                (OLD.status='received' AND NEW.status='returning' AND current_setting('app.store_id',true)=OLD.destination_store_id) OR
                (OLD.status='returning' AND NEW.status='completed' AND current_setting('app.store_id',true)=OLD.source_store_id) OR
                (OLD.status='dispatched' AND NEW.status='cancelled' AND current_setting('app.store_id',true)=OLD.source_store_id)
            ) THEN
                RAISE EXCEPTION 'Invalid custody transition' USING ERRCODE='23514';
            END IF;
            IF jsonb_array_length(NEW.events)<>jsonb_array_length(OLD.events)+1 OR NEW.events - (jsonb_array_length(NEW.events)-1) <> OLD.events THEN
                RAISE EXCEPTION 'Custody history must be append only' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    conn.execute("CREATE TRIGGER store_handoff_guard BEFORE UPDATE ON store_handoffs FOR EACH ROW EXECUTE FUNCTION guard_store_handoff()")
    conn.execute("""
        CREATE FUNCTION count_store_handoff() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='INSERT' THEN
                UPDATE stores SET open_handoff_count=open_handoff_count+1 WHERE id IN (NEW.source_store_id,NEW.destination_store_id);
            ELSIF OLD.status IN ('dispatched','received','returning') AND NEW.status IN ('completed','cancelled') THEN
                UPDATE stores SET open_handoff_count=open_handoff_count-1 WHERE id IN (NEW.source_store_id,NEW.destination_store_id);
            END IF;
            RETURN NEW;
        END $$
    """)
    conn.execute("CREATE TRIGGER store_handoff_count AFTER INSERT OR UPDATE ON store_handoffs FOR EACH ROW EXECUTE FUNCTION count_store_handoff()")
    conn.execute("""
        CREATE FUNCTION guard_order_custody() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.payload->'items' IS DISTINCT FROM OLD.payload->'items' OR
                (NEW.payload->>'status' IS DISTINCT FROM OLD.payload->>'status' AND NEW.payload->>'status' IN ('ready_for_pickup','collected','completed','cancelled','delivered','picked_up')))
               AND EXISTS (SELECT 1 FROM store_handoffs WHERE order_id=OLD.id AND business_id=OLD.business_id AND source_store_id=OLD.location_id AND status IN ('dispatched','received','returning')) THEN
                RAISE EXCEPTION 'Finish or cancel the open handoff before changing items or closing the order';
            END IF;
            RETURN NEW;
        END $$
    """)
    conn.execute("CREATE TRIGGER order_custody_guard BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION guard_order_custody()")
    conn.execute("INSERT INTO fabclean_schema_migrations(version) VALUES (%s)", (VERSION,))
