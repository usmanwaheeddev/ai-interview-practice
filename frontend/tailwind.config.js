/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
        ink: {
          900: "#0f172a",
          700: "#334155",
          500: "#64748b",
          300: "#cbd5e1",
          100: "#f1f5f9",
        },
        success: { 50: "#f0fdf4", 600: "#16a34a", 700: "#15803d" },
        warning: { 50: "#fffbeb", 600: "#d97706", 700: "#b45309" },
        danger: { 50: "#fef2f2", 600: "#dc2626", 700: "#b91c1c" },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Inter",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      fontSize: {
        // Type scale — every screen picks from this rather than one-off sizes.
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.875rem", { lineHeight: "1.35rem" }],
        base: ["1rem", { lineHeight: "1.5rem" }],
        lg: ["1.125rem", { lineHeight: "1.65rem" }],
        xl: ["1.375rem", { lineHeight: "1.8rem" }],
        "2xl": ["1.75rem", { lineHeight: "2.15rem" }],
        "3xl": ["2.25rem", { lineHeight: "2.6rem" }],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.06), 0 1px 3px 0 rgb(15 23 42 / 0.08)",
      },
    },
  },
  plugins: [],
}
