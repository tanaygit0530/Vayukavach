/** @type {import('tailwindcss').Config} */
// Design tokens are fleshed out in Phase 4 (see docs/SPEC.md "Implementation spec").
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        dot: ['"DotGothic16"', 'monospace'],
      },
      colors: {
        ink: { DEFAULT: '#17212B', muted: '#5E6B77' },
        accent: '#1F9D55',
        aqi: {
          good: '#3BB44A',
          satisfactory: '#A5D63F',
          moderate: '#F5D547',
          poor: '#F08A3C',
          verypoor: '#E5483F',
          severe: '#9E1B32',
        },
      },
      borderRadius: { card: '26px' },
      boxShadow: { card: '0 8px 30px rgba(23,33,43,0.07)' },
    },
  },
  plugins: [],
}
