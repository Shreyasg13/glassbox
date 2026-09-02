"use client";

import { motion, useReducedMotion } from "framer-motion";

/** See app/(marketing)/template.tsx for why this is entrance-only. */
export default function AppTemplate({ children }: { children: React.ReactNode }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 0.68, 0, 1.2] }}
    >
      {children}
    </motion.div>
  );
}
