/** Where the "Buy me a coffee" buttons go. Paste the full page link, e.g. "https://buymeacoffee.com/yourname".
 * Empty = every coffee button hides itself (nothing points at a dead or wrong page). It is a plain constant,
 * not an env var, because Next bakes NEXT_PUBLIC_* in at image build time and CI builds the images. */
export const SUPPORT_URL = "";

/** Only a real https Buy Me a Coffee link counts; anything else is treated as "not set". */
export function supportUrl(): string | null {
  try {
    const u = new URL(SUPPORT_URL);
    return u.protocol === "https:" && (u.hostname === "buymeacoffee.com" || u.hostname === "www.buymeacoffee.com") ? u.toString() : null;
  } catch {
    return null;
  }
}
