import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        forzy: {
          bg: "#0b1120",
          panel: "#111a2e",
          border: "#1e293b",
          accent: "#22d3ee",
        },
      },
    },
  },
  plugins: [],
};

export default config;
