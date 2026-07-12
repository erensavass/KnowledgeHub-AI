/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { 50: '#eef7ff', 500: '#1769aa', 600: '#12578f', 700: '#104873' },
      },
    },
  },
  plugins: [],
}
