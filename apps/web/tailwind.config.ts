import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07090d",
          900: "#0b0f16",
          850: "#0f1520",
          800: "#151c2a",
          700: "#1c2536",
          600: "#263247",
        },
        mist: {
          100: "#e8edf6",
          200: "#c7d0e0",
          400: "#8b97ad",
          500: "#6b778f",
        },
        accent: {
          DEFAULT: "#2dd4bf",
          dim: "#14b8a6",
          soft: "rgba(45, 212, 191, 0.12)",
        },
        warn: "#f0b429",
        danger: "#f07178",
      },
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 40px rgba(45, 212, 191, 0.08)",
        panel: "0 20px 60px rgba(0,0,0,0.35)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
        aurora:
          "radial-gradient(ellipse 80% 50% at 20% -10%, rgba(45,212,191,0.18), transparent 55%), radial-gradient(ellipse 60% 40% at 90% 10%, rgba(56,189,248,0.10), transparent 50%), radial-gradient(ellipse 50% 30% at 50% 100%, rgba(251,191,36,0.05), transparent 50%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
