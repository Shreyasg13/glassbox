type Variant = "panel" | "raised" | "accent";

const variantClass: Record<Variant, string> = {
  panel: "glass-panel",
  raised: "glass-panel-raised",
  accent: "glass-panel-accent",
};

export function GlassPanel({
  variant = "panel",
  className = "",
  children,
}: {
  variant?: Variant;
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={`${variantClass[variant]} p-sp5 ${className}`}>{children}</div>;
}
