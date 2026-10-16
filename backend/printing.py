"""Store-scoped printing profiles and staff-confirmed print audit (no device claims)."""
import math
import re
from datetime import datetime, timezone
from fastapi import Header, HTTPException
from tenant_scope import ScopedMemoryDict

DEFAULT_PROFILE = {'scanner_mode': 'hid_keyboard', 'scanner_prefix': '', 'scanner_suffix': '', 'scanner_uppercase': True, 'printer_mode': 'browser', 'printer_dpi': 203, 'label_width_mm': 50, 'label_height_mm': 25, 'label_gap_mm': 2, 'receipt_paper': '80mm'}
confirmations = ScopedMemoryDict()


def validate_profile(value):
    if not isinstance(value, dict) or set(value) - DEFAULT_PROFILE.keys():
        raise HTTPException(400, 'Unsupported hardware profile fields')
    for key, item in value.items():
        if key in ('scanner_prefix', 'scanner_suffix'):
            if not isinstance(item, str) or len(item) > 40 or any(ord(ch) < 32 for ch in item):
                raise HTTPException(400, 'Scanner prefix/suffix must be at most 40 printable characters')
        elif key == 'scanner_uppercase':
            if type(item) is not bool:
                raise HTTPException(400, 'Scanner uppercase must be a boolean')
        elif key in ('label_width_mm', 'label_height_mm', 'label_gap_mm'):
            low, high = {'label_width_mm': (30, 110), 'label_height_mm': (25, 150), 'label_gap_mm': (0, 10)}[key]
            if type(item) not in (int, float) or not math.isfinite(item) or not low <= item <= high:
                raise HTTPException(400, f'{key} must be between {low} and {high}')
        elif key == 'printer_dpi':
            if type(item) is not int or item not in (203, 300):
                raise HTTPException(400, 'Printer DPI must be 203 or 300')
        elif item not in {'scanner_mode': ('hid_keyboard',), 'printer_mode': ('browser', 'zpl', 'tspl'), 'receipt_paper': ('58mm', '80mm', 'a4')}[key]:
            raise HTTPException(400, 'Unsupported printer or receipt mode')
    return value


def effective_profile(value):
    # Legacy unvalidated settings must not become printer commands or CSS.
    result = dict(DEFAULT_PROFILE)
    if isinstance(value, dict):
        for key, item in value.items():
            try:
                validate_profile({key: item})
                result[key] = item
            except HTTPException:
                pass
    return result


def register(app, s):
    @app.get('/api/orders/{order_id}/print-preview')
    @s.order_transaction
    def preview(order_id: str, x_session_token: str | None = Header(default=None)):
        receipt = s.order_receipt(order_id, x_session_token)
        garments = s.list_order_garments(order_id, x_session_token)
        settings = s.get_settings_value()
        return {'receipt': receipt, 'garments': garments['garments'], 'business': {key: settings.get(key, '') for key in ('business_name', 'business_address', 'business_phone')}, 'profile': effective_profile(settings.get('hardware_profile')), 'generated_at': datetime.now(timezone.utc).isoformat()}

    @app.post('/api/orders/{order_id}/print-confirmations')
    @s.order_transaction
    def confirm(order_id: str, payload: dict, x_session_token: str | None = Header(default=None)):
        staff = s.require_permission('orders', x_session_token)
        s.get_order(order_id, x_session_token)
        if set(payload) - {'request_id', 'document', 'garment_codes'}:
            raise HTTPException(400, 'Unsupported print confirmation fields')
        request_id = payload.get('request_id')
        if not isinstance(request_id, str) or not re.fullmatch('[a-zA-Z0-9-]{16,64}', request_id):
            raise HTTPException(400, 'A valid print request identifier is required')
        document = payload.get('document')
        codes = payload.get('garment_codes', [])
        if document not in ('receipt', 'order_tag', 'garment_tags') or not isinstance(codes, list) or len(codes) > 100 or any(not isinstance(code, str) or len(code) > 100 for code in codes) or len(set(codes)) != len(codes):
            raise HTTPException(400, 'Invalid document or garment selection (maximum 100 tags)')
        if (document == 'garment_tags') != bool(codes):
            raise HTTPException(400, 'Garment codes are required only for garment tags')
        metadata = {'request_id': request_id, 'document': document, 'garment_codes': sorted(codes), 'staff_id': staff['id'], 'staff_name': staff.get('name', ''), 'confirmation': 'staff_confirmed_physical_print'}
        if s.DATABASE_URL:
            with s.db() as conn:
                previous = conn.execute("SELECT id,metadata FROM order_events WHERE order_id=%s AND event_type='physical_print_confirmed' AND metadata->>'request_id'=%s", (order_id, request_id)).fetchone()
        else:
            previous = confirmations.get(order_id + ':' + request_id)
        if previous:
            if previous['metadata'] != metadata:
                raise HTTPException(409, 'Print identifier already used for a different confirmation')
            return {'confirmation': previous, 'duplicate': True}
        garments = s.list_order_garments(order_id, x_session_token)['garments']
        allowed = {g['garment_code'] for g in garments}
        if set(codes) - allowed:
            raise HTTPException(404, 'Garment not found in this order')
        if s.DATABASE_URL:
            with s.db() as conn:
                conn.execute('UPDATE order_garments SET tag_print_count=tag_print_count+1,updated_at=NOW() WHERE order_id=%s AND garment_code=ANY(%s)', (order_id, codes))
        else:
            for garment in s.memory_garments.get(order_id, []):
                if garment['garment_code'] in codes:
                    garment['tag_print_count'] = garment.get('tag_print_count', 0) + 1
        event = s.record_order_event(order_id, 'physical_print_confirmed', metadata=metadata)
        if not s.DATABASE_URL:
            confirmations[order_id + ':' + request_id] = event
        return {'confirmation': event, 'duplicate': False}
