type SpeedToLeadServicePlaybook = {
  serviceLabel: string;
  concernCluster: string;
  personalizationAngle: string;
  communicationStyle: string;
  qualificationQuestions: string[];
  bookingLiftRange: [number, number];
};

export type SpeedToLeadInput = {
  clinic_name?: string;
  patient_name: string;
  phone: string;
  email: string;
  concern: string;
  service_interest: string;
  include_voice?: boolean;
};

export type SpeedToLeadTimelineStep = {
  title: string;
  detail: string;
  integration: "MCP" | "Twilio" | "Email" | "Vapi" | "Calendly" | "Cal.com" | "Owner alert";
  offsetSeconds: number;
};

export type SpeedToLeadResult = {
  mode: "mock" | "mcp";
  clinic_name: string;
  received_at: string;
  lead: {
    patient_name: string;
    first_name: string;
    phone: string;
    email: string;
    concern: string;
    service_interest: string;
    lead_temperature: "Warm" | "Hot";
    urgency_score: number;
  };
  ontology_state: {
    ontology: string;
    concern_cluster: string;
    service_line: string;
    personalization_angle: string;
    communication_style: string;
    qualification_focus: string;
    booking_strategy: "offer_slot" | "auto_book";
  };
  engagement: {
    sms: string;
    email_subject: string;
    email_body: string;
    voice_script?: string;
  };
  qualification_questions: string[];
  booking: {
    provider: "Calendly" | "Cal.com";
    mode: "offer_slot" | "auto_book";
    link: string;
    suggested_slots: string[];
    reserved_slot?: string;
    note: string;
  };
  owner_notification: {
    channel: string;
    summary: string;
  };
  metrics: {
    first_response_seconds: number;
    booking_lift_min: number;
    booking_lift_max: number;
    qualification_completion_pct: number;
    owner_notification_seconds: number;
  };
  integrations: {
    mcp: "live" | "mock";
    twilio: "mock";
    vapi: "mock" | "skipped";
    scheduling: "mock";
  };
  timeline: SpeedToLeadTimelineStep[];
};

const MCP_ENDPOINT =
  process.env.MCP_SPEED_TO_LEAD_ENDPOINT ||
  process.env.MCP_ENDPOINT ||
  process.env.NEXT_PUBLIC_MCP_ENDPOINT;

const SERVICE_PLAYBOOKS: Record<string, SpeedToLeadServicePlaybook> = {
  injectables: {
    serviceLabel: "Injectables consult",
    concernCluster: "Fine lines + natural-result reassurance",
    personalizationAngle: "natural-looking refresh without looking overdone",
    communicationStyle: "Fast, confident, low-friction",
    qualificationQuestions: [
      "Have you had Botox or Dysport before, or would this be your first treatment?",
      "Are you hoping for a subtle refresh or a stronger wrinkle-softening result?",
      "Is there a specific event or date you want to look ready for?",
    ],
    bookingLiftRange: [46, 70],
  },
  skin: {
    serviceLabel: "Skin rejuvenation consult",
    concernCluster: "Texture, pigment, downtime tolerance",
    personalizationAngle: "match the right skin plan to healing time and desired glow",
    communicationStyle: "Consultative and education-led",
    qualificationQuestions: [
      "What are you most focused on improving first: pigment, texture, or acne scarring?",
      "How much downtime are you comfortable with after treatment?",
      "Have you done lasers, RF microneedling, or peels before?",
    ],
    bookingLiftRange: [38, 58],
  },
  body: {
    serviceLabel: "Body contouring consult",
    concernCluster: "Timeline, candidacy, non-surgical expectations",
    personalizationAngle: "clarify candidacy and realistic contouring outcomes",
    communicationStyle: "High-touch and expectation-setting",
    qualificationQuestions: [
      "Which area is bothering you most right now?",
      "Are you looking for inch loss, skin tightening, or both?",
      "Do you have a deadline or event you want results lined up for?",
    ],
    bookingLiftRange: [35, 55],
  },
  weight: {
    serviceLabel: "Medical weight loss consult",
    concernCluster: "Readiness, support needs, compliance",
    personalizationAngle: "make the path feel guided, safe, and physician-led",
    communicationStyle: "Reassuring, structured, physician-forward",
    qualificationQuestions: [
      "Have you tried a medical weight loss program before?",
      "Would you prefer a virtual consult, in-person consult, or the first available option?",
      "Are you most motivated by energy, appearance, or a specific health milestone?",
    ],
    bookingLiftRange: [42, 64],
  },
  laser: {
    serviceLabel: "Laser hair removal consult",
    concernCluster: "Area, package fit, treatment cadence",
    personalizationAngle: "position a package that matches the treatment area and timeline",
    communicationStyle: "Direct and efficiency-focused",
    qualificationQuestions: [
      "Which area are you looking to treat first?",
      "Have you done laser hair removal before or would this be your first series?",
      "Are you mainly looking for pricing, earliest availability, or both?",
    ],
    bookingLiftRange: [37, 57],
  },
  wellness: {
    serviceLabel: "Wellness consult",
    concernCluster: "Energy, hormones, longevity intent",
    personalizationAngle: "connect the inquiry to a guided plan instead of a one-off service",
    communicationStyle: "Warm and concierge-like",
    qualificationQuestions: [
      "What prompted you to start looking into wellness support right now?",
      "Are you looking for labs, symptom relief, or an ongoing optimization plan?",
      "Would you prefer to meet with the first available provider or a specific clinician?",
    ],
    bookingLiftRange: [40, 60],
  },
};

