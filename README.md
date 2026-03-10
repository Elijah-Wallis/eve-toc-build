# Eve Ontology — Single Source of Truth (SSOT) Constitution

This repository is the highest-authority specification for Eve Ontology: a Palantir-style operational digital twin for PE-backed medspa, dental, and plastic surgery platforms. OpenClaw is the runtime substrate. The ontology is the product.

## Core Mission

Unify operational reality into one canonical ontology so operators, automations, analytics, and AI agents all act on the same facts, the same identities, and the same provenance. Every material workflow in this repo must reduce fragmentation between source systems and the operating truth used by the platform.

## Highest Leverage Problem #1: Data Fragmentation

The primary failure mode in multi-site healthcare operations is fragmented data: disconnected patient, provider, clinic, inventory, financial, and compliance records that force humans to reconcile truth manually. Eve exists to collapse that fragmentation into one auditable, typed, provenance-backed model that can drive action safely.

## 5 Core Invariants

1. Ontology first. Every durable operational fact must map to a declared ontology object and relationship.
2. Provenance required. No record is canonical unless the source system, capture path, and timestamps are preserved.
3. No shadow systems. Workflows, scripts, dashboards, and agents may not create parallel schemas or undeclared entities outside the SSOT.
4. Safe self-improvement only. Agents may propose improvements through the existing proposal system, but they may not directly self-modify code or schema outside that governed flow.
5. Runtime serves the ontology. OpenClaw, Telegram, n8n, Supabase, launchd, PM2, and Retell are implementation layers; if they diverge from the ontology SSOT, they must be changed, not the Constitution.

## Domain Objects

The ontology must at minimum represent these core domain objects:

1. PatientJourney
2. ClinicalEncounter
3. AestheticProcedure/DentalService
4. Provider
5. ClinicLocation
6. ConsumableInventory
7. FinancialEvent
8. ComplianceRecord

Each object must declare relationships and provenance requirements in [`ontology/schema.yml`](/Users/elijah/Developer/eve-toc-build/ontology/schema.yml).

## Repo Philosophy

- Keep the ontology explicit and small enough to govern the whole system.
- Keep runtime code practical, observable, and replaceable.
- Prefer typed, auditable paths over clever shortcuts.
- Route all agent improvement through proposals, validation, and human review.
- Reject foreign framework drift that does not strengthen the ontology SSOT against fragmentation.

## Implementation Boundary

This repo contains the ontology plus the operating machinery around it:

- OpenClaw runtime and proposal system
- Telegram control and launchd/PM2 supervision
- n8n orchestration hooks
- Supabase schema and upgrades
- Retell integration paths

These components are valid only insofar as they preserve the Constitution above.
