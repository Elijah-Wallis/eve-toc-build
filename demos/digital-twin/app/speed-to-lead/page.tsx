import Link from "next/link";
import { Activity } from "lucide-react";
import { SpeedToLeadSimulator } from "@/components/speed-to-lead-simulator";
import { Button } from "@/components/ui/button";

export default function SpeedToLeadPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,hsl(var(--primary)/0.15),transparent)]" />
      <div className="relative mx-auto max-w-6xl px-4 py-10 sm:py-14">
        <div className="mb-6">
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
            <Link href="/diagnostic">&larr; Back to diagnostic</Link>
          </Button>
        </div>

        <header className="mb-10 text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-4 py-1.5 text-sm text-primary">
            <Activity className="h-4 w-4" />
            <span>Eve Patient Acquisition Flywheel</span>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Speed-to-Lead Patient Response Module
          </h1>
          <p className="mx-auto mt-4 max-w-3xl text-lg text-muted-foreground">
            The missing piece after the diagnostic: Eve responds instantly,
            qualifies intelligently, and moves new patient leads to booking
            while the clinic owner gets a clean summary in real time.
          </p>
        </header>

        <SpeedToLeadSimulator />
      </div>
    </div>
  );
}
