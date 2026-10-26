import type { LiveNarrative, Source } from './run-types';

const fields: Record<string, RegExp> = {
  products: /\bsoap|\bbar\b|\bproduct/i,
  ingredients: /\bingredient list|\bolive oil|\bcoconut oil|\bjojoba oil|\bcastor oil/i,
  prices: /₹|\bINR\b|\bprice/i,
  positioning: /\bposition|\bbrand|\bconscious|\bcertif|\bhandcraft/i,
  channels: /\bwholesale|\bretail|\be-commerce|\bdirect.to.consumer|\bboutique/i,
  packaging: /\bpackag/i,
  feedback: /\breview|\bcustomer feedback/i,
  launches: /\blaunch|\bannouncement/i,
};

/** Display only persisted, attributed notes whose every source belongs to this brand.
 * This adds no structured fact, numeric value, claim-support score or normalization.
 */
export function attributedNotes(narrative: LiveNarrative | null | undefined, sources: Source[], competitorId: string, field: string) {
  const pattern = fields[field];
  if (!pattern || !narrative) return [];
  const sourceMap = new Map(sources.map(source => [source.id, source]));
  if (field === 'ingredients') {
    // Prefer an explicit ingredient declaration in an approved stored listing,
    // rather than classifying general "natural ingredients" marketing as a list.
    const quoted = sources.filter(source => source.competitor_id === competitorId && source.access_status === 'ok')
      .flatMap(source => {
        const match = source.excerpt?.match(/\bIngredients:\s*[^\n]{1,900}/i);
        return match ? [{ kind: 'source_claim', text: 'Verbatim listed ingredients: ' + match[0], source_ids: [source.id] }] : [];
      });
    if (quoted.length) return quoted;
  }
  return narrative.synthesis.notes.filter(note => note.kind === 'source_claim' && pattern.test(note.text)
    && note.source_ids.length > 0 && note.source_ids.every(id => {
      const source = sourceMap.get(id);
      return source?.competitor_id === competitorId && source.access_status === 'ok';
    }));
}
