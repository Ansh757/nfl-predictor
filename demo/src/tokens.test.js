import fs from 'fs';
import path from 'path';

/**
 * Every colour class a component uses must resolve to a token that exists.
 *
 * This is the test that should have existed before the redesign renamed the
 * palette. `AccuracyChart` kept using `fill-mist` and `stroke-ink-700` after
 * those tokens were deleted, so Tailwind stopped generating the rules, the SVG
 * fell back to a default black fill, and the backtest numbers were invisible on
 * a dark background. Nothing failed - not the build, not the tests, not the
 * type checker, because there is none. It was only visible by looking.
 *
 * The failure mode is worse than a crash: `slate-500` and `red-400` are still
 * real Tailwind defaults, so a stale class can keep rendering in the *old*
 * palette's colours and simply stop following the theme.
 */
const SRC = path.join(__dirname);
const CONFIG = fs.readFileSync(path.join(__dirname, '..', 'tailwind.config.js'), 'utf8');

/** Colour utilities, with their optional shade and opacity modifier. */
const COLOUR_CLASS = /\b(bg|text|fill|stroke|border|ring|from|via|to)-([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\b/g;

/**
 * Names Tailwind provides that this project deliberately still uses, plus the
 * structural keywords that are not colours at all.
 */
const BUILT_IN = new Set([
  'white', 'black', 'transparent', 'current', 'inherit', 'none',
  // Structural values that share the utility prefixes above.
  'x', 'y', 'left', 'right', 'top', 'bottom', 'center', 'start', 'end', 'auto',
  'sm', 'md', 'lg', 'xl', 'full', 'px', 'wide', 'wider', 'widest', 'tight',
  'clip', 'ellipsis', 'nowrap', 'balance', 'pretty', 'left-4', 'solid', 'dashed',
]);

const tokensFromConfig = () => {
  const tokens = new Set();
  for (const [, name] of CONFIG.matchAll(/withAlpha\('([a-z-]+)'\)/g)) {
    tokens.add(name);
  }
  // Nested groups: surface.elevated -> surface-elevated, and the bare group name.
  for (const [, group] of CONFIG.matchAll(/^\s{8}([a-z]+): \{/gm)) tokens.add(group);
  for (const [, key] of CONFIG.matchAll(/^\s{10}([A-Za-z]+): withAlpha/gm)) {
    tokens.add(key.toLowerCase());
  }
  return tokens;
};

const componentFiles = () => {
  const found = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.jsx$/.test(entry.name)) found.push(full);
    }
  };
  walk(path.join(SRC, 'components'));
  found.push(path.join(SRC, 'App.js'));
  return found;
};

/** Build the set of names a colour utility may legitimately use. */
const allowed = () => {
  const tokens = tokensFromConfig();
  const names = new Set(BUILT_IN);
  for (const token of tokens) {
    names.add(token);
    // surface-elevated, content-muted, accent-hover, accent-on ...
    for (const suffix of ['elevated', 'selected', 'strong', 'secondary', 'muted', 'hover', 'on']) {
      names.add(`${token}-${suffix}`);
    }
  }
  return names;
};

describe('theme tokens', () => {
  const names = allowed();

  test('the config defines the tokens the design depends on', () => {
    for (const token of ['background', 'surface', 'edge', 'content', 'accent',
      'success', 'warning', 'danger', 'opposing']) {
      expect(names.has(token)).toBe(true);
    }
  });

  test.each(componentFiles().map((file) => [path.relative(SRC, file), file]))(
    '%s uses only colours that exist',
    (_relative, file) => {
      const source = fs.readFileSync(file, 'utf8');
      const unknown = new Set();

      for (const [, , name] of source.matchAll(COLOUR_CLASS)) {
        // Strip an opacity modifier: accent/40 -> accent
        const base = name.split('/')[0];
        if (names.has(base)) continue;
        // Directional width utilities share the prefixes - border-t-0 sets a
        // top border width, not a colour.
        if (/^[trblxyse]-\d/.test(base)) continue;
        // Anything with a numeric shade is a leftover from the old ramp -
        // slate-500, ink-700, red-400. Those are exactly what this catches.
        if (/-\d+$/.test(base) || ['mist', 'ink', 'caution', 'positive', 'insight'].includes(base)) {
          unknown.add(base);
        }
      }

      expect([...unknown]).toEqual([]);
    }
  );
});
