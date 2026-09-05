import fs from 'fs';
import path from 'path';

/**
 * Contrast guard for the palette.
 *
 * Values are parsed from index.css rather than duplicated here, so the test
 * cannot drift from what actually ships. Both themes are checked against every
 * surface a token is used on, because a colour that reads on the page and
 * disappears on an elevated card is still a bug.
 */
const css = fs.readFileSync(path.join(__dirname, 'index.css'), 'utf8');

const blockFor = (selector) => {
  const start = css.indexOf(selector);
  if (start === -1) throw new Error(`no ${selector} block in index.css`);
  return css.slice(start, css.indexOf('}', start));
};

const paletteOf = (selector) => {
  const palette = {};
  for (const [, token, channels] of blockFor(selector).matchAll(/--([\w-]+):\s*([\d\s]+);/g)) {
    palette[token] = channels.trim().split(/\s+/).map(Number);
  }
  return palette;
};

const DARK = paletteOf(':root {');
const LIGHT = paletteOf(":root[data-theme='light']");

const luminance = ([r, g, b]) =>
  [r, g, b]
    .map((channel) => channel / 255)
    .map((channel) => (channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4))
    .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);

const contrast = (fg, bg) => {
  const [light, dark] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
};

const AA_TEXT = 4.5;
const AA_LARGE = 3;
const SURFACES = ['background', 'surface', 'surface-elevated'];
const TEXT = ['text-primary', 'text-secondary', 'text-muted'];
const STATUS = ['accent', 'success', 'warning', 'danger'];

describe.each([['dark', DARK], ['light', LIGHT]])('%s theme', (name, palette) => {
  test('defines every token the other theme defines', () => {
    expect(Object.keys(palette).sort()).toEqual(Object.keys(name === 'dark' ? LIGHT : DARK).sort());
  });

  test.each(TEXT.flatMap((token) => SURFACES.map((surface) => [token, surface])))(
    '%s is legible on %s',
    (token, surface) => {
      expect(contrast(palette[token], palette[surface])).toBeGreaterThanOrEqual(AA_TEXT);
    }
  );

  test.each(STATUS)('%s is legible as a status colour on a card', (token) => {
    expect(contrast(palette[token], palette.surface)).toBeGreaterThanOrEqual(AA_LARGE);
  });

  test('an accent button carries its own label', () => {
    // The specified accent takes white text at only 3.73:1, under AA. Rather
    // than change the colour, the label is darkened - so this asserts the pair,
    // not a hardcoded white.
    expect(contrast(palette['on-accent'], palette.accent)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  test('the three layers actually read as three layers', () => {
    /*
     * Not merely "different values" - that passed while every section
     * dissolved into the one behind it. The burgundy stepped 1.06 and 1.08
     * between adjacent surfaces, and a set of greens proposed to fix it
     * stepped 1.07 and 1.08: flatter than the problem. A hue swap does not
     * produce depth; a luminance step does.
     */
    const MIN_STEP = 1.12;
    expect(contrast(palette.background, palette.surface)).toBeGreaterThanOrEqual(MIN_STEP);
    expect(contrast(palette.surface, palette['surface-elevated'])).toBeGreaterThanOrEqual(MIN_STEP);
  });

  test('the two halves of a win-probability bar are distinguishable', () => {
    /*
     * The gap no other assertion covers. Every check above compares text
     * against a surface; this compares two fills against each other, which is
     * where a recolour actually breaks. With a blue accent the losing half
     * could be text-muted and read fine; against a green accent that lands at
     * 1.0:1 and the 39/61 split simply vanishes.
     */
    expect(contrast(palette.opposing, palette.accent)).toBeGreaterThanOrEqual(2);
  });

  test('borders are visible against the surfaces they divide', () => {
    // A border that cannot be seen is not doing the job the design asks of it.
    expect(contrast(palette['border-subtle'], palette.surface)).toBeGreaterThan(1.15);
    expect(contrast(palette['border-strong'], palette.surface))
      .toBeGreaterThan(contrast(palette['border-subtle'], palette.surface));
  });
});

describe('theme structure', () => {
  test('dark is the default, light is the opt-in', () => {
    // The bare :root block is what a page with no data-theme attribute gets.
    expect(css.indexOf(':root {')).toBeLessThan(css.indexOf("[data-theme='light']"));
    expect(blockFor(':root {')).toContain('color-scheme: dark');
  });

  test('reduced motion is respected', () => {
    expect(css).toContain('prefers-reduced-motion');
  });

  test('focus is visible', () => {
    expect(css).toContain(':focus-visible');
  });
});

/**
 * The matchup card tints the winner's half with the accent at low alpha, which
 * composites a new background under text whose contrast nothing else here
 * measures. That is the same gap that let `--opposing` ship at 1.0:1 against
 * the accent: every other assertion in this file compares a text token against
 * a *declared* surface, and a colour that only exists after compositing is
 * invisible to all of them.
 *
 * TINT_ALPHA must track the value in MatchupCard.jsx. Raising it there without
 * raising it here would leave the tint unmeasured again.
 */
const TINT_ALPHA = 0.14;

const over = (fg, bg, alpha) =>
  fg.map((channel, index) => bg[index] + (channel - bg[index]) * alpha);

describe.each([['dark', DARK], ['light', LIGHT]])('%s theme card tint', (name, palette) => {
  const tinted = () => over(palette.accent, palette.surface, TINT_ALPHA);

  test.each(TEXT)('%s stays legible over the tinted half of a card', (token) => {
    expect(contrast(palette[token], tinted())).toBeGreaterThanOrEqual(AA_TEXT);
  });

  test('the tint reads as a lean, not as a highlighted row', () => {
    // Strong enough to see, weak enough that the card still looks like one
    // surface. Past about 1.35 it stops being a tint and starts being a second
    // panel butted against the first.
    const step = contrast(tinted(), palette.surface);
    expect(step).toBeGreaterThan(1.04);
    expect(step).toBeLessThan(1.35);
  });

  test('the tint has more headroom than the page layers it sits between', () => {
    // If the tint were flatter than the background/surface step, it would be
    // asking a reader to see a difference finer than the one the whole layering
    // pass existed to fix.
    expect(contrast(tinted(), palette.surface))
      .toBeGreaterThan(contrast(palette.background, palette.surface));
  });
});
