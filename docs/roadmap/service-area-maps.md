# OpenStreetMap delivery coverage

Status: ACCEPTED, MERGED AND DEPLOYED at `bf41434` — both Render services live on 13 October 2026.
Priority: P2 — current sequential roadmap item.
Implementation branch: `codex/pr-10-service-area-maps`, based on accepted main `be01ff3`.
PR: https://github.com/mahendraek/FabClean-SaaS/pull/10
Implemented: 13 October 2026.
Publication: implementation `b179ec0`, planning merge `1e9147b`; both branch refs and PR #10 head verified at `1e9147b`. GitHub title/body editing returned Forbidden; review details are retained in the implementation notes.

## Delivered scope

Selected-store locations and pickup/delivery coverage on an OpenStreetMap map; opt-in radius or simple polygon zones; explicit address/pin eligibility; configurable miles/kilometres; inside/outside feedback; web/mobile-compatible controls; linked OSM/ODbL attribution. Server checks protect new and changed pickup/delivery orders and recurring generation. Existing orders retain saved assessments; unconfigured stores retain the legacy scheduling workflow until coverage is enabled.

See [design, migration, API, rollout and validation](../PR10_IMPLEMENTATION.md).

## Validation and boundaries

136 backend tests without skips, 31 frontend tests, clean TypeScript, 31-route export, six desktop/mobile browser suites and zero-error load validation pass. Forced RLS and related store/brand foreign keys protect configuration. Desktop coverage tests use controlled tiles; mobile tests verify tile failure fallback. Actual OSM tile access is blocked by the cloud proxy; the required tile/attribution domains are saved in the environment-settings draft for review. Native devices and authenticated production coverage remain unverified.

Only mahendraek/FabClean-SaaS changes. No geocoder, address autocomplete, device-location permission, driving-route distance, polygon holes or date-line-spanning zones are included. Addresses use a staff-confirmed pin; text-to-coordinate accuracy is not automatically verified. Main and both Render services include PR #10; public smoke checks pass. PR #11 and later work remains planned. The user explicitly approved merge/deployment; both are verified in [release evidence](../DEPLOYMENT_STATUS.md).
