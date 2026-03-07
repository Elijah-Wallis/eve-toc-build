import Link from "next/link";
import { Activity, ArrowLeft, Calendar, MessageSquare, PhoneCall } from "lucide-react";
import { SpeedToLeadModule } from "@/components/speed-to-lead-module";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { createDefaultClinicContext } from "@/lib/speed-to-lead";

const clinicContext = createDefaultClinicContext("Radiant Glow Medspa");

export default function SpeedToLeadPage() {
  return (
    <div className="min-h-screen bg-background">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,hsl(var(--primary)/0.14),transparent)]" />
      <div className="relative mx-auto max-w-6xl px-4 py-10 sm:py-14">
        <div className="mb-8">
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
            <Link href="/diagnostic">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to diagnostic
            </Link>
          </Button>
        </div>

        <header className="mb-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-sm text-primary">
            <Activity className="h-4 w-4" />
            Eve Patient Acquisition Flywheel
          </div>
          <h1 className="mt-5 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Speed-to-Lead for medspas: instant response, qualification, and booking
          </h1>
          <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
            This is the missing piece after the diagnostic: Eve catches the lead,
            personalizes the first response, qualifies intent, offers the consult,
            and keeps the owner informed without waiting on the front desk.
          </p>
        </header>

        <div className="mb-10 grid gap-4 md:grid-cols-3">
          <Card className="border-border/80 bg-card/95">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Instant outreach</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Eve sends personalized SMS and email within seconds so new leads never sit stale in an inbox.
              </CardDescription>
            </CardContent>
          </Card>
          <Card className="border-border/80 bg-card/95">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <PhoneCall className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Voice fallback</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Vapi mock support shows how Eve escalates to concierge voice follow-up for high-intent patients.
              </CardDescription>
            </CardContent>
          </Card>
          <Card className="border-border/80 bg-card/95">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">Booking capture</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription>
                Calendly and Cal.com placeholders let the demo show slot offering or auto-booking immediately.
              </CardDescription>
            </CardContent>
          </Card>
        </div>

        <SpeedToLeadModule
          clinicName={clinicContext.clinicName}
          clinicContext={clinicContext}
          description="Run a live medspa lead demo with mock MCP, Twilio, Vapi, and booking steps. Everything is wired for instant demo-mode feedback."
        />
      </div>
    </div>
  );
}
