// Every entity, value and event here is synthetic DEMO material, not research.
export type Candidate = { id: string; initial: string; name: string; tone: string; why: string; fits: string; x: number | null; y: number | null; source: string };
export const candidates: Candidate[] = [
  { id: "a", initial: "A", name: "DEMO Competitor A", tone: "lavender", why: "Small-batch cold-process bars sold direct online; closest product match.", fits: "mmmpm", x: 58, y: 18, source: "S1" },
  { id: "b", initial: "B", name: "DEMO Competitor B", tone: "turmeric", why: "Natural-ingredient story aimed at the same customer; public feedback available.", fits: "mmmmp", x: 38, y: 26, source: "S2" },
  { id: "c", initial: "C", name: "DEMO Competitor C", tone: "rose", why: "Gifting-led artisan brand on marketplaces; overlaps on price and channel.", fits: "pmmmm", x: 78, y: 40, source: "S3" },
  { id: "d", initial: "D", name: "DEMO Competitor D", tone: "mint", why: "Similar products, but no source confirmed its prices.", fits: "mpmun", x: 24, y: 52, source: "S4" },
  { id: "e", initial: "E", name: "DEMO Competitor E", tone: "stone", why: "Mostly offline maker; very little public evidence.", fits: "mnmnn", x: 62, y: 68, source: "S5" },
];
export const fitLabels = ["Product", "Customer", "Region", "Price", "Channel"];
export const fitScore = (fits: string) => [...fits].reduce((total, fit) => total + (fit === "m" ? 1 : fit === "p" ? 0.5 : 0), 0);
export const demoSources = ["DEMO A — product page", "DEMO A — about page", "DEMO B — public review example", "DEMO C — shop listing", "DEMO launch article"];
export const comparison = [
  ["Formats", "Bars, gift sets", "Bars, liquid", "Bars, shampoo bars"],
  ["Listed price", "₹120 · DEMO date", "!₹140 vs ₹160 · two DEMO sources", "₹180 · DEMO date"],
  ["Weight per bar", "100 g", "—", "100 g"],
  ["Ingredients disclosed", "Full DEMO list", "Key oils only", "Full DEMO list"],
  ["Main claims (their words)", "DEMO ingredient story", "DEMO gentle claim", "!DEMO skincare claim · flagged"],
  ["Channels", "Own site, marketplace", "Own site", "Marketplace, retail"],
  ["Positioning", "Ingredient-led", "Everyday care", "Gifting-led"],
  ["Reviewers like / dislike", "DEMO scent theme", "DEMO packaging theme", "—"],
  ["Recent launches", "DEMO gift pack", "—", "DEMO product line"],
];
export const opportunities = [
  { area: "Positioning", title: "Make ingredient disclosure easy to compare", evidence: "DEMO disclosure gaps [S1][S3]", rationale: "Clear disclosures may reduce comparison effort.", benefit: "A simpler first-purchase decision.", assumes: "Customers value transparent labels.", next: "Test two label descriptions with target customers.", tone: "lavender" },
  { area: "Pricing", title: "Test a clearly priced starter pair", evidence: "DEMO pack and price comparison [S1][S4]", rationale: "A starter pack could help customers explore the range.", benefit: "Lower decision effort without an efficacy promise.", assumes: "Customers want to try more than one bar.", next: "Validate interest in two pack-size concepts.", tone: "turmeric" },
  { area: "Product & pack", title: "Explain the gift before the ingredients", evidence: "DEMO gifting and review themes [S2][S5]", rationale: "Gift shoppers may need a clearer use occasion.", benefit: "More useful gifting information.", assumes: "The intended audience buys soap as gifts.", next: "Compare two gifting messages in a small concept test.", tone: "mint" },
];
export function demoState(value: string | string[] | undefined): "ready" | "loading" | "empty" | "error" {
  return value === "loading" || value === "empty" || value === "error" ? value : "ready";
}
