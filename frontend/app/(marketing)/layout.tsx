import { MarketingNav } from "@/components/marketing/MarketingNav";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { AgentMarquee } from "@/components/marketing/AgentMarquee";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <MarketingNav />
      <AgentMarquee />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}
