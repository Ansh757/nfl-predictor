/** @type {import('tailwindcss').Config} */
module.exports = {
  // Every class the dashboard uses is written literally in these files, so the
  // scan below is what keeps the generated stylesheet small.
  content: ['./src/**/*.{js,jsx}', './public/index.html'],
  theme: {
    extend: {
      colors: {
        // Palette taken from the dashboard design
        ink: { 900: '#0B1220', 800: '#111827', 700: '#1E293B' },
        accent: '#2563EB',
        positive: '#10B981',
        caution: '#F59E0B',
        insight: '#8B5CF6',
        mist: '#E2E8F0'
      }
    }
  },
  plugins: []
};
