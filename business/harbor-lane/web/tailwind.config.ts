import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        harbor: {
          50: "#f0f7fa",
          100: "#dbeef5",
          200: "#b8dde9",
          300: "#86c4d6",
          400: "#4fa3bc",
          500: "#3587a3",
          600: "#2d6d87",
          700: "#295a6f",
          800: "#284b5c",
          900: "#25404e",
          950: "#152935",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
