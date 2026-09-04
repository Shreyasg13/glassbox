import Link from "next/link";

export default function ChoosePage() {
  return (
    <div className="mx-auto flex max-w-[760px] flex-col gap-sp6 py-sp8">
      <div>
        <h1 className="mb-sp2 text-[22px] font-extrabold text-t1">Welcome to Glass Box</h1>
        <p className="text-[13.5px] text-t3">Pick how you'd like to start.</p>
      </div>

      <div className="grid grid-cols-1 gap-sp5 sm:grid-cols-2">
        <div className="glass-panel-raised flex flex-col gap-sp4 p-sp6">
          <div className="grid h-[38px] w-[38px] place-items-center rounded-r2 bg-teal-dim text-[18px] text-teal">
            ▷
          </div>
          <div>
            <h2 className="mb-sp2 text-[15.5px] font-bold text-t1">Explore with sample data</h2>
            <p className="text-[13px] leading-relaxed text-t2">
              See the live dashboard, agent signals, and reports right away using illustrative
              sample data. No setup required.
            </p>
          </div>
          <Link href="/dashboard" className="btn btn-primary mt-auto justify-center">
            Go to Dashboard →
          </Link>
        </div>

        <div className="glass-panel-raised flex flex-col gap-sp4 p-sp6">
          <div className="grid h-[38px] w-[38px] place-items-center rounded-r2 bg-gold-dim text-[18px] text-gold">
            ✦
          </div>
          <div>
            <h2 className="mb-sp2 text-[15.5px] font-bold text-t1">Connect your data</h2>
            <p className="text-[13px] leading-relaxed text-t2">
              Add your tickers, connect a broker, and set your alert preferences in a 4-step
              onboarding flow.
            </p>
          </div>
          <Link href="/onboarding" className="btn btn-ghost mt-auto justify-center">
            Start Onboarding →
          </Link>
        </div>
      </div>
    </div>
  );
}
