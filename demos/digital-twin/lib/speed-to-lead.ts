export type SpeedToLeadClinicContext = {
  clinicName: string;
  monthlyRevenue: number;
  avgTreatmentValue: number;
  noShowRate: number;
  staffHoursSavedPerWeek: number;
  revenueLiftPct: number;
  locations: number;
};

export type SpeedToLeadLeadInput = {
  clinicName: string;
  patientName: string;
  phone: string;
  email: string;
  concern: string;
  serviceInterest: string;
  includeVoice: boolean;
  autoBook: boolean;
  clinicContext: SpeedToLeadClinicContext;
};

export type SpeedToLeadAgentStep = {
  agent: string;
  status: string;
  detail: string;
};

export type SpeedToLeadChannelMessage = {
  provider: string;
  status: string;
  preview: string;
  body: string;
  eta: string;
};

export type SpeedToLeadSimulation = {
  mode: "mock";
  runId: string;
  triggeredAt: string;
  ontologyState: {
    serviceLine: string;
    leadTemperature: "high" | "medium";
    urgency: "same-day" | "24-hour";
    bookingPriority: "auto-book" | "offer-slots";
    responseStyle: string;
    constraintFocus: string;
  };
  metrics: {
    responseSeconds: number;
    bookingLiftLow: number;
    bookingLiftHigh: number;
    bookingLiftExpected: number;
    qualificationScore: number;
    afterHoursCoverage: number;
  };
  timeline: SpeedToLeadAgentStep[];
  sms: SpeedToLeadChannelMessage;
  email: SpeedToLeadChannelMessage & { subject: string };
  voice?: SpeedToLeadChannelMessage;
  qualificationQuestions: string[];
  booking: {
    provider: string;
    autoBooked: boolean;
    status: string;
    bookingUrl: string;
    suggestedSlots: string[];
  };
  ownerNotification: {
    provider: string;
    status: string;
    preview: string;
    body: string;
  };
};

const BASE_BOOKING_LIFT_LOW = 35;

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function titleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function inferServiceLine(serviceInterest: string, concern: string): string {
  const combined = `${serviceInterest} ${concern}`.toLowerCase();

  if (combined.includes("botox") || combined.includes("filler") || combined.includes("inject")) {
    return "injectables";
  }
  if (combined.includes("weight") || combined.includes("semaglutide") || combined.includes("tirzepatide")) {
    return "weight-loss";
  }
  if (combined.includes("laser") || combined.includes("pigment") || combined.includes("resurfacing")) {
    return "laser";
  }
  if (combined.includes("facial") || combined.includes("skin") || combined.includes("acne")) {
    return "skin-health";
  }
  if (combined.includes("body") || combined.includes("contour") || combined.includes("sculpt")) {
    return "body-contouring";
  }

  return "aesthetics";
}

function buildConstraintFocus(context: SpeedToLeadClinicContext): string {
  if (context.noShowRate >= 12) {
    return "recover high-intent leads before delay turns into no-shows";
  }
  if (context.staffHoursSavedPerWeek >= 60) {
    return "keep front-desk bandwidth free while follow-up happens instantly";
  }
  return "turn first response speed into booked consults";
}

function buildBookingLiftHigh(context: SpeedToLeadClinicContext): number {
  const weighted =
    BASE_BOOKING_LIFT_LOW +
    Math.round(context.noShowRate * 1.2 + context.revenueLiftPct * 0.7 + context.locations * 2);

  return Math.max(45, Math.min(70, weighted));
}

function buildQualificationQuestions(serviceLine: string, concern: string): string[] {
  const normalizedConcern = concern.trim();

  if (serviceLine === "injectables") {
    return [
      `Is ${normalizedConcern.toLowerCase()} your main priority right now, or are you also thinking about preventive maintenance?`,
      "Have you had injectables before, and if so roughly when was your last treatment?",
      "Would you prefer the earliest consultation, or a time that works around your work schedule?",
    ];
  }

  if (serviceLine === "weight-loss") {
    return [
      "Are you looking for a consultation this week, or are you still comparing programs?",
      "Have you used GLP-1 medication before, or would this be your first medically supervised program?",
      "Would mornings or afternoons be easier if we reserve a consult now?",
    ];
  }

  if (serviceLine === "laser") {
    return [
      `How long has ${normalizedConcern.toLowerCase()} been bothering you, and have you tried other treatments yet?`,
      "Is your goal faster correction before an event, or a long-term treatment plan?",
      "If we hold a slot for you, do you prefer the next available consult or a specific day of the week?",
    ];
  }

  return [
    `What would a successful outcome for ${normalizedConcern.toLowerCase()} look like for you?`,
    "Are you hoping to start treatment this week, this month, or just gathering options right now?",
    "If we send over available consult times now, would you prefer text or email follow-up first?",
  ];
}

