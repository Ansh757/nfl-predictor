/**
 * Colours resolve through the CSS variables in src/index.css, so a theme is a
 * token change rather than a second set of classes on every element. The
 * rgb(... / <alpha-value>) form is what keeps opacity modifiers working
 * against a variable.
 *
 * Names are semantic - surface, border, text - rather than a colour ramp,
 * because the two themes are not inversions of each other and a name like
 * "slate-700" stops meaning anything the moment one of them is warm.
 */
const withAlpha = (token) => `rgb(var(--${token}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx}', './public/index.html'],
  theme: {
    extend: {
      colors: {
        background: withAlpha('background'),
        surface: {
          DEFAULT: withAlpha('surface'),
          elevated: withAlpha('surface-elevated'),
          selected: withAlpha('surface-selected'),
        },
        edge: {
          DEFAULT: withAlpha('border-subtle'),
          strong: withAlpha('border-strong'),
        },
        content: {
          DEFAULT: withAlpha('text-primary'),
          secondary: withAlpha('text-secondary'),
          muted: withAlpha('text-muted'),
        },
        accent: {
          DEFAULT: withAlpha('accent'),
          hover: withAlpha('accent-hover'),
          on: withAlpha('on-accent'),
        },
        success: withAlpha('success'),
        warning: withAlpha('warning'),
        danger: withAlpha('danger'),
        // Losing half of a win-probability bar - see index.css.
        opposing: withAlpha('opposing'),
      },
      // Restrained. Nothing in a data-dense view wants a 24px corner.
      borderRadius: {
        DEFAULT: '4px',
        md: '6px',
        lg: '8px',
        xl: '10px',
      },
      fontFamily: {
        display: ['var(--font-display)'],
      },
    },
  },
  plugins: [],
};
