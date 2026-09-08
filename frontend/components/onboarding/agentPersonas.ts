// Onboarding-only "choose your agent" personas -- a deliberately SEPARATE
// system from the marketing landing page's 8 Strategy Lens personas
// (components/marketing/lensData.ts). They are fictional archetypes, same
// spirit as Strategy Lenses (NOT real investors/firms), but a distinct set
// with their own avatars/voices per an explicit product decision: this
// wizard's persona choice is purely cosmetic (it themes onboarding's
// colors, voice, and verification framing) and is NOT the same concept as
// the real per-user agent subscriptions feature (/api/me/agent-subscriptions),
// so it deliberately doesn't reuse that system's data model either.
//
// Display names use "Agent" rather than "Lens" (e.g. "The Allocation
// Agent") even though the source design used "Lens" for all six --
// several of these names/tags already exist verbatim as Strategy Lens
// personas (e.g. "The Allocation Lens" = Englander), and using the same
// name for a second, unrelated persona elsewhere in the app would be a
// real user-facing confusion, not just an internal naming nit.
export type AgentFaceStyle = "glasses" | "beard" | "wave" | "short" | "longhair" | "visor";

export type AgentFace = {
  skin: string;
  hair: string;
  acc: string;
  style: AgentFaceStyle;
};

export type AgentPersona = {
  id: string;
  name: string;
  tag: string;
  who: string;
  strategy: string;
  rank: string;
  color: string;
  face: AgentFace;
  growth: number; // 0-100, illustrative meter
  risk: number; // 0-100, illustrative meter
  note: string;
  /** GlassBox's own framing of this agent's emphasis, spoken via voice
   * when available -- not a quote attributed to any real person. */
  say: string;
  // ElevenLabs/Kokoro voice ids. Unlike the 8 Strategy Lens voices and the
  // Guide's "River" voice (each fetched live from GET /v2/voices with a
  // real ELEVENLABS_API_KEY and confirmed against this account), these 6
  // were assigned with no key available in this environment -- they're
  // long-stable public ElevenLabs premade-catalog ids (Antoni, Arnold,
  // Josh, Rachel, Bella, Domi) that predate and are independent of any
  // one account's voice library, not fetched/confirmed live this session.
  // Verify with a real key before treating them as certainly correct,
  // same bar the rest of this project holds itself to.
  elevenLabsVoiceId?: string;
  kokoroVoiceId?: string;
};

export const AGENT_PERSONAS: AgentPersona[] = [
  {
    id: "allocation",
    name: "The Allocation Agent",
    tag: "MULTI-STRAT RISK",
    who: "Balanced strategist",
    strategy: "Multi-Strategy",
    rank: "#1",
    color: "#0DCCAA",
    face: { skin: "#E8B88A", hair: "#B9C2CE", acc: "#0DCCAA", style: "glasses" },
    growth: 68,
    risk: 22,
    note: "Spreads conviction across many signals. Balances growth against drawdown so no single factor dominates the score.",
    say: "The Allocation Agent spreads conviction across many signals, balancing growth against drawdown so no single factor dominates.",
    elevenLabsVoiceId: "ErXwobaYiN019PkySvjV", // Antoni -- Well-rounded, warm (premade catalog id, not live-verified)
    kokoroVoiceId: "am_adam",
  },
  {
    id: "value",
    name: "The Value Agent",
    tag: "DEEP VALUE",
    who: "Patient value hunter",
    strategy: "Long-term value",
    rank: "#2",
    color: "#E8A020",
    face: { skin: "#E8B88A", hair: "#8A8F98", acc: "#E8A020", style: "short" },
    growth: 41,
    risk: 14,
    note: "Durable businesses at a fair price. Leans on balance-sheet strength and financial-distress signals over momentum.",
    say: "The Value Agent leans on balance-sheet strength and financial-distress signals -- durable businesses at a fair price.",
    elevenLabsVoiceId: "VR6AewLTigWG4xSOukaG", // Arnold -- Crisp, confident (premade catalog id, not live-verified)
    kokoroVoiceId: "bm_daniel",
  },
  {
    id: "quant",
    name: "The Quant Agent",
    tag: "SYSTEMATIC",
    who: "Signal-driven analyst",
    strategy: "Systematic",
    rank: "#3",
    color: "#4D7AFF",
    face: { skin: "#EAC29A", hair: "#D8DEE9", acc: "#4D7AFF", style: "beard" },
    growth: 74,
    risk: 38,
    note: "Signal over narrative. Emphasizes statistical factors like momentum and volatility, discounts qualitative story.",
    say: "The Quant Agent emphasizes statistical factors like momentum and volatility over narrative -- signal first.",
    elevenLabsVoiceId: "TxGEqnHWrfWFTfGW9XjX", // Josh -- Deep, young (premade catalog id, not live-verified)
    kokoroVoiceId: "am_liam",
  },
  {
    id: "macro",
    name: "The Macro Agent",
    tag: "GLOBAL MACRO",
    who: "Big-picture navigator",
    strategy: "Global macro",
    rank: "#4",
    color: "#8B7FE8",
    face: { skin: "#E7B98C", hair: "#C6CBD6", acc: "#8B7FE8", style: "wave" },
    growth: 59,
    risk: 44,
    note: "Reads the regime, not just the ticker. Weighs how a holding behaves across rates, inflation and market cycles.",
    say: "The Macro Agent weighs how a holding behaves across rates, inflation and market cycles -- the regime, not just the ticker.",
    elevenLabsVoiceId: "21m00Tcm4TlvDq8ikWAM", // Rachel -- Calm, clear (premade catalog id, not live-verified)
    kokoroVoiceId: "af_heart",
  },
  {
    id: "reflexive",
    name: "The Reflexive Agent",
    tag: "MOMENTUM",
    who: "Trend reader",
    strategy: "Momentum",
    rank: "#5",
    color: "#E8445A",
    face: { skin: "#F2C9A0", hair: "#3B2F2A", acc: "#E8445A", style: "longhair" },
    growth: 81,
    risk: 57,
    note: "Follows conviction and flow. Tolerates higher volatility where momentum and the longer thesis line up.",
    say: "The Reflexive Agent follows conviction and flow, tolerating higher volatility where momentum and the longer thesis line up.",
    elevenLabsVoiceId: "EXAVITQu4vr4xnSDxMaL", // Bella -- Soft, gentle (premade catalog id, not live-verified)
    kokoroVoiceId: "af_sky",
  },
  {
    id: "glassbox",
    name: "The GlassBox Agent",
    tag: "EVIDENCE-FIRST",
    who: "Neutral default",
    strategy: "Balanced default",
    rank: "#6",
    color: "#0DB87A",
    face: { skin: "#F0C49B", hair: "#2B3245", acc: "#0DB87A", style: "visor" },
    growth: 55,
    risk: 30,
    note: "The neutral, evidence-first view. All factors weighted evenly before any philosophy is applied.",
    say: "The GlassBox Agent is the neutral view -- every factor weighted evenly, every number traceable to its source.",
    elevenLabsVoiceId: "AZnzlk1XvdvUeBnXmlld", // Domi -- Strong, confident (premade catalog id, not live-verified)
    kokoroVoiceId: "af_nova",
  },
];

export const DEFAULT_AGENT_ID = AGENT_PERSONAS[0].id;

export function getAgentPersona(id: string | null | undefined): AgentPersona {
  return AGENT_PERSONAS.find((a) => a.id === id) ?? AGENT_PERSONAS[0];
}

/** Hex + alpha -> rgba() string, e.g. for --agent-dim/--agent-bd tints. */
export function hexToRgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
