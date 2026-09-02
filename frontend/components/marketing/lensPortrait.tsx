// Procedurally-generated SVG portraits -- ported from the portrait()/
// hairStyle()/mouthStyle()/facialHair()/shade() functions in
// docs/design-reference/GlassBox_Lenses_Interactive.html. These are
// original illustrations built from primitive shapes, NOT photos or real
// likenesses -- see the mandatory disclaimer in
// docs/design-reference/README.md rendered alongside <StrategyLenses>.
import type { LensLook } from "./lensData";

const RGB: Record<string, string> = {
  teal: "13,204,170",
  blue: "77,122,255",
  gold: "232,160,32",
  red: "232,68,90",
  purple: "164,107,255",
  green: "13,184,122",
  cyan: "34,211,238",
};

function shade(hex: string, amt: number): string {
  let c = hex.replace("#", "");
  if (c.length === 3) c = c.split("").map((x) => x + x).join("");
  let r = parseInt(c.slice(0, 2), 16);
  let g = parseInt(c.slice(2, 4), 16);
  let b = parseInt(c.slice(4, 6), 16);
  r = Math.max(0, Math.min(255, r + amt));
  g = Math.max(0, Math.min(255, g + amt));
  b = Math.max(0, Math.min(255, b + amt));
  return "#" + [r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function hairStyleSvg(style: LensLook["hairStyle"], hair: string): string {
  if (style === "short" || style === "balding") {
    if (style === "balding") {
      return `<path d="M40 46 q5 -16 20 -16 q15 0 20 16 q-9 -7 -20 -7 q-6 0 -11 2" fill="${hair}" opacity=".7"/>`;
    }
    return `<path d="M38 52 q0 -26 22 -26 q22 0 22 26 q-6 -14 -22 -14 q-16 0 -22 14" fill="${hair}"/>`;
  }
  if (style === "silver") {
    return `<path d="M38 52 q0 -26 22 -26 q22 0 22 26 q-6 -14 -22 -14 q-16 0 -22 14" fill="#C8CEDA"/>`;
  }
  return `<path d="M38 52 q0 -26 22 -26 q22 0 22 26 q-6 -14 -22 -14 q-16 0 -22 14" fill="${hair}"/>`;
}

function mouthStyleSvg(mouth: LensLook["mouth"]): string {
  const c = "#9E5A44";
  if (mouth === "warm") {
    return `<path d="M52 67 q8 7 16 0 q-8 3 -16 0" fill="#fff" stroke="${c}" stroke-width="1.4"/>`;
  }
  if (mouth === "neutral") {
    return `<path d="M54 68 h12" stroke="${c}" stroke-width="2.2" stroke-linecap="round"/>`;
  }
  return `<path d="M53 68 q7 5 14 0" stroke="${c}" stroke-width="2.2" fill="none" stroke-linecap="round"/>`;
}

function facialHairSvg(type: "beard" | undefined, color: string): string {
  if (type === "beard") {
    return `<path d="M40 60 q0 22 20 24 q20 -2 20 -24 q-6 12 -20 12 q-14 0 -20 -12" fill="${color}" opacity=".85"/>`;
  }
  return "";
}

/** Returns raw SVG markup (string) for a persona's portrait. */
export function lensPortraitMarkup(id: string, look: LensLook, colorToken: string): string {
  const rgb = RGB[colorToken] ?? RGB.teal;
  const ac = `rgb(${rgb})`;
  const acd = `rgba(${rgb},.15)`;
  const skin = look.skin;
  const skinSh = shade(look.skin, -18);
  const hair = look.hair;
  const hairSh = shade(look.hair, -20);
  const suit = look.suit;
  const suitSh = shade(look.suit, -22);
  const shirt = look.shirt || "#F4F7FF";

  return `<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
    <defs><radialGradient id="pg${id}" cx="50%" cy="30%" r="80%"><stop offset="0%" stop-color="${acd}"/><stop offset="100%" stop-color="rgba(10,15,26,.85)"/></radialGradient>
    <linearGradient id="sh${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${skin}"/><stop offset="100%" stop-color="${skinSh}"/></linearGradient></defs>
    <circle cx="60" cy="60" r="60" fill="url(#pg${id})"/>
    <path d="M18 120 q0 -30 42 -30 q42 0 42 30 z" fill="${suit}"/>
    <path d="M60 90 l-11 30 h22 z" fill="${shirt}"/><path d="M60 90 l-9 12 9 6 9 -6 z" fill="${suitSh}"/>
    ${look.tie ? `<path d="M60 96 l-4 5 4 16 4 -16 z" fill="${look.tie}"/>` : ""}
    <path d="M52 78 h16 v12 q-8 6 -16 0 z" fill="url(#sh${id})"/>
    <ellipse cx="60" cy="56" rx="22" ry="24" fill="url(#sh${id})"/>
    <circle cx="38" cy="58" r="4" fill="${skinSh}"/><circle cx="82" cy="58" r="4" fill="${skinSh}"/>
    ${hairStyleSvg(look.hairStyle, hair)}
    <path d="M48 48 q4 -2 8 -0.5" stroke="${hairSh}" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M64 47.5 q4 -1.5 8 0.5" stroke="${hairSh}" stroke-width="2" fill="none" stroke-linecap="round"/>
    ${
      look.glasses
        ? `<circle cx="52" cy="54" r="7.5" fill="#fff" opacity=".08"/><circle cx="68" cy="54" r="7.5" fill="#fff" opacity=".08"/><circle cx="52" cy="54" r="7.5" fill="none" stroke="${look.glassCol || ac}" stroke-width="2"/><circle cx="68" cy="54" r="7.5" fill="none" stroke="${look.glassCol || ac}" stroke-width="2"/><line x1="59.5" y1="54" x2="60.5" y2="54" stroke="${look.glassCol || ac}" stroke-width="2"/>`
        : ""
    }
    <ellipse cx="52" cy="54" rx="2.6" ry="3" fill="#1c2536"/><ellipse cx="68" cy="54" rx="2.6" ry="3" fill="#1c2536"/>
    <circle cx="53" cy="53" r=".9" fill="#fff"/><circle cx="69" cy="53" r=".9" fill="#fff"/>
    <path d="M60 56 l-2 8 q2 1.5 4 0" stroke="${skinSh}" stroke-width="1.6" fill="none" stroke-linecap="round"/>
    ${mouthStyleSvg(look.mouth)}${facialHairSvg(look.facialHair, hairSh)}</svg>`;
}

export function LensPortrait({ id, look, colorToken }: { id: string; look: LensLook; colorToken: string }) {
  return (
    <div
      className="h-full w-full [&>svg]:h-full [&>svg]:w-full"
      // Markup is generated entirely from the fixed LENS_PERSONAS dataset
      // (components/marketing/lensData.ts), never from user/external input.
      dangerouslySetInnerHTML={{ __html: lensPortraitMarkup(id, look, colorToken) }}
    />
  );
}
