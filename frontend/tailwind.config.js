/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 900: "#0b0d10", 800: "#11151a", 700: "#1a2028", 600: "#262e38" },
        line: { DEFAULT: "#243042", soft: "#1a2028" },
        muted: "#7e8a9a",
        accent: { DEFAULT: "#5fa8ff", strong: "#3b82f6" },
        good: "#22c55e",
        bad: "#ef4444",
        warn: "#f59e0b",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SF Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
