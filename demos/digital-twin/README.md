# Eve Digital Twin Demonstration

**Monorepo:** This project lives in [eve-toc-build](https://github.com/Elijah-Wallis/eve-toc-build) at `demos/digital-twin/`. The standalone repo `digital-twin-demonstration` is archived there.

## Overview

The flagship B2B lead magnet for Eve L5_Medspa_IaC. Clinic owners input 5 KPIs and instantly receive a live "Digital Twin" of their practice running under full autonomous ontology — revenue projections, staff reduction, hidden leaks, and a downloadable branded PDF report.

This is the business-version of the "free tire plug" story that turned $0 visitors into $384 customers — now extended with a speed-to-lead patient response module that turns the diagnostic into a complete patient-acquisition flywheel.

## Purpose

- Demonstrate the power of event-state ontology autonomy to decision-makers
- Generate high-quality, qualified leads for long-term Eve ontology contracts ($75k–$250k+ ACV)
- Collect real clinic data that seeds the cross-clinic hive mind
- Convert 25–40% of demos into paid 90-day pilots

## Sales Flow

### Stage 1 — Instant Diagnostic (5 KPIs)
1. Clinic owner enters: clinic name, monthly revenue, staff count, no-show rate, avg treatment value, locations.
2. Eve runs the diagnostic (MCP ontology engine or mock fallback).
3. Dashboard displays: KPI cards, revenue/trajectory charts, staff allocation pie, **5–7 critical bottlenecks** with dollar impact and confidence intervals, hidden leaks, executive narrative.
4. PDF report downloadable immediately.

### Stage 2 — Deeper Ontology Twin (Free Upgrade)
1. User clicks "Unlock Deeper Ontology Twin (Free Upgrade)" button on the dashboard.
2. Modal collects optional deeper data: staff hourly cost, monthly marketing spend, inventory value, and optional CSV upload.
3. Eve re-runs with tighter confidence intervals (92–99% CI) and identifies 2–4 additional bottlenecks: staff idle time, missed upsell, inventory waste, marketing attribution leakage.
4. Dashboard updates in-place with refined projections, new bottleneck cards, and "Deep Ontology" badge.

### Stage 3 — Speed-to-Lead Patient Response Module
1. Visit `/speed-to-lead` or run the embedded simulation directly from the diagnostic results section.
2. Simulate a new patient lead with name, phone, email, concern, and service interest.
3. Eve pulls the relevant ontology pathway, sends hyper-personalized SMS + email (plus optional voice), asks 2–3 smart qualification questions, and moves the lead toward booking.
4. Demo mode uses mock Twilio, Vapi, and Calendly/Cal.com layers so the orchestration works instantly without live credentials.
5. The clinic owner receives an immediate summary notification, and the dashboard frames the expected booking lift at 35–70%.

### Conversion
- Bottleneck cards with CI ranges build trust and urgency — each one is a quantified problem the pilot solves.
- Two-stage flow keeps friction low while collecting progressively richer data.
- PDF includes full bottleneck analysis with CI ranges plus the new speed-to-lead module overview for stakeholder sharing.

## Tech Stack & Purpose

| Tool | Purpose |
|-------------------------|---------|
| Next.js 15 App Router | Fast, server-rendered frontend + API routes |
| Supabase | Postgres DB for persisting diagnostics and seeding real ontology states |
| MCP Agents | Core Eve hive-mind ontology engine that performs state shifts and projections |
| Twilio / Vapi / Calendly / Cal.com (mock) | Instant demo-mode patient response, qualification, and booking orchestration |
| shadcn/ui + Tailwind | Premium cyber-medical UI (teal/gold dark theme) |
| Recharts | Interactive before/after revenue, staff, and trajectory charts |
| jsPDF + html2canvas | Generate beautiful branded PDF reports with embedded charts |
| Zod + React Hook Form | Type-safe, robust form validation |
| Lucide React | Clean, consistent icons |
| Vercel | Instant global deployment and hosting |

## How to Run

```bash
npm run demo  # or: npm run dev
```

Then open:

- `http://localhost:3000/diagnostic` for the clinic autonomy diagnostic
- `http://localhost:3000/speed-to-lead` for the patient lead-response module
