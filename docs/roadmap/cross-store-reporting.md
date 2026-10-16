# Consolidated brand and store reporting

Status: MERGED AND DEPLOYED at `ab3a75663f7b2dcd268707df27f2d656b6bf3240` with explicit user approval on 16 October 2026.
Priority: P2 (development authorized on 15 October 2026)

## Scope
Provide dashboards and exports across authorized stores with brand-level rollups and store-level drilldowns for revenue, orders, turnaround and exceptions.

## Acceptance criteria
Brand admins see only their brand; filters by time/store/status; totals reconcile with operational data; exports obey permissions.

## Boundaries
- Target only mahendraek/FabClean-SaaS; never modify original FabClean.
- Maintain web and mobile support.
- Implementation and validation evidence: [PR #12 notes](../PR12_IMPLEMENTATION.md).
- Do not merge until implementation and explicit approval.

Release: both Render services verified live at the approved merge; 15 read-only public smoke checks passed. See [release evidence](../DEPLOYMENT_STATUS.md).
