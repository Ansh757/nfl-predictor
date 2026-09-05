import { reasoningPoints } from './utils/reasoning';

/**
 * Splitting agent reasoning back into the factors it was built from.
 *
 * The strings below are real responses from the production service, kept
 * verbatim. They are full of decimals - spreads, impact scores, an overround -
 * and a naive split on "." tears every one of them in half, which is the whole
 * reason this has its own tests.
 */
const REAL = {
  market: 'Consensus of 9 sportsbooks. Seattle Seahawks favored by 3.5. Fair moneyline gives '
    + 'Seattle Seahawks a 63% win probability. Vig removed (overround 1.043).',
  elo: 'Elo Seattle Seahawks 1662 vs New England Patriots 1613. Teams are closely rated. '
    + 'Home field is worth 65 Elo points. Implied win probability 66%.',
  injury: 'Seattle Seahawks 12 injuries (impact 0.45), New England Patriots 8 (impact 0.33). '
    + 'New England Patriots is the healthier side. Edge to New England Patriots.',
  travel: 'New England Patriots travelling 2,485 miles. New England Patriots crossing 3 '
    + 'timezone(s) westward. Situational edge to Seattle Seahawks.',
};

describe('splitting real agent reasoning', () => {
  test('recovers the factors the market agent listed', () => {
    expect(reasoningPoints(REAL.market)).toEqual([
      'Consensus of 9 sportsbooks',
      'Seattle Seahawks favored by 3.5',
      'Fair moneyline gives Seattle Seahawks a 63% win probability',
      'Vig removed (overround 1.043)',
    ]);
  });

  test('keeps decimals intact', () => {
    // The failure this guards: "favored by 3" / "5" as two bullets.
    const points = reasoningPoints(REAL.market);
    expect(points.some((p) => p.includes('3.5'))).toBe(true);
    expect(points.some((p) => p.includes('1.043'))).toBe(true);
    expect(points).not.toContain('5');
  });

  test('keeps a parenthesised decimal pair together', () => {
    const [first] = reasoningPoints(REAL.injury);
    expect(first).toBe(
      'Seattle Seahawks 12 injuries (impact 0.45), New England Patriots 8 (impact 0.33)'
    );
  });

  test('handles ratings and percentages', () => {
    expect(reasoningPoints(REAL.elo)).toEqual([
      'Elo Seattle Seahawks 1662 vs New England Patriots 1613',
      'Teams are closely rated',
      'Home field is worth 65 Elo points',
      'Implied win probability 66%',
    ]);
  });

  test('handles a thousands separator and a parenthesised word', () => {
    const points = reasoningPoints(REAL.travel);
    expect(points[0]).toBe('New England Patriots travelling 2,485 miles');
    expect(points[1]).toBe('New England Patriots crossing 3 timezone(s) westward');
  });
});

describe('behaviour at the edges', () => {
  test('an empty or missing reasoning yields nothing to render', () => {
    expect(reasoningPoints(undefined)).toEqual([]);
    expect(reasoningPoints('')).toEqual([]);
    expect(reasoningPoints(null)).toEqual([]);
  });

  test('a single sentence stays whole rather than disappearing', () => {
    expect(reasoningPoints('Injury feed unavailable. No injury signal applied.'))
      .toEqual(['Injury feed unavailable', 'No injury signal applied']);
    expect(reasoningPoints('No meaningful edge')).toEqual(['No meaningful edge']);
  });

  test('takes the first phrasing when alternatives are pipe-separated', () => {
    expect(reasoningPoints('Primary read. Second factor. | Alternative phrasing.'))
      .toEqual(['Primary read', 'Second factor']);
  });

  test('caps the list so one verbose agent cannot dominate the row', () => {
    const long = Array.from({ length: 9 }, (_, i) => `Factor ${i + 1}`).join('. ') + '.';
    expect(reasoningPoints(long)).toHaveLength(4);
    expect(reasoningPoints(long, 2)).toHaveLength(2);
  });

  test('is not fooled by a non-string', () => {
    expect(reasoningPoints({ reasoning: 'x' })).toEqual([]);
    expect(reasoningPoints(42)).toEqual([]);
  });
});
