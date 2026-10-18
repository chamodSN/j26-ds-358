/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07090D",
          900: "#0B0E14",
          800: "#10151D",
          700: "#171E29",
          600: "#222B39",
        },
        fog: {
          100: "#E8ECF2",
          300: "#B4BDCB",
          500: "#7C8798",
          700: "#4B5565",
        },
        volt: {
          300: "#DBFF8A",
          400: "#C8FF4D",
          500: "#A8E81F",
        },
        aqua: { 400: "#4DE1FF" },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      keyframes: {
        aurora: {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "33%": { transform: "translate3d(6%,-8%,0) scale(1.15)" },
          "66%": { transform: "translate3d(-7%,5%,0) scale(0.95)" },
        },
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(-50%)" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        pulseRing: {
          "0%": { transform: "scale(0.8)", opacity: "0.8" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
      },
      animation: {
        aurora: "aurora 18s ease-in-out infinite",
        "aurora-slow": "aurora 28s ease-in-out infinite reverse",
        marquee: "marquee 60s linear infinite",
        shimmer: "shimmer 1.8s linear infinite",
        "pulse-ring": "pulseRing 1.8s ease-out infinite",
      },
    },
  },
  plugins: [],
};