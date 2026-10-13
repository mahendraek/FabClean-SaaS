"""ISO country/subdivision selectors and explicit-country postal lookup.

Bundled ISO data from pycountry 24.6.1 (Debian iso-codes, LGPL-2.1+).
Postal codes are not globally unique; never infer a country solely from format.
"""
import json,re
from pathlib import Path
from functools import lru_cache
import httpx
from fastapi import Header,HTTPException

DATA=json.loads(Path(__file__).with_name('locations.json').read_text())
def country(value):
    value=str(value or '').strip()
    aliases={'usa':'US','united states of america':'US','uk':'GB','u.s.':'US','u.s.a.':'US'}
    if value.casefold() in aliases:return aliases[value.casefold()]
    for item in DATA['countries']:
        if value.casefold() in (item['code'].casefold(),item['name'].casefold()):return item['code']
    return value.upper()
def state(value,country_code):
    value=str(value or '').strip()
    for item in DATA['subdivisions'].get(country(country_code),[]):
        if value.casefold() in (item['code'].casefold(),item['name'].casefold(),(country(country_code)+'-'+item['code']).casefold()):return item['code']
    return value
def validate_location(data):
    code=country(data.get('country','US'));region=state(data.get('state',''),code)
    if code not in {c['code'] for c in DATA['countries']}:raise HTTPException(400,'Select a valid country')
    if region and DATA['subdivisions'].get(code) and region not in {s['code'] for s in DATA['subdivisions'][code]}:raise HTTPException(400,'Select a state belonging to the country')
    data['country']=code;data['state']=region

@lru_cache(maxsize=512)
def postal_lookup(code,postal):
    try:
        r=httpx.get('https://api.zippopotam.us/'+code.lower()+'/'+postal,timeout=8,follow_redirects=False)
        if r.status_code==404:raise HTTPException(404,'Postal code not found for this country; select the country and state manually')
        r.raise_for_status();body=r.json()
    except (httpx.HTTPError,ValueError):raise HTTPException(503,'Postal lookup unavailable; enter the location manually')
    resolved=country(body.get('country abbreviation'))
    if resolved!=code:raise HTTPException(503,'Postal lookup returned a different country')
    places=body.get('places') or []
    states={state(p.get('state abbreviation') or p.get('state'),code) for p in places}
    if len(states)!=1:raise HTTPException(409,'Postal code spans multiple states; choose the correct state manually')
    region=states.pop()
    if not region or region not in {s['code'] for s in DATA['subdivisions'].get(code,[])}:raise HTTPException(503,'Postal lookup returned an unknown state')
    return {'country':code,'state':region,'postal_code':postal,'cities':sorted({p['place name'] for p in places if p.get('place name')}),'source':'Zippopotam.us','note':'Confirm the store address. Postal codes do not determine tax rates or county boundaries.'}

def register(app,s):
    @app.get('/api/locations/options')
    def options(x_session_token:str|None=Header(default=None)):
        s.require_permission('admin',x_session_token);return DATA
    @app.get('/api/locations/postal')
    def postal(country_code:str,postal_code:str,x_session_token:str|None=Header(default=None)):
        s.require_permission('admin',x_session_token);code=country(country_code);postal=postal_code.strip().upper()
        if code not in {c['code'] for c in DATA['countries']} or not re.fullmatch('[A-Z0-9][A-Z0-9 -]{1,11}',postal):raise HTTPException(400,'Select a country and enter a valid postal code')
        return postal_lookup(code,postal)
