import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef8ff",
          100: "#d9efff",
          500: "#2775ff",
          600: "#1f5ddb",
          700: "#1a47a6",
        },
      },
    },
  },
  plugins: [],
};

export default config;
