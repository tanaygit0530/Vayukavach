/** @type {import('tailwindcss').Config} */
// Design tokens: docs/SPEC.md "Implementation spec (latest design)". Values live in CSS
// variables (src/index.css) so themes (e.g. heat levels) can switch them at runtime.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        dot: ['"DotGothic16"', 'monospace'],
      },
      fontWeight: { light: '300', normal: '400', medium: '500', semibold: '600' },
      colors: {
        ink: { DEFAULT: 'var(--text)', muted: 'var(--text-muted)' },
        accent: 'var(--accent)',
        page: 'var(--page-bg)',
        stale: 'var(--stale)',
        aqi: {
          good: 'var(--aqi-good)',
          satisfactory: 'var(--aqi-satisfactory)',
          moderate: 'var(--aqi-moderate)',
          poor: 'var(--aqi-poor)',
          verypoor: 'var(--aqi-verypoor)',
          severe: 'var(--aqi-severe)',
        },
      },
      borderRadius: { card: '26px', bubble: '9999px' },
      boxShadow: {
        card: '0 8px 30px rgba(23,33,43,0.07)',
        bubble: '0 10px 40px rgba(23,33,43,0.10)',
      },
      backdropBlur: { card: '14px', bubble: '10px' },
      spacing: { rail: '74px', touch: '44px' },
      minHeight: { touch: '44px' },
      minWidth: { touch: '44px' },
    },
  },
  plugins: [],
}
