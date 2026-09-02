import { Hero } from "@/components/marketing/Hero";
import { DiscrepancyBand } from "@/components/marketing/DiscrepancyBand";
import { HowItWorks } from "@/components/marketing/HowItWorks";
import { ForAdvisors } from "@/components/marketing/ForAdvisors";
import { Pricing } from "@/components/marketing/Pricing";
import { Blog } from "@/components/marketing/Blog";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <DiscrepancyBand />
      <HowItWorks />
      <ForAdvisors />
      <Pricing />
      <Blog />
    </>
  );
}
