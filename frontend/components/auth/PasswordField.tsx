"use client";

import { useState } from "react";

/** Password input with a show/hide toggle -- shared by /login and
 * /signup, extracted here once a second real use site existed rather
 * than duplicating the ~30-line show/hide markup across both pages. */
export function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
}) {
  const [show, setShow] = useState(false);

  return (
    <label className="flex flex-col gap-sp1 text-[12px] font-semibold text-t3">
      {label}
      <div className="relative">
        <span className="pointer-events-none absolute left-sp3 top-1/2 -translate-y-1/2 text-t4">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="4" y="11" width="16" height="9" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" strokeLinecap="round" />
          </svg>
        </span>
        <input
          className="input pl-[34px] pr-[38px] focus:shadow-teal"
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          aria-label={show ? "Hide password" : "Show password"}
          className="absolute right-sp3 top-1/2 -translate-y-1/2 text-t4 hover:text-t2"
        >
          {show ? (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.83 2.83M9.36 5.36A9.7 9.7 0 0 1 12 5c5 0 9 4 10 7-.32.99-1 2.11-2 3.16M6.3 6.53C4.6 7.68 3.3 9.28 2 12c1 3 5 7 10 7 1.5 0 2.9-.36 4.13-.94"
              />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z" strokeLinecap="round" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      </div>
    </label>
  );
}
