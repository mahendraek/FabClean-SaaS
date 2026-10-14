"""Explicit, reviewed US rate lookup; never call a provider while pricing orders.

ZipTax-compatible v20 lookups are an optional adapter. Account/API eligibility,
including any free allowance, must be verified before enabling it. Importing a
sales-tax rate does not determine whether a laundry service is taxable.
"""
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from fastapi import Header, HTTPException
import taxes
from tenant_scope import ScopedMemoryDict, current_scope

VERSION = "tax-provider-quotes-v1"
memory_quotes = ScopedMemoryDict()


def install(conn):
    if conn.execute("SELECT 1 FROM fabclean_schema_migrations WHERE version=%s", (VERSION,)).fetchone():
        return
    conn.execute("""CREATE TABLE tax_provider_quotes(id TEXT PRIMARY KEY,business_id TEXT NOT NULL,
        location_id TEXT NOT NULL,payload JSONB NOT NULL,
        FOREIGN KEY(location_id,business_id) REFERENCES stores(id,brand_id))""")
    predicate = "business_id=NULLIF(current_setting('app.brand_id',true),'') AND location_id=NULLIF(current_setting('app.store_id',true),'')"
    conn.execute("ALTER TABLE tax_provider_quotes ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE tax_provider_quotes FORCE ROW LEVEL SECURITY")
    conn.execute(f"CREATE POLICY tax_provider_scope ON tax_provider_quotes USING (current_setting('app.maintenance',true)='on' OR ({predicate})) WITH CHECK (current_setting('app.maintenance',true)='on' OR ({predicate}))")
    conn.execute("INSERT INTO fabclean_schema_migrations(version) VALUES (%s)", (VERSION,))


def parse_response(body, loc):
    if not isinstance(body, dict) or body.get("rCode") != 100 or not isinstance(body.get("results"), list):
        raise HTTPException(503, "Tax provider did not return a successful rate lookup")
    matches = [r for r in body["results"] if isinstance(r, dict)
               and taxes.normalized(r.get("geoState")) == taxes.normalized(loc["state"])
               and taxes.normalized(r.get("geoCity")) == taxes.normalized(loc["city"])
               and str(r.get("geoPostalCode")) == loc["postal_code"]]
    if len(matches) != 1:
        raise HTTPException(409, "Provider location is ambiguous or does not match the saved store; verify the street-level jurisdiction")
    row = matches[0]
    try:
        if "taxSales" not in row or isinstance(row["taxSales"], bool):
            raise ValueError()
        rate = (Decimal(str(row["taxSales"])) * 100).normalize()
        if not rate.is_finite() or not 0 <= rate <= 100 or rate.as_tuple().exponent < -4:
            raise ValueError()
    except (ValueError, ArithmeticError):
        raise HTTPException(503, "Tax provider returned an invalid sales-tax rate")
    return {"rate": format(rate, 'f'), "jurisdiction": ", ".join(str(row.get(k) or "") for k in ("geoCity", "geoCounty", "geoState") if row.get(k)),
            "provider_service_flag": str(row.get("txbService", "unknown")),
            "note": "Postal/city rate only. Verify street-level jurisdiction and each service's taxability before import."}


def saved_quotes(s):
    if not s.DATABASE_URL:
        return list(memory_quotes.values())
    with s.db() as conn:
        return [r["payload"] for r in conn.execute("SELECT payload FROM tax_provider_quotes").fetchall()]


