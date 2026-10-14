"""Consent-aware, tenant-scoped notification outbox and immutable receipt snapshots.

Order transactions only enqueue. Authenticated dispatch claims durably before any
provider request; ambiguous outcomes are never automatically resent.
"""
import hashlib
import base64
import json
import os
import re
import string
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock

import httpx
from fastapi import Header, HTTPException, Request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature
from starlette.concurrency import run_in_threadpool
from tenant_scope import ScopedMemoryDict, current_scope

VERSION = "notification-outbox-v1"
MAX_ATTEMPTS = 3
PREFERENCE_KEYS = {"email_opt_in", "sms_opt_in", "whatsapp_opt_in", "receipts", "status_updates"}
DEFAULT_PREFERENCES = {key: False for key in PREFERENCE_KEYS}
TEMPLATES = {
    "order_received": "Hi {name}, {business_name} received order {order_number}.",
    "ready_for_pickup": "Hi {name}, order {order_number} from {business_name} is ready for pickup.",
    "delivery_scheduled": "Hi {name}, delivery for order {order_number} from {business_name} is scheduled.",
    "order_receipt": "Hi {name}, your {business_name} receipt for order {order_number}.",
    "payment_receipt": "Hi {name}, {business_name} recorded payment activity for order {order_number}.",
}
FIELDS = {"name", "business_name", "order_number"}
memory_preferences = ScopedMemoryDict()
memory_outbox = ScopedMemoryDict()
memory_events = ScopedMemoryDict()
memory_lock = RLock()


def now():
    return datetime.now(timezone.utc)


def install(conn):
    if conn.execute("SELECT 1 FROM fabclean_schema_migrations WHERE version=%s", (VERSION,)).fetchone():
        return
    conn.execute("ALTER TABLE customer_notifications ADD COLUMN event_key TEXT")
    conn.execute("ALTER TABLE customer_notifications ADD COLUMN delivery JSONB NOT NULL DEFAULT '{}'::jsonb")
    conn.execute("CREATE UNIQUE INDEX notification_event_once ON customer_notifications(business_id,location_id,event_key) WHERE event_key IS NOT NULL")
    conn.execute("ALTER TABLE customer_notifications ADD UNIQUE(id,business_id,location_id)")
    conn.execute("""CREATE TABLE notification_preferences(
        customer_id TEXT NOT NULL,business_id TEXT NOT NULL,location_id TEXT NOT NULL,
        payload JSONB NOT NULL,PRIMARY KEY(customer_id,business_id,location_id),
        FOREIGN KEY(customer_id,business_id,location_id) REFERENCES customers(id,business_id,location_id))""")
    conn.execute("""CREATE TABLE notification_events(
        id TEXT PRIMARY KEY,notification_id TEXT,business_id TEXT NOT NULL,location_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,event TEXT NOT NULL,metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY(customer_id,business_id,location_id) REFERENCES customers(id,business_id,location_id),
        FOREIGN KEY(notification_id,business_id,location_id) REFERENCES customer_notifications(id,business_id,location_id))""")
    for table in ("notification_preferences", "notification_events"):
        predicate = "business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),'')"
        conn.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        conn.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        conn.execute(f"CREATE POLICY notification_scope ON {table} USING (current_setting('app.maintenance',true)='on' OR ({predicate})) WITH CHECK (current_setting('app.maintenance',true)='on' OR ({predicate}))")
    conn.execute("""CREATE FUNCTION protect_notification_events() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Notification audit events are append-only'; END $$""")
    conn.execute("CREATE TRIGGER notification_events_append_only BEFORE UPDATE OR DELETE ON notification_events FOR EACH ROW EXECUTE FUNCTION protect_notification_events()")
    conn.execute("CREATE INDEX notification_pending ON customer_notifications(business_id,location_id,status)")
    conn.execute("INSERT INTO fabclean_schema_migrations(version) VALUES (%s)", (VERSION,))


def install_delivery_events(conn):
    version = "notification-signed-events-v1"
    if conn.execute("SELECT 1 FROM fabclean_schema_migrations WHERE version=%s", (version,)).fetchone():
        return
    conn.execute("ALTER TABLE notification_events ADD COLUMN provider_event_key TEXT")
    conn.execute("CREATE UNIQUE INDEX notification_provider_event_once ON notification_events(business_id,location_id,provider_event_key) WHERE provider_event_key IS NOT NULL")
    conn.execute("INSERT INTO fabclean_schema_migrations(version) VALUES (%s)", (version,))


