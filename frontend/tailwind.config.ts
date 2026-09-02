import type { Config } from "tailwindcss";

// Colors ported 1:1 from the source design system
// (C:\Users\shrey\Downloads\Glassbox\GlassBox_Complete_v3(1).html :root tokens).
// Each Tailwind color points at a CSS variable in app/globals.css so the
// palette has one source of truth shared by Tailwind utilities and raw CSS.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--c-bg)",
        bg1: "var(--c-bg1)",
        bg2: "var(--c-bg2)",
        bg3: "var(--c-bg3)",
        panel: "var(--c-panel)",
        panel2: "var(--c-panel2)",
        raised: "var(--c-raised)",
        border: "var(--c-border)",
        border2: "var(--c-border2)",
        teal: "var(--c-teal)",
        teal2: "var(--c-teal2)",
        "teal-glow": "var(--c-teal-glow)",
        "teal-dim": "var(--c-teal-dim)",
        gold: "var(--c-gold)",
        "gold-dim": "var(--c-gold-dim)",
        red: "var(--c-red)",
        "red-dim": "var(--c-red-dim)",
        green: "var(--c-green)",
        "green-dim": "var(--c-green-dim)",
        blue: "var(--c-blue)",
        "blue-dim": "var(--c-blue-dim)",
        t1: "var(--c-t1)",
        t2: "var(--c-t2)",
        t3: "var(--c-t3)",
        t4: "var(--c-t4)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      spacing: {
        sp1: "4px",
        sp2: "8px",
        sp3: "12px",
        sp4: "16px",
        sp5: "20px",
        sp6: "24px",
        sp8: "32px",
        sp10: "40px",
      },
      borderRadius: {
        r1: "6px",
        r2: "10px",
        r3: "14px",
        r4: "20px",
      },
      boxShadow: {
        sm2: "0 1px 3px rgba(0,0,0,.4), 0 1px 2px rgba(0,0,0,.3)",
        md2: "0 4px 16px rgba(0,0,0,.5), 0 2px 6px rgba(0,0,0,.3)",
        lg2: "0 12px 40px rgba(0,0,0,.6), 0 4px 12px rgba(0,0,0,.4)",
        teal: "0 0 0 1px rgba(13,204,170,.25), 0 4px 20px rgba(13,204,170,.1)",
      },
      transitionTimingFunction: {
        glass: "cubic-bezier(.22,.68,0,1.2)",
      },
    },
  },
  plugins: [],
};

export default config;
