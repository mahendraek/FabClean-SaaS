# FabClean V1 Implementation Status

This file records the initial foundation and is not a current completion audit. Use [DEVELOPMENT_TRACKER.md](DEVELOPMENT_TRACKER.md) for the active PR queue and validation evidence. The current persistent backend is PostgreSQL, not MongoDB.

## Implemented foundation
- Separate FabClean repository
- Expo/React Native shared web + mobile frontend
- FastAPI backend
- FabClean branding and app metadata
- Laundry service data model
- Seed categories for Laundry, Dry Cleaning, Shoes, Bags, Curtains and Household
- Pricing models represented in backend model
- Walk-in/drop-off counter order flow
- Automatic order barcode ID
- Automatic item barcode IDs
- Order lookup by order number, order barcode or item barcode
- Order status API
- Configurable pickup enable/disable
- Configurable delivery enable/disable
- Rewards/offers/referrals/subscriptions feature flags
- Admin demo/settings screen
- Service catalog screen
- Netlify web deployment configuration
- Render backend deployment configuration
- V1/Phase 2/Phase 3 roadmap retained in repository documentation

## V1 still to implement
- Persistent MongoDB storage
- Authentication and role-based authorization
- Customer profile and saved addresses
- Full admin service CRUD UI
- Service variants and modifier UI
- Inspection workflow
- Stain/damage structured tags
- Photo upload and item photos
- Actual barcode image generation (Code 128)
- Barcode label printing layout
- Mobile camera barcode scanner
- Order status timeline UI
- Offers and promo-code management
- Rewards ledger and customer wallet
- Referral lifecycle and reward qualification
- Subscription plan management
- Recurring pickup scheduling
- Pickup/delivery slots and service areas
- Driver assignment and driver screens
- Manual payment status UI
- Reports dashboard
- Multi-tenant enforcement
- Multi-location enforcement
- Audit history
- Automated tests and CI
- Production deployment/environment setup

## Phase 2 and Phase 3
See docs/FUNCTIONAL_SPEC_V1.md. Deferred features remain part of the product roadmap and are not to be dropped.