def validate_settings(values):
    for key in ("notification_email_sender", "notification_sms_sender"):
        value = values.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str) or not valid_contact("email" if key.endswith("email_sender") else "sms", value):
            raise HTTPException(400, "Use a verified sender email or E.164 SMS number")
    templates = values.get("notification_templates")
    if templates is not None:
        if not isinstance(templates, dict) or set(templates) - set(TEMPLATES):
            raise HTTPException(400, "Unsupported notification templates")
        for text in templates.values():
            if not isinstance(text, str) or not text.strip() or len(text) > 1500:
                raise HTTPException(400, "Templates must contain 1–1500 characters")
            try:
                for _, field, spec, conversion in string.Formatter().parse(text):
                    if field is not None and (field not in FIELDS or spec or conversion):
                        raise ValueError()
            except ValueError:
                raise HTTPException(400, "Use only {name}, {business_name} and {order_number} placeholders")


def valid_contact(channel, value):
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value)) if channel == "email" else bool(re.fullmatch(r"\+[1-9]\d{7,14}", value))


def preferences(s, customer_id):
    if not s.DATABASE_URL:
        saved = memory_preferences.get(customer_id, {})
    else:
        with s.db() as conn:
            row = conn.execute("SELECT payload FROM notification_preferences WHERE customer_id=%s", (customer_id,)).fetchone()
        saved = row["payload"] if row else {}
    return {**DEFAULT_PREFERENCES, **deepcopy(saved)}


