"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Bell,
  Brain,
  Calendar,
  CheckCircle2,
  Clock3,
  Loader2,
  Mail,
  MessageSquare,
  PhoneCall,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  createDefaultLeadInput,
  buildSpeedToLeadSimulation,
  type SpeedToLeadClinicContext,
  type SpeedToLeadLeadInput,
  type SpeedToLeadSimulation,
} from "@/lib/speed-to-lead";

type SpeedToLeadModuleProps = {
  clinicName: string;
  clinicContext: SpeedToLeadClinicContext;
  title?: string;
  description?: string;
  embedded?: boolean;
  ctaHref?: string;
};

type LeadFormState = Omit<SpeedToLeadLeadInput, "clinicContext" | "clinicName">;

const CHANNEL_ICONS = {
  sms: MessageSquare,
  email: Mail,
  voice: PhoneCall,
} as const;

function MetricCard({
  label,
  value,
  helper,
}: {
  label: string;
  value: string;
  helper: string;
}) {
  return (
    <Card className="border-border/80 bg-card/95">
      <CardContent className="p-5">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
        <p className="mt-2 text-2xl font-semibold text-foreground">{value}</p>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{helper}</p>
      </CardContent>
    </Card>
  );
}

function MessageCard({
  label,
  icon: Icon,
  provider,
  status,
  body,
}: {
  label: string;
  icon: typeof MessageSquare;
  provider: string;
  status: string;
  body: string;
}) {
  return (
    <Card className="border-border/80 bg-card/95">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm">{label}</CardTitle>
          </div>
          <span className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs text-primary">
            {provider}
          </span>
        </div>
        <CardDescription>{status}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="whitespace-pre-line text-sm leading-relaxed text-foreground/90">{body}</p>
      </CardContent>
    </Card>
  );
}

