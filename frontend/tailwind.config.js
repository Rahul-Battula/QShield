/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#080a0f",
          900: "#0b0e14",
          850: "#10141d",
          800: "#151a25",
          700: "#1e2532",
          600: "#2b3342",
        },
        fg: { DEFAULT: "#e8ebf1", muted: "#9aa3b2", faint: "#626b7c" },
        brand: { DEFAULT: "#5bb0ff", dim: "#3d7fd6", glow: "#8fd0ff" },
        crit: "#ff6b6b",
        high: "#ffb454",
        med: "#e9d16b",
        ok: "#5fd08a",
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', '"Cascadia Code"', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
        glow: "0 0 0 1px rgba(91,176,255,0.25), 0 8px 30px -8px rgba(91,176,255,0.25)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: 0, transform: "translateY(6px)" }, "100%": { opacity: 1, transform: "none" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-up": "fade-up .28s ease both",
        shimmer: "shimmer 1.4s infinite",
      },
    },
  },
  plugins: [],
};
