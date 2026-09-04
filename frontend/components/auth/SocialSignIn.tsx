"use client";

// Google/Microsoft sign-in: real OAuth needs two things that don't exist
// yet -- registered OAuth apps with Google Cloud Console + Microsoft
// Entra ID (client id/secret, same external-provider pattern as the
// Gemini/Hugging Face keys elsewhere in this build) and backend routes
// to handle the OAuth callback and issue a session for it. These buttons
// are disabled with an honest "not set up yet" state rather than wired
// to a fake success path -- see docs/PROJECT_STATUS.md task list. Shared
// by /login and /signup since both offer the same (currently inert)
// social options.
function SocialButton({ provider, icon }: { provider: string; icon: React.ReactNode }) {
  return (
    <button
      type="button"
      disabled
      title="Needs OAuth app registration -- not set up yet"
      className="btn btn-ghost flex-1 cursor-not-allowed justify-center gap-sp2 opacity-60"
    >
      {icon}
      {provider}
    </button>
  );
}

export function SocialSignIn() {
  return (
    <>
      <div className="mb-sp4 flex gap-sp2">
        <SocialButton
          provider="Google"
          icon={
            <svg width="15" height="15" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M21.6 12.23c0-.68-.06-1.36-.17-2H12v3.99h5.4a4.63 4.63 0 0 1-2 3.04v2.5h3.23c1.9-1.75 2.97-4.32 2.97-7.53Z"
              />
              <path
                fill="currentColor"
                d="M12 22c2.7 0 4.97-.89 6.63-2.42l-3.23-2.5c-.9.6-2.05.95-3.4.95-2.6 0-4.8-1.76-5.6-4.12H3.07v2.58A10 10 0 0 0 12 22Z"
              />
              <path fill="currentColor" d="M6.4 13.9a6 6 0 0 1 0-3.8V7.5H3.07a10 10 0 0 0 0 9l3.33-2.6Z" />
              <path
                fill="currentColor"
                d="M12 5.98c1.47 0 2.79.5 3.82 1.5l2.87-2.87A9.96 9.96 0 0 0 12 2 10 10 0 0 0 3.07 7.5l3.33 2.6c.8-2.36 3-4.12 5.6-4.12Z"
              />
            </svg>
          }
        />
        <SocialButton
          provider="Microsoft"
          icon={
            <svg width="15" height="15" viewBox="0 0 24 24">
              <path fill="#F25022" d="M2 2h9.5v9.5H2z" />
              <path fill="#7FBA00" d="M12.5 2H22v9.5h-9.5z" />
              <path fill="#00A4EF" d="M2 12.5h9.5V22H2z" />
              <path fill="#FFB900" d="M12.5 12.5H22V22h-9.5z" />
            </svg>
          }
        />
      </div>

      <div className="mb-sp4 flex items-center gap-sp3 text-[11px] text-t3">
        <div className="h-px flex-1 bg-border" />
        or with username
        <div className="h-px flex-1 bg-border" />
      </div>
    </>
  );
}
