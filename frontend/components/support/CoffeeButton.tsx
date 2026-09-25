import { supportUrl } from "@/lib/support";

/** A plain link to the Buy Me a Coffee page. GlassBox never sees a card or any payment detail: the visitor
 * pays on buymeacoffee.com. Renders nothing until SUPPORT_URL is set. */
export function CoffeeButton({ label = "Buy me a coffee", className = "btn btn-primary justify-center" }: { label?: string; className?: string }) {
  const url = supportUrl();
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={className}>
      <span aria-hidden>☕</span> {label}
    </a>
  );
}
