/**
 * Colours resolve through CSS variables defined in src/index.css, so a theme
 * switch is one attribute on <html> rather than a second set of classes on
 * every element. The rgb(... / <alpha-value>) form is what keeps opacity
 * modifiers (bg-accent/15, border-red-500/40) working against a variable.
 *
 * Shades are declared exhaustively: extending a stock scale like `slate`
 * replaces it, so anything omitted here silently stops generating a class.
 */
const withAlpha = (token) => `rgb(var(--${token}) / <alpha-value>)`;

const scale = (name, shades) =>
  Object.fromEntries(shades.map((shade) => [shade, withAlpha(`${name}-${shade}`)]));

/** @type {import('tailwindcss').Config} */
module.exports = {
  // Every class the dashboard uses is written literally in these files, so the
  // scan below is what keeps the generated stylesheet small.
  content: ['./src/**/*.{js,jsx}', './public/index.html'],
  theme: {
    extend: {
      colors: {
        // Palette taken from the dashboard design
        ink: scale('ink', [900, 800, 700]),
        accent: withAlpha('accent'),
        positive: withAlpha('positive'),
        caution: withAlpha('caution'),
        insight: withAlpha('insight'),
        mist: withAlpha('mist'),
        slate: scale('slate', [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]),
        red: scale('red', [300, 400, 500])
      }
    }
  },
  plugins: []
};
