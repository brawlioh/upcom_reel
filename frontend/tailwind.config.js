/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0b1220',
          800: '#0f172a',
          700: '#1f2937',
          600: '#374151',
          500: '#4b5563',
          400: '#9ca3af'
        },
        primary: {
          700: '#1d4ed8',
          600: '#2563eb',
          500: '#3b82f6'
        }
      }
    },
  },
  plugins: [],
}
