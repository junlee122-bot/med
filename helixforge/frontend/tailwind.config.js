/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: '#070b16', soft: '#0b1120', panel: '#0f172a', raised: '#141d33', hover: '#1a2540' },
        line: { DEFAULT: '#1f2b48', soft: '#172038', bright: '#2b3b63' },
        brand: { 300: '#79e6bd', 400: '#3fd39f', 500: '#16b884', 600: '#0a946b' },
        helix: { cyan: '#22d3ee', blue: '#3b82f6', violet: '#8b5cf6', amber: '#f59e0b', red: '#ef4444', green: '#22c55e', slate: '#94a3b8' },
      },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'] },
    },
  },
  plugins: [],
}
