/** @type {import('tailwindcss').Config} */
module.exports = {
  // Every class the dashboard uses is written literally in these files, so the
  // scan below is what keeps the generated stylesheet small.
  content: ['./src/**/*.{js,jsx}', './public/index.html'],
  theme: { extend: {} },
  plugins: []
};
