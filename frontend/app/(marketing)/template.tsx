"use client";

import { motion, useReducedMotion } from "framer-motion";

/**
 * Next.js re-mounts `template.tsx` on every navigation into this route
 * group (unlike `layout.tsx`, which persists) — that remount is what
 * gives us a clean per-navigation entrance animation without fighting
 * the App Router's server-component streaming model. We deliberately
 * skip AnimatePresence/exit animations: coordinating an exit transition
 * with App Router's Suspense-based route swap is fragile in practice,
 * and an entrance-only transition already reads as a real transition.
 */
export default function MarketingTemplate({ children }: { children: React.ReactNode }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.22, 0.68, 0, 1.2] }}
    >
      {children}
    </motion.div>
  );
}
