/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#070b16',
          soft: '#0b1120',
          panel: '#0f172a',
          raised: '#141d33',
          hover: '#1a2540',
        },
        line: {
          DEFAULT: '#1f2b48',
          soft: '#172038',
          bright: '#2b3b63',
        },
        brand: {
          50: '#eefdf6',
          100: '#d6f9e9',
          200: '#aff2d6',
          300: '#79e6bd',
          400: '#3fd39f',
          500: '#16b884',
          600: '#0a946b',
          700: '#0a7657',
          800: '#0c5d47',
          900: '#0c4c3b',
        },
        helix: {
          cyan: '#22d3ee',
          blue: '#3b82f6',
          violet: '#8b5cf6',
          pink: '#ec4899',
          amber: '#f59e0b',
          red: '#ef4444',
          green: '#22c55e',
          slate: '#94a3b8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(34,211,238,0.14), 0 8px 30px -12px rgba(34,211,238,0.35)',
        'glow-green': '0 0 0 1px rgba(22,184,132,0.18), 0 10px 30px -14px rgba(22,184,132,0.4)',
        card: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 12px 30px -18px rgba(0,0,0,0.8)',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { boxShadow: '0 0 0 0 rgba(34,211,238,0.5)' },
          '70%': { boxShadow: '0 0 0 10px rgba(34,211,238,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(34,211,238,0)' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'dash': {
          to: { strokeDashoffset: '-16' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.8s cubic-bezier(0.4,0,0.6,1) infinite',
        'fade-in': 'fade-in 0.35s ease-out',
        'slide-in': 'slide-in 0.3s ease-out',
        dash: 'dash 1s linear infinite',
        shimmer: 'shimmer 1.6s infinite',
      },
    },
  },
  plugins: [],
}