def audit(s, customer_id, event, notification_id=None, metadata=None):
    row = {"id": str(uuid.uuid4()), "customer_id": customer_id, "notification_id": notification_id,
           "event": event, "metadata": metadata or {}, "created_at": now().isoformat()}
    if not s.DATABASE_URL:
        memory_events[row["id"]] = row
    else:
        with s.db() as conn:
            conn.execute("INSERT INTO notification_events(id,customer_id,notification_id,business_id,location_id,event,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                         (row["id"], customer_id, notification_id, *current_scope.get(), event, json.dumps(row["metadata"])))


def update_preferences(s, customer_id, payload, staff):
    if not isinstance(payload, dict) or set(payload) - (PREFERENCE_KEYS | {"consent_note"}):
        raise HTTPException(400, "Unsupported communication preference")
    if any(type(value) is not bool for key, value in payload.items() if key in PREFERENCE_KEYS):
        raise HTTPException(400, "Preferences must be booleans")
    note = payload.get("consent_note", "")
    if not isinstance(note, str) or len(note) > 500:
        raise HTTPException(400, "Consent note must be at most 500 characters")
    # An explicit affirmative record is required whenever a channel is enabled.
    if any(payload.get(key) is True for key in ("email_opt_in", "sms_opt_in", "whatsapp_opt_in")) and not note.strip():
        raise HTTPException(400, "Record how the customer gave consent before opting in")
    def revised(previous):
        return {**DEFAULT_PREFERENCES, **previous, **{k: v for k, v in payload.items() if k in PREFERENCE_KEYS},
                "updated_at": now().isoformat(), "updated_by": staff.get("id"),
                "consent_note": note.strip() if "consent_note" in payload else previous.get("consent_note", "")}
    if not s.DATABASE_URL:
        with memory_lock:
            values = revised(preferences(s, customer_id))
            memory_preferences[customer_id] = values
            audit(s, customer_id, "preferences_updated", metadata={**values})
    else:
        with s.db() as conn, conn.transaction():
            marker = s.transaction_connection.set(conn)
            try:
                conn.execute("INSERT INTO notification_preferences(customer_id,business_id,location_id,payload) VALUES (%s,%s,%s,'{}'::jsonb) ON CONFLICT(customer_id,business_id,location_id) DO NOTHING", (customer_id, *current_scope.get()))
                previous = conn.execute("SELECT payload FROM notification_preferences WHERE customer_id=%s FOR UPDATE", (customer_id,)).fetchone()['payload']
                values = revised(previous)
                conn.execute("INSERT INTO notification_preferences(customer_id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT(customer_id,business_id,location_id) DO UPDATE SET payload=EXCLUDED.payload",
                             (customer_id, *current_scope.get(), json.dumps(values)))
                audit(s, customer_id, "preferences_updated", metadata={**values})
            finally:
                s.transaction_connection.reset(marker)
    return values


def permitted(prefs, kind, channel):
    return bool(prefs.get(channel + "_opt_in") and prefs.get("receipts" if kind.endswith("receipt") else "status_updates"))


def current_customer(s, customer_id):
    if not s.DATABASE_URL:
        customer = s.memory_customers.get(customer_id)
        return customer.model_dump(mode="json") if customer else {}
    with s.db() as conn:
        row = conn.execute("SELECT id,name,email,phone FROM customers WHERE id=%s", (customer_id,)).fetchone()
    return dict(row) if row else {}


def receipt(s, order, payment=None):
    rows, paid, balance = s.payment_totals(order["id"], order["total"])
    return {"order_number": order["order_number"], "items": deepcopy(order.get("items", [])),
            **{key: deepcopy(order.get(key, 0)) for key in ("subtotal", "discount", "delivery_fee", "tax", "total")},
            "tax_snapshot": deepcopy(order.get("tax_snapshot")), "paid_total": paid, "balance_due": balance,
            "payment": json.loads(json.dumps(payment, default=str)) if payment else None,
            "receipt_number": (payment or (rows[-1] if rows else {})).get("receipt_number")}


def render(s, order, kind, payment=None):
    settings = s.get_settings_value()
    fields = {"name": (order.get("customer") or {}).get("name") or "Customer",
              "business_name": settings.get("business_name") or "FabClean", "order_number": order["order_number"]}
    text = settings.get("notification_templates", {}).get(kind, TEMPLATES[kind]).format(**fields)
    snapshot = receipt(s, order, payment) if kind.endswith("receipt") else None
    if snapshot:
        lines = (snapshot.get('tax_snapshot') or {}).get('lines') or []
        text += "\n" + "\n".join(f"{item.get('service_name', 'Service')} x {item.get('quantity', 1)}: {float(lines[i]['base']) if i<len(lines) else float(s.taxes.money(s.taxes.number(item.get('quantity',1))*s.taxes.number(item.get('unit_price',0)))):.2f}" for i,item in enumerate(snapshot["items"]))
        currency = (snapshot.get('tax_snapshot') or {}).get('currency') or 'Recorded amount'
        text += "\n" + "\n".join(f"{key.replace('_',' ').title()}: {currency} {snapshot[key]:.2f}" for key in ("subtotal", "discount", "delivery_fee", "tax", "total", "paid_total", "balance_due"))
        tax = snapshot.get("tax_snapshot") or {}
        loc = tax.get("location") or {}
        text += "\nService location: " + ", ".join(str(loc.get(k) or "") for k in ("city", "state", "postal_code", "country") if loc.get(k))
        for entry in tax.get("breakdown", []):
            text += f"\n{entry['jurisdiction']} ({entry['rate']}%): {currency} {entry['amount']:.2f}"
        if payment:
            text += f"\n{payment['transaction_type'].title()} {payment['receipt_number']}: {currency} {float(payment['amount']):.2f}"
            if payment.get("tax_amount"):
                text += f"\nRefund tax credit: {currency} {float(payment['tax_amount']):.2f}"
    return fields["business_name"] + " · " + kind.replace("_", " ") + " · " + fields["order_number"], text, snapshot


def whatsapp_receipt(s, order):
    """Prepare a manual share only. No provider calls, queue or delivery claim."""
    customer = current_customer(s, (order.get('customer') or {}).get('id'))
    if not customer:
        raise HTTPException(404, 'Customer not found in the selected store')
    prefs = preferences(s, customer['id'])
    if not permitted(prefs, 'order_receipt', 'whatsapp'):
        raise HTTPException(409, 'Record WhatsApp consent and enable receipts in Customer Profile before sharing')
    raw = str(customer.get('phone') or '').strip()
    if not re.fullmatch(r'\+[0-9 ()-]+', raw):
        raise HTTPException(400, 'Save the customer phone with an international country code, for example +15551234567')
    phone = '+' + re.sub(r'\D', '', raw)
    if not valid_contact('sms', phone):
        raise HTTPException(400, 'Save a valid international customer phone number before sharing')
    _, message, snapshot = render(s, {**order, 'customer': customer}, 'order_receipt')
    if len(message.encode('utf-8')) > 6000:
        raise HTTPException(400, 'This receipt is too long for WhatsApp link sharing; use the printed receipt')
    fingerprint = hashlib.sha256(json.dumps([phone, message, snapshot, prefs.get('updated_at')], sort_keys=True, default=str).encode()).hexdigest()
    return {'phone': phone, 'message': message, 'receipt': snapshot, 'fingerprint': fingerprint}


def enqueue(s, order, kind, staff=None, payment=None, manual=False):
    if kind not in TEMPLATES:
        raise HTTPException(400, "Unsupported notification type")
    settings = s.get_settings_value()
    if not settings.get("notifications_enabled", False) and not manual:
        return []
    customer = current_customer(s, (order.get("customer") or {}).get("id"))
    if not customer.get("id"):
        return []
    order = {**order, "customer": customer}
    prefs = preferences(s, customer["id"])
    subject, text, snapshot = render(s, order, kind, payment)
    event = payment["id"] if payment else order["id"]
    if manual:
        event += ":" + hashlib.sha256(json.dumps([snapshot, subject, text, settings.get('notification_email_sender'), settings.get('notification_sms_sender'), customer.get('email'), customer.get('phone'), prefs.get('updated_at')], sort_keys=True, default=str).encode()).hexdigest()
    results = []
    for channel in ("email", "sms"):
        event_key = f"{kind}:{event}:{channel}"
        recipient = str(customer.get("email" if channel == "email" else "phone") or "").strip()
        status = "queued" if permitted(prefs, kind, channel) else "suppressed"
        row = {"id": str(uuid.uuid4()), "customer_id": customer["id"], "order_id": order["id"],
               "notification_type": kind, "channel": channel, "message": text, "status": status,
               "event_key": event_key, "created_at": now().isoformat(), "staff_id": (staff or {}).get("id"),
               "staff_name": (staff or {}).get("name", ""), "delivery": {"subject": subject, "recipient": recipient,
               "receipt": snapshot, "attempts": 0, "next_attempt_at": None}}
        if not s.DATABASE_URL:
            with memory_lock:
                existing = next((v for v in memory_outbox.values() if v.get("event_key") == event_key), None)
                if existing:
                    results.append(deepcopy(existing))
                    continue
                memory_outbox[row["id"]] = row
                audit(s, customer["id"], status, row["id"])
        else:
            with s.db() as conn, conn.transaction():
                marker = s.transaction_connection.set(conn)
                try:
                    inserted = conn.execute("""INSERT INTO customer_notifications(id,customer_id,order_id,notification_type,channel,message,status,staff_id,staff_name,event_key,delivery)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                        ON CONFLICT(business_id,location_id,event_key) WHERE event_key IS NOT NULL DO NOTHING RETURNING *""",
                        (row["id"], row["customer_id"], row["order_id"], kind, channel, text, status, row["staff_id"], row["staff_name"], event_key, json.dumps(row["delivery"]))).fetchone()
                    if not inserted:
                        row = dict(conn.execute("SELECT * FROM customer_notifications WHERE event_key=%s", (event_key,)).fetchone())
                    else:
                        row = dict(inserted)
                        audit(s, customer["id"], status, row["id"])
                finally:
                    s.transaction_connection.reset(marker)
        results.append(row)
    return results


def load(s, notification_id):
    if not s.DATABASE_URL:
        row = memory_outbox.get(notification_id)
    else:
        with s.db() as conn:
            row = conn.execute("SELECT * FROM customer_notifications WHERE id=%s", (notification_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Notification not found")
    return deepcopy(dict(row))


def save(s, row, event):
    if not s.DATABASE_URL:
        memory_outbox[row["id"]] = deepcopy(row)
        audit(s, row["customer_id"], event, row["id"], {"attempts": row["delivery"].get("attempts", 0)})
    else:
        with s.db() as conn, conn.transaction():
            marker = s.transaction_connection.set(conn)
            try:
                conn.execute("UPDATE customer_notifications SET status=%s,delivery=%s::jsonb,provider_message_id=%s,error_message=%s WHERE id=%s",
                             (row["status"], json.dumps(row["delivery"]), row.get("provider_message_id"), row.get("error_message", ""), row["id"]))
                audit(s, row["customer_id"], event, row["id"], {"attempts": row["delivery"].get("attempts", 0)})
            finally:
                s.transaction_connection.reset(marker)


def provider_send(s, row, sender):
    """Send only persisted plain text. Never return or log raw provider errors."""
    if row["channel"] == "email":
        response = httpx.post("https://api.sendgrid.com/v3/mail/send", headers={"Authorization": "Bearer " + s.SENDGRID_API_KEY},
                              json={"personalizations": [{"to": [{"email": row["delivery"]["recipient"]}],
                                    "custom_args": {"fabclean_notification_id": row["id"], "fabclean_brand_id": current_scope.get()[0], "fabclean_store_id": current_scope.get()[1]}}],
                                    "from": {"email": sender}, "subject": row["delivery"]["subject"],
                                    "content": [{"type": "text/plain", "value": row["message"]}]}, timeout=15)
    else:
        response = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{s.TWILIO_ACCOUNT_SID}/Messages.json",
                              auth=(s.TWILIO_ACCOUNT_SID, s.TWILIO_AUTH_TOKEN),
                              data={"To": row["delivery"]["recipient"], "From": sender, "Body": row["message"]}, timeout=15)
    if 200 <= response.status_code < 300:
        provider_id = response.headers.get("X-Message-Id", "") if row["channel"] == "email" else response.json().get("sid", "")
        return {"status": "accepted", "provider_message_id": provider_id}
    if response.status_code in (408,) or response.status_code >= 500:
        return {"status": "unknown", "error_message": "Provider outcome uncertain; inspect provider records before any new send"}
    return {"status": "failed", "error_message": f"Provider rejected request (HTTP {response.status_code})",
            "retryable": response.status_code == 429}


def claim(s, notification_id):
    """Commit the sending claim first: crashes cannot cause automatic duplicates."""
    if not s.DATABASE_URL:
        with memory_lock:
            row = load(s, notification_id)
            return claim_row(s, row)
    with s.db() as conn, conn.transaction():
        selected = conn.execute("SELECT * FROM customer_notifications WHERE id=%s FOR UPDATE", (notification_id,)).fetchone()
        if not selected:
            raise HTTPException(404, "Notification not found")
        marker = s.transaction_connection.set(conn)
        try:
            return claim_row(s, dict(selected))
        finally:
            s.transaction_connection.reset(marker)


def claim_row(s, row):
    delivery = row.get("delivery") or {}
    if not row.get("event_key"):
        raise HTTPException(409, "Legacy prepared messages cannot be sent; queue a fresh receipt")
    if row["status"] not in ("queued", "blocked", "failed"):
        raise HTTPException(409, "This notification cannot be sent again")
    if row["status"] == "failed" and not delivery.get("retryable"):
        raise HTTPException(409, "This rejection requires corrected configuration and a new receipt")
    if delivery.get("attempts", 0) >= MAX_ATTEMPTS:
        raise HTTPException(409, "Maximum delivery attempts reached")
    if delivery.get("next_attempt_at") and now() < datetime.fromisoformat(delivery["next_attempt_at"]):
        raise HTTPException(409, "Retry is not due yet")
    settings = s.get_settings_value()
    if not permitted(preferences(s, row["customer_id"]), row["notification_type"], row["channel"]):
        row["status"] = "suppressed"
        save(s, row, "consent_suppressed")
        return row, None
    if not settings.get("notifications_enabled", False):
        row["status"] = "blocked"
        row["error_message"] = "Enable notifications for the selected store first"
        delivery["next_attempt_at"] = (now() + timedelta(minutes=5)).isoformat()
        save(s, row, "blocked")
        return row, None
    customer = current_customer(s, row["customer_id"])
    current_contact = str(customer.get("email" if row["channel"] == "email" else "phone") or "").strip()
    sender = settings.get("notification_" + row["channel"] + "_sender") or (s.SENDGRID_FROM_EMAIL if row["channel"] == "email" else s.TWILIO_FROM_NUMBER)
    configured = bool(s.SENDGRID_API_KEY) if row["channel"] == "email" else bool(s.TWILIO_ACCOUNT_SID and s.TWILIO_AUTH_TOKEN)
    if not configured or not valid_contact(row["channel"], sender) or not valid_contact(row["channel"], current_contact) or current_contact != delivery["recipient"]:
        row["status"] = "blocked"
        row["error_message"] = "Configure a verified sender and valid unchanged customer contact before delivery"
        delivery["next_attempt_at"] = (now() + timedelta(minutes=5)).isoformat()
        save(s, row, "blocked")
        return row, None
    row["status"] = "sending"
    row["error_message"] = ""
    delivery["attempts"] = delivery.get("attempts", 0) + 1
    delivery["claimed_at"] = now().isoformat()
    delivery["sender"] = sender
    row["delivery"] = delivery
    save(s, row, "sending")
    return row, sender


def dispatch(s, notification_id):
    row, sender = claim(s, notification_id)
    if sender is None:
        return row
    try:
        outcome = provider_send(s, row, sender)
    except (httpx.HTTPError, ValueError, KeyError):
        outcome = {"status": "unknown", "error_message": "Provider outcome uncertain; inspect provider records before any new send"}
    row.update({k: v for k, v in outcome.items() if k != "retryable"})
    row["delivery"]["retryable"] = outcome.get("retryable", False)
    row["delivery"]["next_attempt_at"] = (now() + timedelta(seconds=60 * 2 ** (row["delivery"]["attempts"] - 1))).isoformat() if outcome.get("retryable") else None
    # Signed delivery evidence may arrive before the provider send response.
    if s.DATABASE_URL:
        with s.db() as conn, conn.transaction():
            current = conn.execute("SELECT status FROM customer_notifications WHERE id=%s FOR UPDATE", (row["id"],)).fetchone()
            if current["status"] in ("delivered", "undelivered", "suppressed"):
                return load(s, row["id"])
            marker = s.transaction_connection.set(conn)
            try:
                save(s, row, row["status"])
            finally:
                s.transaction_connection.reset(marker)
    else:
        save(s, row, row["status"])
    return row


def verify_email_event(raw, signature, timestamp):
    public_key = os.getenv("FABCLEAN_SENDGRID_WEBHOOK_PUBLIC_KEY", "")
    if not public_key:
        raise HTTPException(503, "Signed email delivery events are not configured")
    try:
        stamp = int(timestamp)
        if abs(now().timestamp() - stamp) > 300:
            raise ValueError()
        key = serialization.load_pem_public_key(public_key.encode()) if public_key.startswith("-----BEGIN") else serialization.load_der_public_key(base64.b64decode(public_key, validate=True))
        if not isinstance(key, ec.EllipticCurvePublicKey):
            raise ValueError()
        key.verify(base64.b64decode(signature, validate=True), timestamp.encode() + raw, ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature):
        raise HTTPException(401, "Invalid email-event signature or timestamp")


def apply_email_events(s, events):
    if not isinstance(events, list) or len(events) > 1000:
        raise HTTPException(400, "Invalid delivery-event batch")
    for event in events:
        if not isinstance(event, dict):
            raise HTTPException(400, "Invalid delivery event")
        identifiers = [event.get(k) for k in ("fabclean_notification_id", "fabclean_brand_id", "fabclean_store_id", "sg_event_id")]
        if any(not isinstance(value, str) or not value or len(value) > 200 for value in identifiers):
            continue
        nid, brand, store, event_id = identifiers
        marker = current_scope.set((brand, store))
        try:
            with s.db() as conn, conn.transaction():
                row = conn.execute("SELECT * FROM customer_notifications WHERE id=%s AND channel='email' FOR UPDATE", (nid,)).fetchone()
                if not row or not row.get("event_key") or not row["delivery"].get("attempts"):
                    continue
                if conn.execute("SELECT 1 FROM notification_events WHERE provider_event_key=%s", (event_id,)).fetchone():
                    continue
                message_id = row.get("provider_message_id")
                if message_id and not str(event.get("sg_message_id", "")).startswith(message_id + ".") and event.get("sg_message_id") != message_id:
                    continue
                if event.get("email") != row["delivery"].get("recipient"):
                    continue
                kind = event.get("event")
                if kind not in ("delivered", "bounce", "dropped", "deferred", "spamreport", "unsubscribe"):
                    continue
                status = "delivered" if kind == "delivered" else "undelivered" if kind in ("bounce", "dropped") else row["status"]
                if row["status"] != "delivered":
                    conn.execute("UPDATE customer_notifications SET status=%s WHERE id=%s", (status, nid))
                conn.execute("INSERT INTO notification_events(id,notification_id,customer_id,business_id,location_id,event,metadata,provider_event_key) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                             (str(uuid.uuid4()), nid, row["customer_id"], brand, store, kind, json.dumps({"source": "signed_sendgrid_event"}), event_id))
                if kind in ("spamreport", "unsubscribe"):
                    conn.execute("INSERT INTO notification_preferences(customer_id,business_id,location_id,payload) VALUES (%s,%s,%s,'{}'::jsonb) ON CONFLICT(customer_id,business_id,location_id) DO NOTHING", (row['customer_id'],brand,store))
                    previous = conn.execute("SELECT payload FROM notification_preferences WHERE customer_id=%s FOR UPDATE", (row['customer_id'],)).fetchone()['payload']
                    prefs = {**DEFAULT_PREFERENCES, **previous, "email_opt_in": False, "updated_at": now().isoformat(), "updated_by": "provider_opt_out"}
                    conn.execute("INSERT INTO notification_preferences(customer_id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT(customer_id,business_id,location_id) DO UPDATE SET payload=EXCLUDED.payload", (row["customer_id"], brand, store, json.dumps(prefs)))
        finally:
            current_scope.reset(marker)


def register(app, s):
    @app.post("/api/notifications/webhooks/sendgrid")
    async def email_events(request: Request):
        if not s.DATABASE_URL:
            raise HTTPException(503, "Delivery events require database mode")
        raw = await request.body()
        if len(raw) > 256000:
            raise HTTPException(413, "Delivery-event batch is too large")
        verify_email_event(raw, request.headers.get("X-Twilio-Email-Event-Webhook-Signature", ""), request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", ""))
        try:
            events = json.loads(raw)
        except ValueError:
            raise HTTPException(400, "Invalid delivery-event JSON")
        await run_in_threadpool(apply_email_events, s, events)
        return {"received": True}

    @app.get("/api/customers/{customer_id}/communication-preferences")
    def get_preferences(customer_id: str, x_session_token: str | None = Header(default=None)):
        s.require_permission("customers", x_session_token)
        s.get_customer(customer_id, x_session_token)
        return preferences(s, customer_id)

    @app.put("/api/customers/{customer_id}/communication-preferences")
    def put_preferences(customer_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
        staff = s.require_permission("customers", x_session_token)
        s.get_customer(customer_id, x_session_token)
        return update_preferences(s, customer_id, payload, staff)

    @app.post("/api/orders/{order_id}/send-receipt")
    @s.order_transaction
    def queue_receipt(order_id: str, x_session_token: str | None = Header(default=None)):
        staff = s.require_permission("orders", x_session_token)
        order = s.get_order(order_id, x_session_token)
        order = order.model_dump(mode="json") if hasattr(order, "model_dump") else dict(order)
        return {"notifications": enqueue(s, order, "order_receipt", staff, manual=True)}

    @app.get('/api/orders/{order_id}/whatsapp-receipt')
    @s.order_transaction
    def preview_whatsapp(order_id: str, x_session_token: str | None = Header(default=None)):
        s.require_permission('orders', x_session_token)
        order = s.get_order(order_id, x_session_token)
        order = order.model_dump(mode='json') if hasattr(order, 'model_dump') else dict(order)
        return whatsapp_receipt(s, order)

    @app.post('/api/orders/{order_id}/whatsapp-receipt')
    @s.order_transaction
    def confirm_whatsapp(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
        staff = s.require_permission('orders', x_session_token)
        if set(payload) != {'fingerprint'} or not isinstance(payload['fingerprint'], str):
            raise HTTPException(400, 'Confirm the reviewed WhatsApp receipt')
        order = s.get_order(order_id, x_session_token)
        order = order.model_dump(mode='json') if hasattr(order, 'model_dump') else dict(order)
        preview = whatsapp_receipt(s, order)
        if payload['fingerprint'] != preview['fingerprint']:
            raise HTTPException(409, 'Receipt, recipient or preferences changed; preview the WhatsApp receipt again')
        audit(s, order['customer']['id'], 'whatsapp_share_prepared', metadata={'order_id': order_id,
              'fingerprint': preview['fingerprint'], 'receipt': preview['receipt'], 'prepared_by': staff.get('id')})
        return preview

    @app.get("/api/notifications/outbox")
    def outbox(pending: bool = False, x_session_token: str | None = Header(default=None)):
        s.require_permission("orders", x_session_token)
        if not s.DATABASE_URL:
            rows = list(memory_outbox.values())
        else:
            with s.db() as conn:
                condition = " AND (status IN ('queued','blocked') OR (status='failed' AND delivery->>'retryable'='true')) AND COALESCE((delivery->>'attempts')::int,0)<3 AND (delivery->>'next_attempt_at' IS NULL OR (delivery->>'next_attempt_at')::timestamptz<=NOW())" if pending else ""
                rows = [dict(r) for r in conn.execute("SELECT * FROM customer_notifications WHERE event_key IS NOT NULL"+condition+" ORDER BY created_at "+('ASC' if pending else 'DESC')+" LIMIT 100").fetchall()]
        if pending and not s.DATABASE_URL:
            rows = [r for r in rows if r['status'] in ('queued','blocked','failed') and (r['status']!='failed' or r['delivery'].get('retryable')) and r['delivery'].get('attempts',0)<3 and (not r['delivery'].get('next_attempt_at') or datetime.fromisoformat(r['delivery']['next_attempt_at'])<=now())]
        return {"notifications": sorted(rows, key=lambda r: str(r["created_at"]), reverse=not pending)[:100]}

    @app.post("/api/notifications/outbox/{notification_id}/dispatch")
    def send(notification_id: str, x_session_token: str | None = Header(default=None)):
        s.require_permission("orders", x_session_token)
        return dispatch(s, notification_id)

    @app.get("/api/customers/{customer_id}/communication-events")
    def events(customer_id: str, x_session_token: str | None = Header(default=None)):
        s.require_permission("customers", x_session_token)
        s.get_customer(customer_id, x_session_token)
        if not s.DATABASE_URL:
            rows = [v for v in memory_events.values() if v["customer_id"] == customer_id]
        else:
            with s.db() as conn:
                rows = [dict(r) for r in conn.execute("SELECT * FROM notification_events WHERE customer_id=%s ORDER BY created_at DESC LIMIT 100", (customer_id,)).fetchall()]
        return {"events": rows}

    @app.post("/api/notifications/outbox/{notification_id}/delivery-status")
    def delivery_status(notification_id: str, x_session_token: str | None = Header(default=None)):
        s.require_permission("orders", x_session_token)
        row = load(s, notification_id)
        if row["channel"] != "sms" or not row.get("provider_message_id") or row["status"] != "accepted":
            raise HTTPException(409, "Only accepted SMS messages can be checked with the provider")
        message_id = row["provider_message_id"]
        if not re.fullmatch(r"SM[0-9a-fA-F]{32}", message_id):
            raise HTTPException(409, "Invalid saved provider message ID")
        if not s.TWILIO_ACCOUNT_SID or not s.TWILIO_AUTH_TOKEN:
            raise HTTPException(503, "SMS provider is not configured")
        try:
            response = httpx.get(f"https://api.twilio.com/2010-04-01/Accounts/{s.TWILIO_ACCOUNT_SID}/Messages/{message_id}.json", auth=(s.TWILIO_ACCOUNT_SID, s.TWILIO_AUTH_TOKEN), timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get("sid") != message_id:
                raise ValueError()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Provider delivery status is unavailable")
        # Provider acceptance is distinct from delivery; never infer email delivery.
        if data.get("status") in ("delivered", "undelivered", "failed"):
            row["status"] = "delivered" if data["status"] == "delivered" else "undelivered"
            save(s, row, row["status"])
        return row