export function SpeedToLeadModule({
  clinicName,
  clinicContext,
  title = "Speed-to-Lead Patient Response Module",
  description = "Simulate how Eve responds in under a minute, qualifies the lead, books the consult, and updates the owner automatically.",
  embedded = false,
  ctaHref,
}: SpeedToLeadModuleProps) {
  const defaults = useMemo(() => createDefaultLeadInput(clinicName), [clinicName]);
  const fieldPrefix = useMemo(
    () => clinicName.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
    [clinicName]
  );
  const [form, setForm] = useState<LeadFormState>({
    patientName: defaults.patientName,
    phone: defaults.phone,
    email: defaults.email,
    concern: defaults.concern,
    serviceInterest: defaults.serviceInterest,
    includeVoice: defaults.includeVoice,
    autoBook: defaults.autoBook,
  });
  const [loading, setLoading] = useState(false);
  const [simulation, setSimulation] = useState<SpeedToLeadSimulation | null>(
    buildSpeedToLeadSimulation({ ...defaults, clinicContext })
  );

  useEffect(() => {
    setSimulation(
      buildSpeedToLeadSimulation({
        clinicName,
        clinicContext,
        ...form,
      })
    );
  }, [clinicContext, clinicName, form]); // Keep the live preview aligned with the latest diagnostic state.

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    try {
      const payload: SpeedToLeadLeadInput = {
        clinicName,
        clinicContext,
        ...form,
      };

      const res = await fetch("/api/speed-to-lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const json = (await res.json()) as {
        success?: boolean;
        simulation?: SpeedToLeadSimulation;
      };

      if (!res.ok || !json.success || !json.simulation) {
        throw new Error("Speed-to-lead simulation failed");
      }

      setSimulation(json.simulation);
    } catch {
      setSimulation(
        buildSpeedToLeadSimulation({
          clinicName,
          clinicContext,
          ...form,
        })
      );
    } finally {
      setLoading(false);
    }
  }

  const metrics = simulation?.metrics;

  return (
    <div className={embedded ? "space-y-6" : "space-y-8"}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Demo mode with mock Twilio and Vapi
          </div>
          <h2 className="mt-3 text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            {title}
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
            {description}
          </p>
        </div>
        {ctaHref ? (
          <Button asChild variant="outline" className="border-primary/30 bg-background/40">
            <Link href={ctaHref}>
              Open full simulator
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Response speed"
          value={metrics ? `< ${metrics.responseSeconds + 5}s` : "< 60s"}
          helper="Eve answers new patient leads instantly, including after-hours and weekend submissions."
        />
        <MetricCard
          label="Booking lift"
          value={
            metrics
              ? `${metrics.bookingLiftLow}-${metrics.bookingLiftHigh}%`
              : "35-70%"
          }
          helper="Expected consult-booking lift when the first touch, qualification, and scheduling happen in one workflow."
        />
        <MetricCard
          label="Owner visibility"
          value={metrics ? `${metrics.qualificationScore}/100 lead score` : "Live summary"}
          helper="Owners receive the lead score, concern, booking status, and next action without chasing the front desk."
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr,1.4fr]">
        <Card className="border-border/80 bg-card/95">
          <CardHeader>
            <CardTitle className="text-base">Simulate a patient submission</CardTitle>
            <CardDescription>
              Use the demo values or swap in a new medspa lead and rerun the full orchestration.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4" onSubmit={handleSubmit}>
              <div className="grid gap-2">
                <Label htmlFor={`${fieldPrefix}-patient-name`}>Patient name</Label>
                <Input
                  id={`${fieldPrefix}-patient-name`}
                  value={form.patientName}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, patientName: event.target.value }))
                  }
                  className="bg-background/50"
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor={`${fieldPrefix}-phone`}>Phone</Label>
                  <Input
                    id={`${fieldPrefix}-phone`}
                    value={form.phone}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, phone: event.target.value }))
                    }
                    className="bg-background/50"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor={`${fieldPrefix}-email`}>Email</Label>
                  <Input
                    id={`${fieldPrefix}-email`}
                    type="email"
                    value={form.email}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, email: event.target.value }))
                    }
                    className="bg-background/50"
                  />
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor={`${fieldPrefix}-service-interest`}>Service interest</Label>
                <Input
                  id={`${fieldPrefix}-service-interest`}
                  value={form.serviceInterest}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      serviceInterest: event.target.value,
                    }))
                  }
                  className="bg-background/50"
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor={`${fieldPrefix}-concern`}>Concern</Label>
                <textarea
                  id={`${fieldPrefix}-concern`}
                  value={form.concern}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, concern: event.target.value }))
                  }
                  className="min-h-24 rounded-md border border-input bg-background/50 px-3 py-2 text-sm text-foreground outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>

              <div className="grid gap-3 rounded-xl border border-border/70 bg-background/40 p-4 text-sm">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={form.includeVoice}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        includeVoice: event.target.checked,
                      }))
                    }
                    className="mt-1"
                  />
                  <span>
                    Add voice follow-up using the Vapi mock so the demo includes SMS + email + voice.
                  </span>
                </label>
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={form.autoBook}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, autoBook: event.target.checked }))
                    }
                    className="mt-1"
                  />
                  <span>
                    Auto-book if qualified, otherwise offer a Calendly / Cal.com slot instantly.
                  </span>
                </label>
              </div>

              <Button
                type="submit"
                size="lg"
                disabled={loading}
                className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Running Eve lead workflow...
                  </span>
                ) : (
                  "Run speed-to-lead demo"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="border-primary/25 bg-primary/5">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4 text-primary" />
                <CardTitle className="text-base">MCP Eve agent run</CardTitle>
              </div>
              <CardDescription>
                Ontology pull, personalization, qualification, booking, and owner summary.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {simulation?.timeline.map((step) => (
                <div
                  key={step.agent}
                  className="flex items-start justify-between gap-4 rounded-xl border border-border/70 bg-background/60 p-4"
                >
                  <div>
                    <p className="font-medium text-foreground">{step.agent}</p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {step.detail}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs text-primary">
                    {step.status}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card className="border-border/80 bg-card/95">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm">Pulled ontology state</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">Service line:</span>{" "}
                  {simulation?.ontologyState.serviceLine}
                </p>
                <p>
                  <span className="font-medium text-foreground">Lead temperature:</span>{" "}
                  {simulation?.ontologyState.leadTemperature}
                </p>
                <p>
                  <span className="font-medium text-foreground">Constraint focus:</span>{" "}
                  {simulation?.ontologyState.constraintFocus}
                </p>
              </CardContent>
            </Card>

            <Card className="border-border/80 bg-card/95">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm">Booking path</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <p>{simulation?.booking.status}</p>
                <ul className="space-y-1">
                  {simulation?.booking.suggestedSlots.map((slot) => (
                    <li key={slot} className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                      {slot}
                    </li>
                  ))}
                </ul>
                <p className="break-all text-xs text-primary">{simulation?.booking.bookingUrl}</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4">
            <MessageCard
              label="SMS"
              icon={CHANNEL_ICONS.sms}
              provider={simulation?.sms.provider ?? "Twilio mock"}
              status={simulation?.sms.status ?? "ready"}
              body={simulation?.sms.body ?? ""}
            />
            <MessageCard
              label="Email"
              icon={CHANNEL_ICONS.email}
              provider={simulation?.email.provider ?? "SMTP mock"}
              status={simulation?.email.subject ?? simulation?.email.status ?? "ready"}
              body={simulation?.email.body ?? ""}
            />
            {simulation?.voice ? (
              <MessageCard
                label="Voice"
                icon={CHANNEL_ICONS.voice}
                provider={simulation.voice.provider}
                status={simulation.voice.status}
                body={simulation.voice.body}
              />
            ) : null}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card className="border-border/80 bg-card/95">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm">Qualification prompts</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {simulation?.qualificationQuestions.map((question, index) => (
                    <li key={question} className="flex gap-2">
                      <span className="text-primary">{index + 1}.</span>
                      <span>{question}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card className="border-border/80 bg-card/95">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-primary" />
                  <CardTitle className="text-sm">Owner summary notification</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="mb-3 text-sm font-medium text-foreground">
                  {simulation?.ownerNotification.preview}
                </p>
                <p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
                  {simulation?.ownerNotification.body}
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
