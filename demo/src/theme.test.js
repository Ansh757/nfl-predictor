import fs from 'fs';
import path from 'path';

/**
 * Contrast guard for the palette.
 *
 * The light theme was written by mirroring the slate ramp, which is right for
 * surfaces and wrong for text - a mirrored slate-400 lands on #94A3B8, which is
 * 2.5:1 on white and unreadable. These assertions pin the text tokens to the
 * WCAG AA thresholds so a future palette edit cannot quietly regress them.
 *
 * Values are parsed from index.css rather than duplicated here, so the test
 * cannot drift from what actually ships.
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

describe.each([['dark', DARK], ['light', LIGHT]])('%s theme', (name, palette) => {
  test('defines every token the other theme defines', () => {
    expect(Object.keys(palette).sort()).toEqual(Object.keys(name === 'dark' ? LIGHT : DARK).sort());
  });

  // Text sits on the page (ink-900) or on a card (ink-800); both must hold.
  test.each(['ink-900', 'ink-800'])('body text is legible on %s', (surface) => {
    expect(contrast(palette.mist, palette[surface])).toBeGreaterThanOrEqual(AA_TEXT);
  });

  // Dim text appears on the page and on cards, so both grounds have to hold.
  test.each([
    ['slate-300', 'ink-900'], ['slate-300', 'ink-800'],
    ['slate-400', 'ink-900'], ['slate-400', 'ink-800'],
    ['slate-500', 'ink-900'], ['slate-500', 'ink-800'],
    ['slate-600', 'ink-900'], ['slate-600', 'ink-800']
  ])('%s is legible as secondary text on %s', (token, surface) => {
    expect(contrast(palette[token], palette[surface])).toBeGreaterThanOrEqual(AA_TEXT);
  });

  test.each(['accent', 'positive', 'caution', 'insight', 'red-400'])(
    '%s is legible as a status colour on a card',
    (token) => {
      expect(contrast(palette[token], palette['ink-800'])).toBeGreaterThanOrEqual(AA_LARGE);
    }
  );

  test('white on an accent button is legible', () => {
    expect(contrast([255, 255, 255], palette.accent)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  test('cards are distinguishable from the page behind them', () => {
    expect(palette['ink-800']).not.toEqual(palette['ink-900']);
  });
});
