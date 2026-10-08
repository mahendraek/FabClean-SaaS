# FabClean

FabClean is a configurable laundry operations and customer management platform for laundromats, dry cleaners, shoe/bag/curtain cleaning businesses, and related garment-care services.

## Architecture
- Frontend: Expo + React Native + Expo Router (Web, iOS, Android)
- Backend: FastAPI
- Database: MongoDB
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
