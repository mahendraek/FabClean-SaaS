# Design decision log

Requested by the user on 29 October 2026. Record substantive architecture, database, security, integration, deployment, and business-rule design changes here before or alongside implementation. Explain why, not just what changed. This requirement documents decisions; it does not itself authorize implementation, merge, deployment, or production configuration changes.

## Record format

- ID, title, date, and status: proposed, accepted, implemented, or superseded.
- Problem and constraints, including the user requirement.
- Decision and reasoning, supported by evidence where available.
- Alternatives considered and why they were rejected or deferred.
- Consequences: benefits, trade-offs, operational costs, risks, and limitations.
- Migration and rollback implications, including compatibility and existing data.
- Validation performed and any outstanding acceptance checks.
- Approval, implementation/PR links, and release status; distinguish each explicitly.

Retain previous records when decisions change and link the superseding record. Do not present newly inferred reasoning as the original author's documented intent.

## DD-001 — Retain PostgreSQL as FabClean-SaaS's primary database

Date: 29 October 2026. Status: recommendation to retain the implemented architecture; no database migration proposed or performed.

Problem: the user asked why PostgreSQL replaced the MongoDB mentioned in the original FabClean README, and which database best fits the applications.

Historical evidence: original FabClean commit [605394d](https://github.com/mahendraek/FabClean/commit/605394d16837bc5fba4d29fe88572f2e3609d387), dated 5 October 2026, added PostgreSQL persistence for orders, services, and settings that had previously been stored in memory. It did not migrate those records from MongoDB. Its message does not explain why PostgreSQL was chosen over MongoDB, and does not establish user approval of that choice. FabClean-SaaS inherited the PostgreSQL implementation. Subsequent tenant isolation uses forced PostgreSQL row-level security.

Current reasoning: customers, stores, orders, payments, refunds, and subscriptions have related ownership and financial consistency requirements. PostgreSQL provides transactions, foreign keys, unique/check constraints, SQL reporting, and database-enforced row-level security that fit these requirements. JSONB also supports flexible invoice snapshots and metadata without introducing another primary database.

Alternative: MongoDB supports flexible document models, transactions, indexes, and aggregation; it is not inherently unsuitable for financial applications. However, adopting it here would require redesigning the existing ownership enforcement, relationships, reporting, and database code. Its document model alone does not justify that cost for the current workload. Its distributed scaling features may be useful for a different, demonstrated workload; no such requirement has been established for FabClean.

Trade-offs: PostgreSQL requires disciplined schema migrations, query/index tuning, backups, connection management, and careful RLS configuration. JSONB should not replace relational constraints where ownership or financial integrity depends on them. Database selection does not by itself guarantee correct or secure application behavior.

Migration/rollback: retaining PostgreSQL requires no data conversion. Any future switch needs a separate decision, data reconciliation, isolation/concurrency testing, cutover plan, and recovery plan before execution.

Validation: inspected the original persistence commit and current backend/database-isolation documentation. This documentation change requires no application tests. No new database performance comparison or MongoDB benchmark was performed.

Approval and release: the user explicitly requested recording future design decisions and their reasoning. The PostgreSQL retention recommendation here is an assessment of the existing implementation, not evidence of original design approval. No application behavior, database configuration, or deployment changes are included.

## DD-002 — Brand as tenant with licensed stores and delegated branding

Date: 5 November 2026. Status: proposed design; documentation authorized, implementation not authorized.

Problem: a customer subscribes for one brand and up to three stores. SuperAdmin must provision identity/capacity and branding; Brand Admin must configure its stores and own logo/theme without exposing another brand's data.

Decision proposed: retain Brand = Tenant in shared PostgreSQL; allocate active-store capacity through platform-owned entitlements, keep brand/store operational scope and explicit memberships, and provide separate platform and brand workspaces. SuperAdmin controls canonical identity and subscription limits and can configure branding; Brand Admin branding edits are allowed for its brand by default with explicit platform locks/delegation. Document SaaS subscriptions separately from laundry-customer subscriptions.

Reasoning: current brands/stores, forced RLS, capacity checks, owner invitations and configuration inheritance already fit the example. Reusing them reduces migration and security regression risk. A customer-facing setup flow and consistent logo/theme model address UI gaps without changing ownership.

Alternatives: organization-above-brand hierarchy deferred until multi-brand contracting is required; database-per-tenant deferred because operational complexity is not justified by this scenario; client-side filtering rejected as a security boundary; SuperAdmin-only branding rejected as the default because the user also requires Brand Admin self-service; unrestricted store overrides rejected because they obscure brand identity and control.

Consequences: shared-database isolation still requires complete per-table and non-SQL access reviews. Store capacity and branding edits need atomic/revision safeguards, clear audit and accessible UI. Public branding assets must be distinguished from private operational images. Commercial lifecycle/access/retention rules remain to be finalized.

Migration/rollback: no migration is performed. Future implementation must map legacy business/location identifiers and existing logo/theme sources without changing stable ownership or old invoices, use additive changes where feasible and rehearse compatibility/rollback.

Validation: read-only source/test review, detailed in [the audit](TENANT_MANAGEMENT_AUDIT.md). No live security or regression run was performed. See [requirements and acceptance scenarios](TENANT_MANAGEMENT_REQUIREMENTS.md).

Approval/release: user requested audit and documentation only on 5 November 2026. No new feature code, production configuration, database changes, merge or deployment is included.

Documentation publication: [PR #16](https://github.com/mahendraek/FabClean-SaaS/pull/16), awaiting review. Future implementation checklist: [issue #17](https://github.com/mahendraek/FabClean-SaaS/issues/17). Publication does not approve the proposed design or implementation.
