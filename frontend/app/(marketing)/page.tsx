import { Hero } from "@/components/marketing/Hero";
import { DiscrepancyBand } from "@/components/marketing/DiscrepancyBand";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { MLProvenance } from "@/components/marketing/MLProvenance";
import { StrategyLenses } from "@/components/marketing/StrategyLenses";
import { ConversionCTA } from "@/components/marketing/ConversionCTA";
import { AgentLauncher } from "@/components/marketing/AgentLauncher";
import { ScoreFeedback } from "@/components/marketing/ScoreFeedback";
import { ForAdvisors } from "@/components/marketing/ForAdvisors";
import { Pricing } from "@/components/marketing/Pricing";
import { Blog } from "@/components/marketing/Blog";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <StrategyLenses />
      <ConversionCTA />
      <DiscrepancyBand />
      <HowItWorks />
      <MLProvenance />
      <ScoreFeedback />
      <ForAdvisors />
      <Pricing />
      <Blog />
      <AgentLauncher />
    </>
  );
}