function formatSlot(date: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function buildSuggestedSlots(runSeed: number): string[] {
  const offsets = [1, 2, 4];
  return offsets.map((offset, index) => {
    const slot = new Date(Date.now() + offset * 24 * 60 * 60 * 1000);
    slot.setHours(10 + ((runSeed + index) % 5) * 2, index % 2 === 0 ? 0 : 30, 0, 0);
    return formatSlot(slot);
  });
}

function buildSmsBody(input: SpeedToLeadLeadInput, bookingUrl: string, question: string): string {
  return [
    `Hi ${input.patientName.split(" ")[0]} - this is Eve for ${input.clinicName}.`,
    `I saw your interest in ${input.serviceInterest} for ${input.concern}.`,
    `${question} If you'd like, I can hold a consult now: ${bookingUrl}`,
  ].join(" ");
}

function buildEmailBody(
  input: SpeedToLeadLeadInput,
  bookingUrl: string,
  questions: string[]
): string {
  return [
    `Hi ${input.patientName},`,
    "",
    `Thanks for reaching out to ${input.clinicName} about ${input.serviceInterest}. Based on your note about ${input.concern}, Eve has already prepared the best next step so your team can respond instantly.`,
    "",
    "To get you to the right provider quickly, we just need a little context:",
    ...questions.map((question, index) => `${index + 1}. ${question}`),
    "",
    `If you already know you want to talk with the team, you can grab a consultation time here right away: ${bookingUrl}`,
    "",
    "Warmly,",
    `Eve for ${input.clinicName}`,
  ].join("\n");
}

function buildVoiceBody(input: SpeedToLeadLeadInput, bookingUrl: string): string {
  return [
    `Hi ${input.patientName}, this is Eve calling for ${input.clinicName}.`,
    `Thanks for asking about ${input.serviceInterest} for ${input.concern}.`,
    "I can help get you to the right provider quickly.",
    `If you are ready, we can reserve a consultation now at ${bookingUrl}.`,
  ].join(" ");
}

export function createDefaultClinicContext(
  clinicName = "Radiant Glow Medspa"
): SpeedToLeadClinicContext {
  return {
    clinicName,
    monthlyRevenue: 120000,
    avgTreatmentValue: 325,
    noShowRate: 12,
    staffHoursSavedPerWeek: 68,
    revenueLiftPct: 24,
    locations: 1,
  };
}

export function createDefaultLeadInput(
  clinicName = "Radiant Glow Medspa"
): SpeedToLeadLeadInput {
  return {
    clinicName,
    patientName: "Ava Martinez",
    phone: "(305) 555-0128",
    email: "ava@example.com",
    concern: "post-acne scarring before a wedding",
    serviceInterest: "Laser resurfacing consultation",
    includeVoice: true,
    autoBook: false,
    clinicContext: createDefaultClinicContext(clinicName),
  };
}

export function buildSpeedToLeadSimulation(
  input: SpeedToLeadLeadInput
): SpeedToLeadSimulation {
  const clinicContext = input.clinicContext;
  const serviceLine = inferServiceLine(input.serviceInterest, input.concern);
  const constraintFocus = buildConstraintFocus(clinicContext);
  const bookingLiftHigh = buildBookingLiftHigh(clinicContext);
  const bookingLiftExpected = Math.round((BASE_BOOKING_LIFT_LOW + bookingLiftHigh) / 2);
  const qualificationScore = Math.min(
    98,
    68 +
      Math.round(clinicContext.noShowRate * 0.8) +
      (input.autoBook ? 5 : 0) +
      (input.includeVoice ? 4 : 0)
  );
  const responseSeconds = 38 + (input.patientName.length % 7) * 3;
  const leadTemperature = qualificationScore >= 80 ? "high" : "medium";
  const urgency = qualificationScore >= 82 ? "same-day" : "24-hour";
  const bookingPriority = input.autoBook && qualificationScore >= 80 ? "auto-book" : "offer-slots";
  const runId = `stl-${slugify(input.patientName)}-${Date.now().toString().slice(-6)}`;
  const bookingUrl = `https://cal.com/eve-demo/${slugify(input.clinicName)}?lead=${runId}`;
  const qualificationQuestions = buildQualificationQuestions(serviceLine, input.concern);
  const suggestedSlots = buildSuggestedSlots(input.patientName.length + input.serviceInterest.length);
  const smsBody = buildSmsBody(input, bookingUrl, qualificationQuestions[0]);
  const emailBody = buildEmailBody(input, bookingUrl, qualificationQuestions);
  const voiceBody = buildVoiceBody(input, bookingUrl);

  const timeline: SpeedToLeadAgentStep[] = [
    {
      agent: "Ontology state pull",
      status: "complete",
      detail: `Loaded ${titleCase(serviceLine)} playbook and clinic state for ${clinicContext.clinicName}.`,
    },
    {
      agent: "Hyper-personalized outreach",
      status: "complete",
      detail: "SMS and email drafted with service-specific positioning and immediate booking CTA.",
    },
    {
      agent: "Qualification",
      status: "complete",
      detail: `Prepared ${qualificationQuestions.length} smart questions tuned to ${titleCase(serviceLine)} conversion.`,
    },
    {
      agent: "Booking handoff",
      status: bookingPriority === "auto-book" ? "auto-booked" : "slots offered",
      detail:
        bookingPriority === "auto-book"
          ? `Auto-booked into ${suggestedSlots[0]}.`
          : "Sent live booking link and next-best consult slots.",
    },
    {
      agent: "Owner notification",
      status: "queued",
      detail: "Summary notification prepared for the clinic owner with lead score and next action.",
    },
  ];

  return {
    mode: "mock",
    runId,
    triggeredAt: new Date().toISOString(),
    ontologyState: {
      serviceLine: titleCase(serviceLine),
      leadTemperature,
      urgency,
      bookingPriority,
      responseStyle: "trusted concierge",
      constraintFocus,
    },
    metrics: {
      responseSeconds,
      bookingLiftLow: BASE_BOOKING_LIFT_LOW,
      bookingLiftHigh,
      bookingLiftExpected,
      qualificationScore,
      afterHoursCoverage: 100,
    },
    timeline,
    sms: {
      provider: "Twilio mock",
      status: "delivered in demo mode",
      preview: smsBody,
      body: smsBody,
      eta: `${responseSeconds}s from form submit`,
    },
    email: {
      provider: "SMTP mock",
      status: "delivered in demo mode",
      subject: `${input.clinicName}: next step for ${input.serviceInterest}`,
      preview: `Personalized consult invite for ${input.patientName}.`,
      body: emailBody,
      eta: `${responseSeconds + 4}s from form submit`,
    },
    voice: input.includeVoice
      ? {
          provider: "Vapi mock",
          status: "voice follow-up armed in demo mode",
          preview: "Outbound concierge call script prepared.",
          body: voiceBody,
          eta: `${responseSeconds + 12}s from form submit`,
        }
      : undefined,
    qualificationQuestions,
    booking: {
      provider: "Calendly / Cal.com mock",
      autoBooked: bookingPriority === "auto-book",
      status:
        bookingPriority === "auto-book"
          ? `Consult reserved for ${suggestedSlots[0]}`
          : "Three consult options sent instantly",
      bookingUrl,
      suggestedSlots,
    },
    ownerNotification: {
      provider: "Owner inbox mock",
      status: "queued",
      preview: `${input.patientName} is ${leadTemperature}-intent for ${input.serviceInterest}.`,
      body: [
        `New patient lead: ${input.patientName}`,
        `Service: ${input.serviceInterest}`,
        `Concern: ${input.concern}`,
        `Lead score: ${qualificationScore}/100`,
        `Booking path: ${bookingPriority === "auto-book" ? "auto-booked" : "link + slots offered"}`,
        `Next step: ${bookingPriority === "auto-book" ? "confirm consult and prep chart." : "watch for reply to qualification question #1."}`,
      ].join("\n"),
    },
  };
}
