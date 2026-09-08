import type { AgentFace } from "./agentPersonas";
import { hexToRgba } from "./agentPersonas";

/** React port of the source prototype's avatarFace() SVG string-builder --
 * a small, deterministic procedural face per agent (NOT a real-person
 * likeness), keyed off face.style. */
function HairLayer({ face }: { face: AgentFace }) {
  switch (face.style) {
    case "glasses":
      return (
        <>
          <path d="M14 20c0-7 6-11 18-11s18 4 18 11" fill={face.hair} />
          <rect x="17" y="27" width="12" height="9" rx="4.5" fill="none" stroke="#222" strokeWidth="1.6" />
          <rect x="35" y="27" width="12" height="9" rx="4.5" fill="none" stroke="#222" strokeWidth="1.6" />
          <path d="M29 31h6" stroke="#222" strokeWidth="1.6" />
        </>
      );
    case "beard":
      return (
        <>
          <path d="M15 22c0-8 6-12 17-12s17 4 17 12" fill={face.hair} />
          <path
            d="M20 36c1 9 5 13 12 13s11-4 12-13c-4 3-8 4-12 4s-8-1-12-4z"
            fill={face.hair}
            opacity={0.85}
          />
        </>
      );
    case "wave":
      return (
        <path
          d="M14 24c0-9 7-14 18-14s18 5 18 14c-3-4-6-6-9-5-2-4-6-5-9-4-4-1-7 0-9 4-3-1-6 1-9 5z"
          fill={face.hair}
        />
      );
    case "short":
      return (
        <path
          d="M15 22c0-8 6-13 17-13s17 5 17 13c-3-3-7-5-17-5s-14 2-17 5z"
          fill={face.hair}
        />
      );
    case "longhair":
      return (
        <path
          d="M13 25c0-10 7-16 19-16s19 6 19 16v14c-3 2-5-2-5-6-2 3-4 4-4 1V17c-6-3-14-3-20 0v17c0 3-2 2-4-1 0 4-2 8-5 6z"
          fill={face.hair}
        />
      );
    case "visor":
      return (
        <>
          <path d="M15 21c0-7 6-11 17-11s17 4 17 11" fill={face.hair} />
          <rect x="16" y="24" width="32" height="7" rx="3.5" fill={face.acc} opacity={0.9} />
        </>
      );
    default:
      return (
        <path
          d="M15 22c0-8 6-13 17-13s17 5 17 13c-3-4-7-6-17-6s-14 2-17 6z"
          fill={face.hair}
        />
      );
  }
}

export function AgentAvatar({
  face,
  color,
  size = 44,
  showCheck = false,
}: {
  face: AgentFace;
  color: string;
  size?: number;
  showCheck?: boolean;
}) {
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
        <circle cx="32" cy="32" r="32" fill={hexToRgba(color, 0.16)} />
        <circle cx="32" cy="30" r="16" fill={face.skin} />
        <path d="M20 52c1-7 6-10 12-10s11 3 12 10z" fill={face.acc} />
        <circle cx="26" cy="31" r="1.7" fill="#3a2f2a" />
        <circle cx="38" cy="31" r="1.7" fill="#3a2f2a" />
        <path d="M28 37c2 1.5 6 1.5 8 0" stroke="#b98a63" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <HairLayer face={face} />
      </svg>
      {showCheck && (
        <span
          className="absolute -bottom-0.5 -right-0.5 grid place-items-center rounded-full border-2 border-panel text-[11px] font-black text-white"
          style={{ width: size * 0.24, height: size * 0.24, minWidth: 18, minHeight: 18, background: "var(--c-green)" }}
        >
          ✓
        </span>
      )}
    </div>
  );
}
