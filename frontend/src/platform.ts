export const FEATURE_LABELS = { offers: "Offers", rewards: "Rewards", referrals: "Referrals", subscriptions: "Recurring subscriptions", pickup: "Pickup booking", delivery: "Delivery booking", handoffs: "Store handoffs", ai: "AI assistance", reports: "Financial reports" };
export type Feature = keyof typeof FEATURE_LABELS;
export type Entitlements = { plan_code: string; features: Record<Feature, boolean>; limits: { stores: number | null; staff: number | null } };
export type Overrides = { features?: Partial<Record<Feature, boolean>>; limits?: Partial<Entitlements["limits"]> };
export function parseLimit(value: string): number | null {
  if (!value.trim()) return null;
  if (!/^\d+$/.test(value.trim())) throw new Error("Limits must be whole numbers, or blank for unlimited.");
  const number = Number(value);
  if (number < 1 || number > 10000) throw new Error("Limits must be between 1 and 10,000.");
  return number;
}
export function selectedFeatures(plan: Entitlements, overrides: Overrides): Record<Feature, boolean> {
  return { ...plan.features, ...overrides.features };
}
// Drop credential parameters on every navigation level while keeping route keys.
export function cleanInviteNavigation<T>(state: T): T {
  return JSON.parse(JSON.stringify(state, (key: string, value: unknown) => {
    if (key === "params" && value && typeof value === "object") {
      const { "#": fragment, token, ...rest } = value as Record<string, unknown>;
      return rest;
    }
    if (key === "path" && typeof value === "string") return value.split("#")[0];
    return value;
  })) as T;
}