def lookup(s):
    loc = taxes.canonical_location(taxes.location(s))
    if loc.get("country") != "US" or not re.fullmatch(r"\d{5}", loc.get("postal_code") or "") or not loc.get("city") or not loc.get("state"):
        raise HTTPException(409, "The current provider requires a saved US state, city and five-digit store postal code")
    instant = datetime.now(timezone.utc)
    for quote in saved_quotes(s):
        if quote["location"] == loc and not quote.get("imported") and datetime.fromisoformat(quote["expires_at"]) > instant:
            return quote
    key = os.getenv("FABCLEAN_TAX_PROVIDER_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Configure a tax-provider API key securely; confirm the account's free allowance before enabling lookups")
    try:
        response = httpx.get("https://api.zip-tax.com/request/v20", params={"key": key, "postalcode": loc["postal_code"], "format": "json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Tax provider unavailable; no location rates were changed")
    result = parse_response(data, loc)
    quote = {"id": str(uuid.uuid4()), "provider": "ZipTax", "location": loc, **result,
             "retrieved_at": instant.isoformat(), "expires_at": (instant + timedelta(hours=24)).isoformat(),
             "imported": False}
    if not s.DATABASE_URL:
        memory_quotes[quote["id"]] = quote
    else:
        with s.db() as conn:
            conn.execute("INSERT INTO tax_provider_quotes(id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb)", (quote["id"], *current_scope.get(), json.dumps(quote)))
    return quote


def apply_quote(s, quote_id, payload, actor):
    if set(payload) != {"jurisdiction_verified", "service_taxability_verified"} or any(v is not True for v in payload.values()):
        raise HTTPException(400, "Confirm both the exact jurisdiction and service tax treatment")
    quote = next((v for v in saved_quotes(s) if v["id"] == quote_id), None)
    if not quote:
        raise HTTPException(404, "Tax quote not found")
    if quote.get("imported"):
        raise HTTPException(409, "Tax quote has already been imported")
    if datetime.fromisoformat(quote["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(409, "Tax quote expired; look up the current location rate again")
    if quote["location"] != taxes.canonical_location(taxes.location(s)):
        raise HTTPException(409, "Store location changed after lookup; fetch a new quote")
    if taxes.selected(taxes.rules(s), quote["location"], taxes.store_date(quote["location"])):
        raise HTTPException(409, "End or void existing effective components before importing a combined provider rate; rates must not be added twice")
    loc = quote["location"]
    rule = taxes.validate_rule({"component": "provider_combined", "jurisdiction": quote["jurisdiction"],
                               **{k: loc[k] for k in ("country", "state", "city", "postal_code")},
                               "rate": quote["rate"], "effective_from": taxes.store_date(loc)})
    rule.update({"id": str(uuid.uuid4()), "provenance": {"provider": quote["provider"], "quote_id": quote_id,
                 "retrieved_at": quote["retrieved_at"], "verified_by": actor.get("id"), "verified_at": datetime.now(timezone.utc).isoformat()}})
    quote["imported"] = True
    if not s.DATABASE_URL:
        taxes.memory_rules[rule["id"]] = rule
        memory_quotes[quote_id] = quote
    else:
        with s.db() as conn:
            conn.execute("INSERT INTO tax_rules(id,business_id,location_id,payload) VALUES (%s,%s,%s,%s::jsonb)", (rule["id"], *current_scope.get(), json.dumps(rule)))
            conn.execute("UPDATE tax_provider_quotes SET payload=%s::jsonb WHERE id=%s", (json.dumps(quote), quote_id))
            s.platform_audit_write(conn, actor, "provider_tax_rule_imported", current_scope.get()[0], {"store_id": current_scope.get()[1], "rule_id": rule["id"], "quote_id": quote_id})
    return rule


def register(app, s):
    @app.get("/api/taxes/provider")
    def status(x_session_token: str | None = Header(default=None)):
        s.require_permission("admin", x_session_token)
        return {"provider": "ZipTax", "configured": bool(os.getenv("FABCLEAN_TAX_PROVIDER_KEY")),
                "coverage": "US postal/city lookup with explicit jurisdiction and service-taxability review",
                "billing_note": "Free-tier eligibility and quota must be confirmed with the provider; no account is created or paid plan selected by this application."}

    @app.post("/api/taxes/provider/lookup")
    def preview(x_session_token: str | None = Header(default=None)):
        s.require_permission("admin", x_session_token)
        if not s.DATABASE_URL:
            with s.configuration.memory_lock:
                return lookup(s)
        with s.db() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (json.dumps(['tax-lookup',*current_scope.get()]),))
            marker = s.transaction_connection.set(conn)
            try:
                return lookup(s)
            finally:
                s.transaction_connection.reset(marker)

    @app.post("/api/taxes/provider/{quote_id}/import")
    def confirm(quote_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
        actor = s.require_permission("admin", x_session_token)
        if not s.DATABASE_URL:
            with s.configuration.memory_lock:
                return apply_quote(s, quote_id, payload, actor)
        with s.db() as conn, conn.transaction():
            s.lock_brand_operations(conn, current_scope.get()[0])
            marker = s.transaction_connection.set(conn)
            try:
                return apply_quote(s, quote_id, payload, actor)
            finally:
                s.transaction_connection.reset(marker)
