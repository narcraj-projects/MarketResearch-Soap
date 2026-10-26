export const goals = ["Price my first range", "Find a positioning gap", "Check claims rivals make", "Pick my sales channel"];
export const segments = ["Let agent find out", "Everyday", "Mid-premium", "Gifting / luxe"] as const;
export type Segment = typeof segments[number];
export type BriefPayload = {
  category: string; geography: string; customer: string; objective: string; known_competitors: string[];
  preferences: { price_segment: Segment; own_price: string | null; own_weight_g: string | null; currency: "INR" };
};
export type BriefRecord = BriefPayload & { id: string; version: number; created_at: string };

export function briefPayload(form: HTMLFormElement, goal: number, segment: Segment): BriefPayload {
  const data = new FormData(form);
  const read = (name: string) => String(data.get(name) ?? "").trim();
  const competitors = read("known").split(",").map(value => value.trim()).filter(Boolean);
  if (competitors.length > 20 || competitors.some(value => value.length > 300)) throw new Error("Enter up to 20 competitor names or links, each under 300 characters.");
  return { category: read("category"), geography: read("geography"), customer: read("customer"),
    objective: read("objective") || goals[goal], known_competitors: competitors,
    preferences: { price_segment: segment, own_price: read("own_price") || null, own_weight_g: read("own_weight_g") || null, currency: "INR" } };
}

export async function saveBrief(payload: BriefPayload, key: string): Promise<BriefRecord> {
  const response = await fetch("/api/briefs", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key }, body: JSON.stringify(payload) });
  if (response.status === 401) throw new Error("Sign in to save your brief. Your form is still here.");
  if (!response.ok) throw new Error("Your brief could not be saved. Your form is still here; please try again.");
  const result: BriefRecord = await response.json();
  if (!result.id || !result.created_at) throw new Error("The save could not be confirmed. Your form is still here.");
  return result;
}
