// Persona data copied verbatim from docs/design-reference/GlassBox_Lenses_Interactive.html
// (the AGENTS array) -- names, track records, and story quotes are the
// exact source copy, not paraphrased. See docs/design-reference/README.md
// for the mandatory legal disclaimer that must ship alongside this data.

export type LensLook = {
  skin: string;
  hair: string;
  hairStyle: "short" | "balding" | "silver";
  suit: string;
  shirt?: string;
  tie?: string;
  glasses?: boolean;
  glassCol?: string;
  mouth: "confident" | "warm" | "neutral";
  facialHair?: "beard";
};

export type LensFilter = "value" | "quant" | "macro" | "multi";

export type LensPersona = {
  id: string;
  code: string;
  name: string;
  title: string;
  color: string; // Tailwind color token name, e.g. "gold"
  cls: LensFilter;
  rank: string;
  lead: boolean;
  inspiredName: string;
  firm: string;
  strat: string;
  track: string;
  growth: number;
  risk: number;
  story: string;
  look: LensLook;
};

export const LENS_FILTERS: { value: "all" | LensFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "value", label: "Value / GARP" },
  { value: "quant", label: "Quant" },
  { value: "macro", label: "Macro" },
  { value: "multi", label: "Multi-Strategy" },
];

export const LENS_PERSONAS: LensPersona[] = [
  {
    id: "buf",
    code: "V",
    name: "The Value Lens",
    title: "Value & Buy-and-Hold",
    color: "gold",
    cls: "value",
    rank: "",
    lead: true,
    inspiredName: "Buffett & Munger",
    firm: "Berkshire Hathaway",
    strat: "Value / Buy & Hold",
    track: "~20% annual, 50+ yrs",
    growth: 70,
    risk: 18,
    story:
      "I read your holdings like a business owner, not a ticker-watcher. Durable moat, honest management, cash that compounds — if the business is wonderful and the price is fair, time does the rest. I flag the ones you should never sell.",
    look: {
      skin: "#E8CBA8",
      hair: "#D8DCE4",
      hairStyle: "balding",
      suit: "#2A2416",
      shirt: "#FFFDF5",
      tie: "#E8A020",
      glasses: true,
      glassCol: "#8a6a2a",
      mouth: "warm",
    },
  },
  {
    id: "lyn",
    code: "G",
    name: "The GARP Lens",
    title: "Growth at Reasonable Price",
    color: "green",
    cls: "value",
    rank: "",
    lead: false,
    inspiredName: "Peter Lynch",
    firm: "Fidelity Magellan",
    strat: "GARP",
    track: "29.2% avg annual (1977–90)",
    growth: 86,
    risk: 34,
    story:
      "I hunt growth hiding in plain sight — the everyday company Wall Street ignored. I check the PEG, not just the P/E, so you pay a fair price for real earnings. Turn over enough rocks and the tenbagger is already in your cart.",
    look: {
      skin: "#EAC9A0",
      hair: "#E4E8EE",
      hairStyle: "silver",
      suit: "#14342E",
      shirt: "#F0FFF9",
      tie: "#0DB87A",
      mouth: "warm",
    },
  },
  {
    id: "gri",
    code: "X",
    name: "The Multi-Strat Lens",
    title: "Multi-Strategy",
    color: "teal",
    cls: "multi",
    rank: "#1 · ~$74B",
    lead: true,
    inspiredName: "Ken Griffin",
    firm: "Citadel",
    strat: "Multi-Strategy",
    track: "~$74B lifetime net gains",
    growth: 82,
    risk: 40,
    story:
      "I look at your book as many uncorrelated bets at once — equities, credit, commodities — each on a tight risk leash. My edge is not one big call; it is a hundred small ones that never blow up together.",
    look: {
      skin: "#E8B892",
      hair: "#3A3F4A",
      hairStyle: "short",
      suit: "#0E2E2A",
      shirt: "#EAFDF9",
      tie: "#0DCCAA",
      mouth: "confident",
    },
  },
  {
    id: "dal",
    code: "M",
    name: "The Macro Lens",
    title: "Global Macro / Risk Parity",
    color: "purple",
    cls: "macro",
    rank: "#2 · ~$58B",
    lead: false,
    inspiredName: "Ray Dalio",
    firm: "Bridgewater",
    strat: "Global Macro",
    track: "~$58B lifetime net gains",
    growth: 74,
    risk: 44,
    story:
      "I balance your portfolio against every economic weather — growth, inflation, both rising, both falling. I do not predict the storm; I make sure you hold up in all of them. Principles over forecasts, always.",
    look: {
      skin: "#DFB98E",
      hair: "#C8CEDA",
      hairStyle: "silver",
      suit: "#2E1E4A",
      shirt: "#F3EEFF",
      glasses: true,
      glassCol: "#5a3a8a",
      mouth: "neutral",
    },
  },
  {
    id: "sim",
    code: "Q",
    name: "The Quant Lens",
    title: "Quantitative",
    color: "cyan",
    cls: "quant",
    rank: "#3 · ~$51B",
    lead: false,
    inspiredName: "Jim Simons",
    firm: "Renaissance Tech",
    strat: "Quantitative",
    track: "~$51B lifetime net gains",
    growth: 90,
    risk: 28,
    story:
      "I see patterns in your holdings no human eye catches — faint, statistical, fleeting. I let the mathematics speak and I never override the model on a hunch. Signal, not story. Discipline, not drama.",
    look: {
      skin: "#E4C4A0",
      hair: "#D8DCE4",
      hairStyle: "silver",
      suit: "#123A44",
      shirt: "#E6FBFF",
      facialHair: "beard",
      mouth: "confident",
    },
  },
  {
    id: "eng",
    code: "A",
    name: "The Allocation Lens",
    title: "Multi-Strat Risk",
    color: "teal",
    cls: "multi",
    rank: "#4 · ~$50B",
    lead: false,
    inspiredName: "Izzy Englander",
    firm: "Millennium",
    strat: "Multi-Strategy",
    track: "~$50B lifetime net gains",
    growth: 68,
    risk: 22,
    story:
      "I treat your book like a floor of specialist teams on tight leashes. The moment a position breaches its risk limit, it gets cut — no debate, no ego. Consistency is the alpha; the drawdown you avoid is the return you keep.",
    look: {
      skin: "#D6A470",
      hair: "#C8CEDA",
      hairStyle: "silver",
      suit: "#123040",
      shirt: "#EAF6FF",
      glasses: true,
      glassCol: "#2a6a8a",
      mouth: "neutral",
    },
  },
  {
    id: "sha",
    code: "D",
    name: "The Algo Lens",
    title: "Quant / Multi-Strategy",
    color: "blue",
    cls: "quant",
    rank: "#5 · ~$43B",
    lead: false,
    inspiredName: "David Shaw",
    firm: "D.E. Shaw",
    strat: "Quant",
    track: "~$43B lifetime net gains",
    growth: 80,
    risk: 30,
    story:
      "I was doing computational finance before it had a name. Every inefficiency in your holdings is a problem to be solved with code and clean data — not intuition. If the math does not confirm it, I do not act on it.",
    look: {
      skin: "#C68642",
      hair: "#2B2B33",
      hairStyle: "short",
      suit: "#1E2A44",
      shirt: "#EAF0FF",
      tie: "#4D7AFF",
      facialHair: "beard",
      mouth: "confident",
    },
  },
  {
    id: "sor",
    code: "R",
    name: "The Reflexive Lens",
    title: "Global Macro",
    color: "red",
    cls: "macro",
    rank: "#6 · ~$41B",
    lead: false,
    inspiredName: "George Soros",
    firm: "Soros Fund Mgmt",
    strat: "Global Macro",
    track: "~$41B lifetime net gains",
    growth: 78,
    risk: 58,
    story:
      "I watch how perception bends reality in your positions — the feedback loop between what people believe and what then becomes true. When the thesis is right and the crowd is wrong, that gap is the opportunity.",
    look: {
      skin: "#E0BE98",
      hair: "#D8DCE4",
      hairStyle: "balding",
      suit: "#3A1E22",
      shirt: "#FFECEE",
      tie: "#E8445A",
      glasses: true,
      glassCol: "#8a3a3a",
      mouth: "confident",
    },
  },
];
