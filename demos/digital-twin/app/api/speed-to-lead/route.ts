import { NextResponse } from "next/server";
import { z } from "zod";
import {
  buildSpeedToLeadSimulation,
  createDefaultClinicContext,
} from "@/lib/speed-to-lead";

const clinicContextSchema = z.object({
  clinicName: z.string().min(1),
  monthlyRevenue: z.number().min(1),
  avgTreatmentValue: z.number().min(1),
  noShowRate: z.number().min(0).max(100),
  staffHoursSavedPerWeek: z.number().min(0),
  revenueLiftPct: z.number().min(0),
  locations: z.number().int().min(1),
});

const bodySchema = z.object({
  clinicName: z.string().min(1),
  patientName: z.string().min(1),
  phone: z.string().min(7),
  email: z.string().email(),
  concern: z.string().min(5),
  serviceInterest: z.string().min(3),
  includeVoice: z.boolean().default(true),
  autoBook: z.boolean().default(false),
  clinicContext: clinicContextSchema.optional(),
});

export async function POST(request: Request) {
  try {
    const raw = await request.json();
    const parsed = bodySchema.safeParse(raw);

    if (!parsed.success) {
      return NextResponse.json(
        {
          success: false,
          error: "Invalid speed-to-lead input",
          details: parsed.error.flatten(),
        },
        { status: 400 }
      );
    }

    const context =
      parsed.data.clinicContext ?? createDefaultClinicContext(parsed.data.clinicName);

    const simulation = buildSpeedToLeadSimulation({
      ...parsed.data,
      clinicContext: {
        ...context,
        clinicName: parsed.data.clinicName,
      },
    });

    return NextResponse.json({
      success: true,
      simulation,
    });
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error:
          error instanceof Error ? error.message : "Speed-to-lead simulation failed",
      },
      { status: 500 }
    );
  }
}
