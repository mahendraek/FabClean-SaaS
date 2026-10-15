# PR #13 — receipt and garment-tag printing

Status: IMPLEMENTED / LOCALLY VALIDATED, authorized 15 October 2026. Based on accepted main `6de9507`; independent of unmerged PR #12.

Scope: store-scoped validated printer profiles, 58/80 mm and A4 receipts, safe print previews, physical garment/order tags, ZPL/TSPL downloads, calibration and explicit staff-confirmed print auditing. Preserve financial amounts/currency, archived invoices and tenant/store isolation. Browser/system drivers handle physical printing; vendor bridges, direct USB/Bluetooth transport, cash drawers and payment terminals are outside this PR.

Acceptance: preview/download/cancel never increment print counts; only explicit staff confirmation does, with idempotent retries. Foreign orders/garments are rejected. Barcodes retain original identifiers and fit selected media or fail clearly. No arbitrary printer commands from customer/service data. Web and mobile web must work; native clients must report unsupported system printing explicitly and support command sharing where available. Physical printer acceptance requires the actual model/media.

Do not merge or deploy without explicit approval.

Validation: 155 backend tests without skips, 41 frontend tests, TypeScript, 32-route web export, eight desktop/mobile suites and a zero-error 160-request load gate. See [implementation notes](../PR13_IMPLEMENTATION.md).
