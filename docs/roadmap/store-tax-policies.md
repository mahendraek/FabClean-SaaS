# New tax functionality — PR #14 development scope

Authorized 16 October 2026, after release of reporting PR #12. This is a new implementation, not a restoration or automatic activation of removed PR #9 settings.

Starting assumption while jurisdiction/provider preference is pending: manually verified store-source rates, disabled by default. No real rates or production configuration are supplied by development. New immutable store policy versions support effective dates, named percentage components, explicit service taxation/exemption, inclusive/exclusive pricing and fee treatment. New invoices save their policy and breakdown; historical invoices stay unchanged. Server estimates/orders, proportional capped refund tax credits, receipt/WhatsApp/printing output and store-scoped reporting/CSV must reconcile. Normal brand/store/RLS permissions apply.

Automatic provider lookup, destination sourcing, legal determination of taxability/rates and tax filing are not part of the starting assumption. Confirm the first store's jurisdiction and preferred rate source before production activation. Merge/deployment require separate approval.
