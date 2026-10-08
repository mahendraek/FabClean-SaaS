# FabClean Functional Specification V1

## Product
FabClean is a configurable laundry operations and customer-management platform for laundromats, dry cleaners, shoe, bag, curtain and household-item cleaning businesses.

## V1 Core
- Walk-in/drop-off as the default fulfillment flow.
- Pickup and delivery independently enabled/disabled by admin.
- Configurable service categories, services, variants, modifiers and pricing.
- Pricing types: per item, lb, kg, pair, panel, flat, starting-at and quote.
- Order and item barcode identification.
- USB/manual barcode lookup in V1; mobile-camera scanner integrates with the same barcode endpoint.
- Inspection notes, stains, damage, special instructions and photos.
- Offers, promo codes, rewards, referrals and subscription definitions.
- Manual payment method/status tracking.
- Owner, manager, counter, processing and driver roles.
- Basic reports.
- Multi-tenant and multi-location-ready architecture.

## Seed Services
Laundry, dry cleaning, shoes, bags, curtains and household/bedding are included as seed data. Administrators must be able to create new services without code changes.

## Walk-in lifecycle
Created -> Received -> Inspection -> Cleaning -> Quality Check -> Ready for Pickup -> Collected -> Completed.

## Pickup/delivery lifecycle
Pickup Scheduled -> Driver Assigned -> Picked Up -> Received -> Inspection -> Cleaning -> Quality Check -> Ready for Delivery -> Out for Delivery -> Delivered -> Completed.

## Phase 2
Physical POS terminals, cash drawer, receipt printers, garment tag printers, heat-seal barcode printers, online payments, Apple Pay/Google Pay, gift cards, refunds, automated subscription billing, advanced route optimization, live driver tracking, proof of delivery, SMS/WhatsApp/push, staff clock-in/out, QuickBooks/Xero and stronger multi-location operations.

## Phase 3+
Washer/dryer integrations and telemetry, payroll, smart lockers, advanced plant management, automated assembly, complex multi-store management, advanced marketing automation, AI receptionist and RFID.

This file is the repository implementation baseline. Deferred features must remain in the roadmap unless explicitly removed through a future scope decision.
