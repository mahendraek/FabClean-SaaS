# FabClean

FabClean is a configurable laundry operations and customer management platform for laundromats, dry cleaners, shoe/bag/curtain cleaning businesses, and related garment-care services.

## Architecture
- Frontend: Expo + React Native + Expo Router (Web, iOS, Android)
- Backend: FastAPI
- Database: PostgreSQL, with an in-memory development demo
- Source baseline: GoFresh architecture, separated into this repository

## V1 priorities
- Walk-in/drop-off orders
- Admin-configurable services/pricing
- Order/item barcode tracking
- Inspection, stains, damage, notes, photos
- Offers, rewards, referrals
- Optional pickup and delivery
- Basic staff/driver workflows
- Multi-tenant and multi-location-ready data model

See `docs/FUNCTIONAL_SPEC_V1.md` for the implementation baseline.

See [the development tracker](docs/DEVELOPMENT_TRACKER.md) for the sequential PR queue, current validation, and deferred roadmap. Without `DATABASE_URL`, the API runs an ephemeral in-memory demo. Database connections must use a non-superuser/non-BYPASSRLS role; see [PR #4 migration notes](docs/roadmap/tenant-data-isolation.md).
