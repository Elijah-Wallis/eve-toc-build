"use client";

import Link from "next/link";
import {
  useEffect,
  useMemo,
  useState,
  type ElementType,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Activity,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Loader2,
  Mail,
  MessageSquare,
  Mic,
  PhoneCall,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
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
import { cn } from "@/lib/utils";
import type { SpeedToLeadResult } from "@/lib/speed-to-lead";

type SpeedToLeadSimulatorProps = {
  clinicName?: string;
  embedded?: boolean;
};

type FormState = {
  patient_name: string;
  phone: string;
  email: string;
  concern: string;
  service_interest: string;
  include_voice: boolean;
};

const DEFAULT_FORM: FormState = {
  patient_name: "Taylor Morgan",
  phone: "(555) 204-8819",
  email: "taylor@example.com",
  concern:
    "I have a wedding in six weeks and want to soften forehead lines without looking frozen.",
  service_interest: "Botox / Wrinkle Relaxers",
  include_voice: true,
};

function ResultPanel({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description?: string;
  icon: ElementType;
  children: ReactNode;
}) {
  return (
    <Card className="border-border/80 bg-card/95">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-primary" />
          <CardTitle className="text-sm">{title}</CardTitle>
        </div>
        {description ? (
          <CardDescription className="text-xs leading-relaxed">
            {description}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function SpeedToLeadSimulator({
  clinicName = "Serenity Med Spa",
  embedded = false,
}: SpeedToLeadSimulatorProps) {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SpeedToLeadResult | null>(null);
  const [visibleSteps, setVisibleSteps] = useState(0);

  const timeline = useMemo(
    () =>
      result
        ? [...result.timeline].sort((a, b) => a.offsetSeconds - b.offsetSeconds)
        : [],
    [result]
  );

  useEffect(() => {
    if (!timeline.length) return;
    setVisibleSteps(0);
    const timers = timeline.map((_, index) =>
      window.setTimeout(() => {
        setVisibleSteps(index + 1);
      }, 120 + index * 280)
    );

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [timeline]);

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch("/api/speed-to-lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_name: clinicName,
          ...form,
        }),
      });

      const data = (await res.json()) as
        | ({ success: true } & SpeedToLeadResult)
        | { success: false; error?: string };

      if (!res.ok || !data.success) {
        toast.error("error" in data ? data.error ?? "Simulation failed" : "Simulation failed");
        return;
      }

      setResult(data);
      toast.success("Speed-to-lead simulation running in demo mode");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  const introTitle = embedded
    ? "How Eve Handles Your New Patient Leads 24/7"
    : "Speed-to-Lead Patient Response Module";
  const introText = embedded
    ? "The diagnostic finds the leaks. This module closes the loop by responding, qualifying, and booking new patient leads in seconds."
    : "Simulate a real patient inquiry and watch Eve respond, qualify, and push the lead to booking using mock Twilio, Vapi, and scheduling layers.";

  return (
    <section className="space-y-6">
      <Card className={cn("border-primary/20 bg-card/95", embedded && "shadow-lg")}>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
                <Zap className="h-3.5 w-3.5" />
                Demo mode live now
              </div>
              <div>
                <CardTitle className="text-xl text-foreground">
                  {introTitle}
                </CardTitle>
                <CardDescription className="mt-2 max-w-2xl text-sm leading-relaxed">
                  {introText}
                </CardDescription>
              </div>
            </div>
            {embedded ? (
              <Button asChild variant="outline" className="border-primary/30">
                <Link href="/speed-to-lead">
                  Open full module
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card className="border-border/70 bg-background/60">
              <CardContent className="flex items-center gap-3 p-4">
                <Activity className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    First response
                  </p>
                  <p className="text-lg font-semibold text-foreground">
                    &lt; 10 seconds
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/70 bg-background/60">
              <CardContent className="flex items-center gap-3 p-4">
                <Sparkles className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Booking lift
                  </p>
                  <p className="text-lg font-semibold text-foreground">
                    35%–70%
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/70 bg-background/60">
              <CardContent className="flex items-center gap-3 p-4">
                <ShieldCheck className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Qualification depth
                  </p>
                  <p className="text-lg font-semibold text-foreground">
                    2–3 smart questions
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/70 bg-background/60">
              <CardContent className="flex items-center gap-3 p-4">
                <CalendarClock className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Booking handoff
                  </p>
                  <p className="text-lg font-semibold text-foreground">
                    Offer slot or auto-book
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.2fr)]">
            <Card className="border-border/80 bg-background/60">
              <CardHeader>
                <CardTitle className="text-base">
                  Simulate a new patient lead
                </CardTitle>
                <CardDescription>
                  This runs instantly in mock mode using the same Eve medspa ontology framing as the diagnostic.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="grid gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="patient_name">Patient name</Label>
                    <Input
                      id="patient_name"
                      value={form.patient_name}
                      onChange={(e) => updateField("patient_name", e.target.value)}
                      className="bg-background/50"
                    />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="grid gap-2">
                      <Label htmlFor="phone">Phone</Label>
                      <Input
                        id="phone"
                        value={form.phone}
                        onChange={(e) => updateField("phone", e.target.value)}
                        className="bg-background/50"
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        value={form.email}
                        onChange={(e) => updateField("email", e.target.value)}
                        className="bg-background/50"
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="service_interest">Service interest</Label>
                    <select
                      id="service_interest"
                      value={form.service_interest}
                      onChange={(e) =>
                        updateField("service_interest", e.target.value)
                      }
                      className="flex h-10 w-full rounded-md border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option>Botox / Wrinkle Relaxers</option>
                      <option>Laser Skin Resurfacing</option>
                      <option>Body Contouring</option>
                      <option>Medical Weight Loss</option>
                      <option>Laser Hair Removal</option>
                      <option>IV / Wellness Membership</option>
                    </select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="concern">Concern</Label>
                    <textarea
                      id="concern"
                      value={form.concern}
                      onChange={(e) => updateField("concern", e.target.value)}
                      className="min-h-28 rounded-md border border-input bg-background/50 px-3 py-2 text-sm leading-relaxed ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>
                  <label className="flex items-center gap-3 rounded-md border border-border/70 bg-background/40 px-3 py-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.include_voice}
                      onChange={(e) =>
                        updateField("include_voice", e.target.checked)
                      }
                      className="h-4 w-4 rounded border-input"
                    />
                    Include mock Vapi voice callback
                  </label>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      type="submit"
                      size="lg"
                      disabled={loading}
                      className="sm:flex-1"
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Running simulation…
                        </span>
                      ) : (
                        "Simulate patient submission"
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="lg"
                      onClick={() => {
                        setForm(DEFAULT_FORM);
                        setResult(null);
                      }}
                      className="border-primary/20"
                    >
                      Reset sample lead
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card className="border-border/80 bg-background/60">
                <CardHeader>
                  <CardTitle className="text-base">
                    Eve orchestration timeline
                  </CardTitle>
                  <CardDescription>
                    Mock integrations mirror Twilio, Vapi, and Calendly/Cal.com behavior so the flow works instantly in demo mode.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!result ? (
                    <div className="rounded-lg border border-dashed border-border/80 bg-background/40 p-5 text-sm text-muted-foreground">
                      Run the sample lead to watch Eve pull ontology state, personalize the outreach, qualify the patient, and move the lead to booking.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {timeline.map((step, index) => {
                        const isVisible = index < visibleSteps;
                        return (
                          <div
                            key={`${step.title}-${index}`}
                            className={cn(
                              "rounded-lg border px-4 py-3 transition-all duration-300",
                              isVisible
                                ? "border-primary/30 bg-primary/5 opacity-100"
                                : "border-border/70 bg-background/40 opacity-40"
                            )}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-medium text-foreground">
                                {step.title}
                              </p>
                              <span className="text-xs text-muted-foreground">
                                +{step.offsetSeconds}s
                              </span>
                            </div>
                            <p className="mt-1 text-sm text-muted-foreground">
                              {step.detail}
                            </p>
                            <p className="mt-2 text-[11px] uppercase tracking-wide text-primary">
                              {step.integration}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              {result ? (
                <Card className="border-primary/20 bg-primary/5">
                  <CardContent className="grid gap-3 p-4 sm:grid-cols-3">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Lead temperature
                      </p>
                      <p className="text-lg font-semibold text-foreground">
                        {result.lead.lead_temperature}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Qualification completion
                      </p>
                      <p className="text-lg font-semibold text-foreground">
                        {result.metrics.qualification_completion_pct}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">
                        Owner alerted
                      </p>
                      <p className="text-lg font-semibold text-foreground">
                        {result.metrics.owner_notification_seconds}s
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : null}
            </div>
          </div>
        </CardContent>
      </Card>

      {result ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <ResultPanel
            title="Ontology state pulled"
            description="This is the Eve state that shapes the reply, qualification path, and booking strategy."
            icon={Zap}
          >
            <div className="grid gap-2 text-sm text-muted-foreground">
              <p>
                <span className="font-medium text-foreground">Ontology:</span>{" "}
                {result.ontology_state.ontology}
              </p>
              <p>
                <span className="font-medium text-foreground">Service line:</span>{" "}
                {result.ontology_state.service_line}
              </p>
              <p>
                <span className="font-medium text-foreground">Concern cluster:</span>{" "}
                {result.ontology_state.concern_cluster}
              </p>
              <p>
                <span className="font-medium text-foreground">Qualification focus:</span>{" "}
                {result.ontology_state.qualification_focus}
              </p>
            </div>
          </ResultPanel>

          <ResultPanel
            title="Hyper-personalized SMS"
            description={`Twilio ${result.integrations.twilio} placeholder`}
            icon={MessageSquare}
          >
            <p className="rounded-lg bg-background/60 p-3 text-sm leading-relaxed text-foreground/90">
              {result.engagement.sms}
            </p>
          </ResultPanel>

          <ResultPanel
            title="Email follow-up"
            description="Email handoff stays consistent with the same personalization angle and booking CTA."
            icon={Mail}
          >
            <p className="text-sm font-medium text-foreground">
              {result.engagement.email_subject}
            </p>
            <p className="mt-3 whitespace-pre-line rounded-lg bg-background/60 p-3 text-sm leading-relaxed text-foreground/90">
              {result.engagement.email_body}
            </p>
          </ResultPanel>

          <ResultPanel
            title="Qualification questions"
            description="Eve asks just enough to confirm candidacy, urgency, and best consult fit."
            icon={ShieldCheck}
          >
            <ul className="space-y-2 text-sm text-foreground/90">
              {result.qualification_questions.map((question) => (
                <li key={question} className="flex gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>{question}</span>
                </li>
              ))}
            </ul>
          </ResultPanel>

          {result.engagement.voice_script ? (
            <ResultPanel
              title="Voice follow-up"
              description={`Vapi ${result.integrations.vapi} placeholder`}
              icon={Mic}
            >
              <p className="rounded-lg bg-background/60 p-3 text-sm leading-relaxed text-foreground/90">
                {result.engagement.voice_script}
              </p>
            </ResultPanel>
          ) : null}

          <ResultPanel
            title="Booking handoff"
            description="Eve either offers live slots or auto-holds the best fit opening for hot leads."
            icon={CalendarClock}
          >
            <div className="space-y-3">
              <p className="text-sm text-foreground/90">
                {result.booking.note}
              </p>
              <div className="rounded-lg bg-background/60 p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {result.booking.provider} mock link
                </p>
                <p className="mt-1 break-all text-sm text-primary">
                  {result.booking.link}
                </p>
              </div>
              <div className="space-y-2">
                {result.booking.suggested_slots.map((slot) => (
                  <div
                    key={slot}
                    className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2 text-sm"
                  >
                    <span>{slot}</span>
                    {result.booking.reserved_slot === slot ? (
                      <span className="text-xs font-medium text-primary">
                        Held now
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Offer slot
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </ResultPanel>

          <ResultPanel
            title="Owner summary notification"
            description={result.owner_notification.channel}
            icon={PhoneCall}
          >
            <p className="rounded-lg bg-background/60 p-3 text-sm leading-relaxed text-foreground/90">
              {result.owner_notification.summary}
            </p>
          </ResultPanel>
        </div>
      ) : null}
    </section>
  );
}
