/**
 * Agent reasoning, as the bullet points it already is.
 *
 * Every agent builds its reasoning with `". ".join(parts)` - see
 * `_generate_reasoning` in each of the five. The string arriving at the UI is
 * therefore a list of discrete factors that has been flattened into a
 * paragraph, and splitting it back out recovers exactly what the agent meant to
 * say. Nothing here summarises, rewrites or infers; if the split fails, the
 * original sentence is shown whole.
 */

/**
 * Split on a full stop followed by whitespace, but only when the character
 * before it ends a word or a number.
 *
 * That lookbehind is what protects the decimals these agents are full of -
 * "favored by 3.5", "impact 0.45", "overround 1.043" - which a naive split on
 * "." would tear in half.
 */
const CLAUSE = /(?<=[a-zA-Z0-9%)\]])\.\s+/;

export function reasoningPoints(reasoning, limit = 4) {
  if (!reasoning || typeof reasoning !== 'string') return [];

  // Some agents separate alternative phrasings with " | "; the first is the
  // one that describes this prediction.
  const [primary] = reasoning.split(' | ');

  return primary
    .split(CLAUSE)
    .map((clause) => clause.trim().replace(/\.$/, ''))
    .filter(Boolean)
    .slice(0, limit);
}
