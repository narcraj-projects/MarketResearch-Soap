import { expect, it } from 'vitest';
import { attributedNotes } from '../src/lib/attributed-notes';
import type { LiveNarrative, Source } from '../src/lib/run-types';

it('shows persisted source-claimed prices without converting them into structured numbers', () => {
  const sources = [{ id: 'a', competitor_id: 'brand-a', access_status: 'ok' }] as Source[];
  const narrative = { synthesis: { notes: [{ kind: 'source_claim', text: 'DEMO soap price INR 275', source_ids: ['a'] }] } } as LiveNarrative;
  expect(attributedNotes(narrative, sources, 'brand-a', 'prices')).toHaveLength(1);
  expect(attributedNotes(narrative, sources, 'brand-b', 'prices')).toEqual([]);
  expect(attributedNotes(narrative, sources, 'brand-a', 'ingredients')).toEqual([]);
});

it('rejects unknown, mixed-brand, unavailable and interpretation-only note bindings', () => {
  const sources = [{ id: 'a', competitor_id: 'brand-a', access_status: 'ok' }, { id: 'b', competitor_id: 'brand-b', access_status: 'ok' }] as Source[];
  const notes = [
    { kind: 'source_claim', text: 'DEMO price', source_ids: ['missing'] },
    { kind: 'source_claim', text: 'DEMO price', source_ids: ['a', 'b'] },
    { kind: 'interpretation', text: 'DEMO price', source_ids: ['a'] },
  ];
  expect(attributedNotes({ synthesis: { notes } } as LiveNarrative, sources, 'brand-a', 'prices')).toEqual([]);
});

it('shows an exact stored ingredient declaration rather than generic marketing', () => {
  const sources = [{ id: 'a', competitor_id: 'brand-a', access_status: 'ok', excerpt: 'DEMO soap.\nIngredients: olive oil, coconut oil.\nWeight: unknown' }] as Source[];
  const narrative = { synthesis: { notes: [{ kind: 'source_claim', text: 'DEMO natural ingredients', source_ids: ['a'] }] } } as LiveNarrative;
  const notes = attributedNotes(narrative, sources, 'brand-a', 'ingredients');
  expect(notes).toEqual([{ kind: 'source_claim', text: 'Verbatim listed ingredients: Ingredients: olive oil, coconut oil.', source_ids: ['a'] }]);
  expect(attributedNotes(narrative, sources, 'brand-b', 'ingredients')).toEqual([]);
});
