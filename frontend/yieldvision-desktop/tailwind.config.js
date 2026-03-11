/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "yv-deep":   "#1B2727",
        "yv-forest": "#3C5148",
        "yv-olive":  "#6B8E4E",
        "yv-sage":   "#B2C5B2",
        "yv-mist":   "#D5DDDF",
      },
      borderRadius: {
        "2xl": "16px",
        "3xl": "24px",
        "4xl": "32px",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "sans-serif"],
      },
      keyframes: {
        glowPulse: {
          "0%, 100%": { filter: "drop-shadow(0 0 6px rgba(178,197,178,0.4))" },
          "50%":      { filter: "drop-shadow(0 0 12px rgba(178,197,178,0.75))" },
        },
        fadeUp: {
          "0%":   { opacity: 0, transform: "translateY(8px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        slideIn: {
          "0%":   { opacity: 0, transform: "translateX(24px)" },
          "100%": { opacity: 1, transform: "translateX(0)" },
        },
      },
      animation: {
        "glow-pulse": "glowPulse 2.5s ease-in-out infinite",
        "fade-up":    "fadeUp 0.25s ease-out",
        "slide-in":   "slideIn 0.22s ease-out",
      },
    },
  },
  plugins: [],
};