function titleCase(value: string): string {
  return value
    .split(/[\s/-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function getFirstName(name: string): string {
  return titleCase(name.trim().split(/\s+/)[0] || "there");
}

function detectServicePlaybook(serviceInterest: string): SpeedToLeadServicePlaybook {
  const normalized = serviceInterest.toLowerCase();

  if (
    normalized.includes("botox") ||
    normalized.includes("dysport") ||
    normalized.includes("wrinkle") ||
    normalized.includes("filler")
  ) {
    return SERVICE_PLAYBOOKS.injectables;
  }
  if (
    normalized.includes("microneed") ||
    normalized.includes("laser facial") ||
    normalized.includes("peel") ||
    normalized.includes("skin")
  ) {
    return SERVICE_PLAYBOOKS.skin;
  }
  if (
    normalized.includes("body") ||
    normalized.includes("sculpt") ||
    normalized.includes("contour")
  ) {
    return SERVICE_PLAYBOOKS.body;
  }
  if (normalized.includes("weight")) {
    return SERVICE_PLAYBOOKS.weight;
  }
  if (normalized.includes("hair")) {
    return SERVICE_PLAYBOOKS.laser;
  }
  return SERVICE_PLAYBOOKS.wellness;
}

function computeUrgencyScore(concern: string): number {
  const normalized = concern.toLowerCase();
  let score = 68;

  const urgentSignals = [
    "asap",
    "soon",
    "this week",
    "next week",
    "wedding",
    "event",
    "before vacation",
    "before my trip",
    "ready to book",
  ];

  urgentSignals.forEach((signal) => {
    if (normalized.includes(signal)) score += 7;
  });

  if (normalized.includes("?")) score += 2;
  return Math.min(96, score);
}

function selectScheduler(firstName: string): "Calendly" | "Cal.com" {
  return firstName.length % 2 === 0 ? "Calendly" : "Cal.com";
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

function generateSlots(): string[] {
  const now = new Date();
  const offsets = [18, 26, 44];
  return offsets.map((hours) => formatSlot(new Date(now.getTime() + hours * 60 * 60 * 1000)));
}

function deriveSpeedToLeadEndpoint() {
  if (!MCP_ENDPOINT) return null;
  if (MCP_ENDPOINT.endsWith("/diagnostic")) {
    return MCP_ENDPOINT.replace(/\/diagnostic$/, "/speed-to-lead");
  }
  return `${MCP_ENDPOINT.replace(/\/$/, "")}/speed-to-lead`;
}

export async function runSpeedToLead(
  input: SpeedToLeadInput
): Promise<SpeedToLeadResult> {
  const endpoint = deriveSpeedToLeadEndpoint();
  if (!endpoint) {
    throw new Error("No MCP speed-to-lead endpoint configured");
  }

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lead_data: input,
      ontology: "L5_Medspa_IaC",
      module: "speed_to_lead",
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`MCP speed-to-lead failed: ${res.status} ${text}`);
  }

  const data = (await res.json()) as SpeedToLeadResult;
  return data;
}

export function getMockSpeedToLeadResult(
  input: SpeedToLeadInput
): SpeedToLeadResult {
  const clinicName = input.clinic_name?.trim() || "Serenity Med Spa";
  const firstName = getFirstName(input.patient_name);
  const playbook = detectServicePlaybook(input.service_interest);
  const urgencyScore = computeUrgencyScore(input.concern);
  const leadTemperature = urgencyScore >= 82 ? "Hot" : "Warm";
  const bookingMode = urgencyScore >= 82 ? "auto_book" : "offer_slot";
  const provider = selectScheduler(firstName);
  const suggestedSlots = generateSlots();
  const reservedSlot = bookingMode === "auto_book" ? suggestedSlots[0] : undefined;
  const qualificationFocus =
    bookingMode === "auto_book"
      ? "Confirm candidacy, timeline, and provider preference before the held slot expires."
      : "Reduce uncertainty fast so the lead moves from curious to booked in one thread.";

  const sms =
    `Hi ${firstName} — this is Eve from ${clinicName}. I saw you asked about ` +
    `${input.service_interest.toLowerCase()} for ${input.concern.trim()}. ` +
    `You sound like a strong fit for a ${playbook.serviceLabel.toLowerCase()}, and we can help you get ` +
    `${playbook.personalizationAngle}. I can text over the best next step and a few openings right now.`;

  const emailSubject = `${firstName}, your ${input.service_interest} options at ${clinicName}`;
  const emailBody =
    `Hi ${firstName},\n\n` +
    `Thanks for reaching out to ${clinicName}. Eve reviewed your inquiry about ${input.service_interest} and flagged ` +
    `${playbook.concernCluster.toLowerCase()} as the right pathway to personalize your first consult.\n\n` +
    `Based on your note — "${input.concern.trim()}" — our fastest route is to confirm a few details, then either hold the best appointment or send you the next openings immediately.\n\n` +
    `Reply with any answers you have, or use your booking link below.\n\n` +
    `- Eve`;

  const voiceScript = input.include_voice
    ? `Hi ${firstName}, this is Eve calling from ${clinicName}. I’m following up on your request about ${input.service_interest}. ` +
      `You mentioned ${input.concern.trim()}. I can help you get pointed to the right consult quickly, ask a couple of questions, and reserve the earliest opening if you want it.`
    : undefined;

  const bookingLink = `https://demo.${provider === "Calendly" ? "calendly" : "cal"}.com/eve/${clinicName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")}/${playbook.serviceLabel.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  const bookingLiftMin = playbook.bookingLiftRange[0];
  const bookingLiftMax = playbook.bookingLiftRange[1];

  return {
    mode: "mock",
    clinic_name: clinicName,
    received_at: new Date().toISOString(),
    lead: {
      patient_name: titleCase(input.patient_name),
      first_name: firstName,
      phone: input.phone,
      email: input.email.toLowerCase(),
      concern: input.concern.trim(),
      service_interest: input.service_interest,
      lead_temperature: leadTemperature,
      urgency_score: urgencyScore,
    },
    ontology_state: {
      ontology: "L5_Medspa_IaC",
      concern_cluster: playbook.concernCluster,
      service_line: playbook.serviceLabel,
      personalization_angle: playbook.personalizationAngle,
      communication_style: playbook.communicationStyle,
      qualification_focus: qualificationFocus,
      booking_strategy: bookingMode,
    },
    engagement: {
      sms,
      email_subject: emailSubject,
      email_body: emailBody,
      voice_script: voiceScript,
    },
    qualification_questions: playbook.qualificationQuestions,
    booking: {
      provider,
      mode: bookingMode,
      link: bookingLink,
      suggested_slots: suggestedSlots,
      reserved_slot: reservedSlot,
      note:
        bookingMode === "auto_book"
          ? `Eve pre-held ${reservedSlot} in mock mode because this lead scored ${urgencyScore}/100 for speed-to-book intent.`
          : `Eve offers live ${provider} slots instantly and keeps the thread open until the patient books.`,
    },
    owner_notification: {
      channel: "Mock SMS + email summary",
      summary:
        `${firstName} came in for ${input.service_interest}. Eve replied in under 10 seconds, asked ${playbook.qualificationQuestions.length} smart questions, ` +
        `${bookingMode === "auto_book" ? `and held ${reservedSlot}` : `and sent 3 live slots via ${provider}`}. ` +
        `Estimated booking lift for this service line: ${bookingLiftMin}%–${bookingLiftMax}%.`,
    },
    metrics: {
      first_response_seconds: 7,
      booking_lift_min: bookingLiftMin,
      booking_lift_max: bookingLiftMax,
      qualification_completion_pct: bookingMode === "auto_book" ? 84 : 71,
      owner_notification_seconds: 22,
    },
    integrations: {
      mcp: "mock",
      twilio: "mock",
      vapi: input.include_voice ? "mock" : "skipped",
      scheduling: "mock",
    },
    timeline: [
      {
        title: "Ontology lead state pulled",
        detail:
          `Eve maps ${input.service_interest} + concern into the ${playbook.serviceLabel.toLowerCase()} pathway and chooses a ${leadTemperature.toLowerCase()}-lead response cadence.`,
        integration: "MCP",
        offsetSeconds: 0,
      },
      {
        title: "Hyper-personalized SMS sent",
        detail: "Twilio mock dispatches an immediate text tailored to the patient’s service, concern, and urgency.",
        integration: "Twilio",
        offsetSeconds: 7,
      },
      {
        title: "Email follow-up queued",
        detail: "Email summary lands with the same personalized positioning plus booking link continuity.",
        integration: "Email",
        offsetSeconds: 12,
      },
      {
        title: "Qualification sequence started",
        detail: `Eve asks ${playbook.qualificationQuestions.length} service-specific questions that cut straight to candidacy and timing.`,
        integration: "MCP",
        offsetSeconds: 18,
      },
      ...(input.include_voice
        ? [
            {
              title: "Voice callback prepared",
              detail: "Vapi mock generates a short callback script for high-intent follow-up without needing a live integration.",
              integration: "Vapi" as const,
              offsetSeconds: 21,
            },
          ]
        : []),
      {
        title: bookingMode === "auto_book" ? "Best slot held automatically" : "Best consult slots offered",
        detail:
          bookingMode === "auto_book"
            ? `Scheduling mock places a soft hold on ${reservedSlot}.`
            : `Scheduling mock sends ${suggestedSlots.length} one-click openings via ${provider}.`,
        integration: provider,
        offsetSeconds: 24,
      },
      {
        title: "Owner summary delivered",
        detail: "Clinic owner gets the lead summary, qualification context, and booking status in one alert.",
        integration: "Owner alert",
        offsetSeconds: 28,
      },
    ],
  };
}
