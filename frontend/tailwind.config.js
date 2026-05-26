/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0f4ff",
          100: "#e0e9ff",
          200: "#c7d7fe",
          300: "#a5b8fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
          950: "#1e1b4b",
        },
        surface: {
          DEFAULT: "#0f0f17",
          50:  "#f8f8fc",
          100: "#f0f0f8",
          200: "#e2e2f0",
          700: "#1a1a2e",
          800: "#13131f",
          900: "#0f0f17",
          950: "#08080f",
        },
      },
      fontFamily: {
        display: ["'DM Serif Display'", "Georgia", "serif"],
        body:    ["'DM Sans'", "system-ui", "sans-serif"],
        mono:    ["'JetBrains Mono'", "monospace"],
      },
      animation: {
        "fade-in":     "fadeIn 0.4s ease forwards",
        "slide-up":    "slideUp 0.4s cubic-bezier(0.16,1,0.3,1) forwards",
        "slide-right": "slideRight 0.3s cubic-bezier(0.16,1,0.3,1) forwards",
        "pulse-slow":  "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "spin-slow":   "spin 8s linear infinite",
        "glow":        "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        fadeIn:     { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:    { from: { opacity: 0, transform: "translateY(16px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        slideRight: { from: { opacity: 0, transform: "translateX(-16px)" }, to: { opacity: 1, transform: "translateX(0)" } },
        glow:       { from: { boxShadow: "0 0 20px rgba(99,102,241,0.3)" }, to: { boxShadow: "0 0 40px rgba(99,102,241,0.6)" } },
      },
      backdropBlur: { xs: "2px" },
      boxShadow: {
        "glow-brand": "0 0 30px rgba(99,102,241,0.25)",
        "glow-green": "0 0 30px rgba(16,185,129,0.25)",
        "card":       "0 1px 3px rgba(0,0,0,0.4), 0 8px 24px rgba(0,0,0,0.3)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.5), 0 16px 40px rgba(0,0,0,0.4)",
      },
    },
  },
  plugins: [],
};
