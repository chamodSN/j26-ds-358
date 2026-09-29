/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F6F5F1",
        surface: "#FFFFFF",
        line: "#E7E4DC",
        ink: {
          DEFAULT: "#1B1912",
          soft: "#5B5748",
          faint: "#8C8776",
        },
        amber: {
          50: "#FBF3E4",
          100: "#F3DFB0",
          400: "#D68F1F",
          500: "#B87610",
          600: "#8F5B0C",
        },
        moss: {
          50: "#EAF2EC",
          400: "#3E8461",
          500: "#2A6B4A",
          600: "#1F5138",
        },
      },
      fontFamily: {
        display: ["Fraunces", "serif"],
        sans: ["Manrope", "system-ui", "sans-serif"],
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "16px",
      },
    },
  },
  plugins: [],
};