import { NextResponse } from "next/server";
import { z } from "zod";
import {
  getMockSpeedToLeadResult,
  runSpeedToLead,
} from "@/lib/speed-to-lead";

const bodySchema = z.object({
  clinic_name: z.string().min(1).optional(),
  patient_name: z.string().min(1, "Patient name is required"),
  phone: z.string().min(7, "Phone number is required"),
  email: z.string().email("Valid email is required"),
  concern: z.string().min(10, "Concern should include some detail"),
  service_interest: z.string().min(2, "Service interest is required"),
  include_voice: z.boolean().optional(),
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

    let result;
    try {
      result = await runSpeedToLead(parsed.data);
    } catch (error) {
      console.warn("Speed-to-lead MCP fallback:", error);
      result = getMockSpeedToLeadResult(parsed.data);
    }

    return NextResponse.json({
      success: true,
      ...result,
    });
  } catch (error) {
    console.error("Speed-to-lead API error:", error);
    return NextResponse.json(
      {
        success: false,
        error:
          error instanceof Error ? error.message : "Internal server error",
      },
      { status: 500 }
    );
  }
}
