"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type Props = {
  tag?: string;
  title: string;
  desc: string;
  learn?: string;
  /** Optional key/value drill-down, revealed by the "learn" sub-button. */
  detail?: Record<string, string>;
  /** Show the < 1 / 1 / > 1 beta-style scale legend below the description. */
  betaScale?: boolean;
  /** Whole `children` becomes the clickable trigger (for inline source
   * labels like "Twelve Data · Live ⓘ") instead of a standalone ⓘ button
   * appended after `children`. */
  inline?: boolean;
  children?: ReactNode;
};

const PAD = 12;
const GAP = 8;
const POPOVER_WIDTH = 280;

/**
 * A single reusable explain-tooltip system: hover + focus + click to open,
 * Escape/outside-click to close, viewport-collision-aware placement (flips
 * below if there's no room above, clamps left/right), and a mobile
 * (<=560px) bottom-sheet variant instead of a floating popover. Portals to
 * document.body so it's never clipped by a parent's overflow.
 *
 * Deliberately separate from GuideBubble.tsx's simpler `GuideHint` (a
 * click-only, non-collision-aware tooltip used elsewhere in the app) --
 * this one is for surfaces (onboarding's agent picker + verification
 * step) that need the richer hover/detail/mobile behavior; GuideHint's
 * existing call sites are untouched.
 */
export function ExplainTooltip({ tag, title, desc, learn, detail, betaScale, inline, children }: Props) {
  const [open, setOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: -9999, left: -9999 });
  const triggerRef = useRef<HTMLElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setMounted(true);
    const mq = window.matchMedia("(max-width: 560px)");
    setIsMobile(mq.matches);
    const onChange = () => setIsMobile(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  function place() {
    if (isMobile || !triggerRef.current || !popRef.current) return;
    const r = triggerRef.current.getBoundingClientRect();
    const popW = Math.min(POPOVER_WIDTH, window.innerWidth - PAD * 2);
    const popH = popRef.current.offsetHeight;
    let top = r.top - popH - GAP;
    if (top < PAD) top = r.bottom + GAP; // flip below when there's no room above
    let left = r.left + r.width / 2 - popW / 2;
    if (left < PAD) left = PAD;
    if (left + popW > window.innerWidth - PAD) left = window.innerWidth - popW - PAD;
    setPos({ top, left });
  }

  useEffect(() => {
    if (!open) return;
    place();
    const onScroll = () => place();
    const onResize = () => place();
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, detailOpen, isMobile]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    function onClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (popRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("click", onClickOutside);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("click", onClickOutside);
    };
  }, [open]);

  function cancelClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }
  function scheduleClose() {
    cancelClose();
    closeTimer.current = setTimeout(() => {
      if (!popRef.current?.matches(":hover")) setOpen(false);
    }, 80);
  }
  function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    setOpen((o) => !o);
  }

  const setTriggerRef = (el: HTMLElement | null) => {
    triggerRef.current = el;
  };

  const triggerProps = {
    "aria-haspopup": "dialog" as const,
    "aria-expanded": open,
    "aria-label": title,
    onMouseEnter: () => {
      cancelClose();
      setOpen(true);
    },
    onMouseLeave: scheduleClose,
    onFocus: () => setOpen(true),
    onBlur: scheduleClose,
    onClick: handleClick,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    },
  };

  const popover = open && mounted && (
    <div
      ref={popRef}
      role="dialog"
      onMouseEnter={cancelClose}
      onMouseLeave={scheduleClose}
      className={
        isMobile
          ? "fixed inset-x-0 bottom-0 z-[999] rounded-t-r3 border-t border-border2 bg-panel px-sp5 py-sp5 pb-[calc(env(safe-area-inset-bottom)+20px)] text-t1 shadow-lg2"
          : "fixed z-[999] w-[280px] max-w-[calc(100vw-24px)] rounded-r2 border border-border2 bg-panel p-sp4 text-t1 shadow-lg2"
      }
      style={isMobile ? undefined : { top: pos.top, left: pos.left }}
    >
      {isMobile && (
        <div className="mx-auto mb-sp3 h-1 w-9 rounded-full bg-border2" aria-hidden="true" />
      )}
      {tag && (
        <span className="mb-sp2 inline-block rounded-r1 bg-teal-dim px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-teal">
          {tag}
        </span>
      )}
      <h4 className="mb-1 text-[12.5px] font-extrabold text-t1">{title}</h4>
      <p className="m-0 text-[12px] leading-relaxed text-t2">{desc}</p>
      {betaScale && (
        <div className="mt-sp2 flex justify-between border-t border-dashed border-border pt-sp2 text-[10px] text-t3">
          <span>
            <b className="block text-[11px] text-t2">&lt; 1</b>less sensitive
          </span>
          <span className="text-teal">
            <b className="block text-[11px]">1</b>market
          </span>
          <span className="text-right">
            <b className="block text-[11px] text-t2">&gt; 1</b>more sensitive
          </span>
        </div>
      )}
      {learn && detail && (
        <button
          type="button"
          className="mt-sp3 border-0 bg-transparent p-0 text-[12px] font-bold text-teal hover:underline"
          onClick={() => {
            setDetailOpen((d) => !d);
          }}
        >
          {learn}
        </button>
      )}
      {detail && detailOpen && (
        <dl className="mt-sp3 grid grid-cols-[auto_1fr] gap-x-sp3 gap-y-1 border-t border-border pt-sp3 text-[11.5px]">
          {Object.entries(detail).map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-semibold text-t3">{k}</dt>
              <dd className="mono text-right text-t1">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );

  if (inline) {
    return (
      <>
        <span
          {...triggerProps}
          ref={setTriggerRef}
          tabIndex={0}
          role="button"
          className="-m-0.5 inline-flex cursor-pointer items-center gap-1 rounded-r1 px-1 py-0.5 transition-colors hover:bg-teal/[0.08]"
        >
          {children}
          <span className="grid h-[15px] w-[15px] shrink-0 place-items-center rounded-full border border-border2 text-[9px] font-extrabold text-t3">
            ⓘ
          </span>
        </span>
        {mounted && createPortal(popover, document.body)}
      </>
    );
  }

  return (
    <span className="inline-flex items-center gap-1">
      {children}
      <button
        type="button"
        {...triggerProps}
        ref={setTriggerRef}
        className="grid h-[17px] w-[17px] shrink-0 place-items-center rounded-full border border-border2 bg-bg2 text-[10px] font-extrabold text-t2 transition-colors hover:border-teal hover:bg-teal/[0.08] hover:text-teal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/25"
      >
        ⓘ
      </button>
      {mounted && createPortal(popover, document.body)}
    </span>
  );
}
