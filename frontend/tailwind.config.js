/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#f5f5f3',
          100: '#eae8e3',
          200: '#d5d1c8',
          300: '#c8a97e',
          400: '#b8955f',
          500: '#a07d48',
          600: '#8a6b3d',
          700: '#6e5532',
          800: '#584428',
          900: '#453620',
        },
        surface: {
          50: '#fafaf8',
          100: '#f5f5f3',
          200: '#e0e0e0',
          300: '#b0b0b0',
          400: '#7a7a7a',
          500: '#4a4a4a',
          600: '#2a2a2a',
          700: '#1a1a1a',
          800: '#0f0f0f',
          900: '#0a0a0a',
        },
        accent: {
          DEFAULT: '#c8a97e',
          dim: 'rgba(200, 169, 126, 0.15)',
        },
        cover: {
          black: '#0a0a0a',
          charcoal: '#1a1a1a',
          dark: '#2a2a2a',
          green: '#4a9e6e',
          'green-dim': 'rgba(74, 158, 110, 0.1)',
          red: '#c45c5c',
          orange: '#c8956e',
          yellow: '#c8b46e',
          warm: '#fafaf8',
        },
      },
      letterSpacing: {
        'widest-plus': '0.15em',
      },
    },
  },
  plugins: [],
}
