# Eve Ontology — Single Source of Truth (SSOT) Constitution

# Iron Law of the Ontology (Prime Directive)

**This is the unbreakable constitution of the repository.**

Every line of code, every model, every integration, every schema change, every commit message, every business decision, and every architectural choice in this repository **MUST** protect and strengthen the Single Source of Truth (SSOT) defined in this document.

**Violating the SSOT is a critical failure.**  
It breaks autonomy, compliance, HIPAA lineage, M&A integration velocity, and scale velocity for every PE-backed medspa, dental, and plastic surgery platform we serve.

**No exceptions. No workarounds. No “temporary” bypasses.**

- All data access and transformations **MUST** route exclusively through the OntologyClient layer (Invariant #1).
- Any PR that introduces direct Supabase, raw SQL, or non-ontology data paths **will be rejected** by automated CI.
- Any change to ontology/ or schema.yml requires explicit reference to “How does this strengthen the SSOT?” in the PR body.
- The SSOT Constitution (this README) is the highest authority. All other files (ARCHITECTURE.md, AGENTS.md, code, etc.) are subordinate.

**Enforcement is automatic and multi-layered**:
- Pre-commit hook
- CI lint that fails the build
- PR template with mandatory SSOT justification checkbox
- CODEOWNERS requiring approval on ontology/ changes

This Iron Law is effective immediately and cannot be amended without unanimous founder approval + full audit.

Protect the SSOT. Everything else compounds from here.

## Core Mission
Eve is an autonomous ontology platform purpose-built for PE-backed medspa, dental, and plastic surgery platforms (10–400+ sites, $10M–$500M+ group revenue).

**Highest Leverage Problem We Solve First and Forever**  
Data fragmentation & lack of single source of truth across disparate EMRs, EHRs, billing systems, and spreadsheets.  
This is Problem #1. Every line of code, model, integration, schema change, and business decision in this repository MUST protect and strengthen this SSOT. Breaking it breaks autonomy, compliance, and scale velocity.

## What Eve Is (Not Just Code)
Eve is an operational ontology — a living digital twin of clinic operations (modeled after Palantir Foundry).  
We map raw, fragmented data sources into coherent **Objects**, **Properties**, **Links**, and **Actions**.  
The code in this repo implements, enforces, and extends the ontology.  
The ontology itself is the single source of truth.

## Core Invariants (Never Break These — Enforced in CI/CD and PR Templates)
1. All data access and transformations MUST route through the Ontology layer. No direct queries to source EMRs/EHRs in production logic.
2. The Ontology schema (defined in /ontology/) is the single canonical model. Any new field, entity, or relationship must be modeled here first.
3. Every integration preserves provenance, auditability, and HIPAA-compliant lineage.
4. Changes to the Ontology require explicit approval + update to this README section.
5. Autonomy (AI decisions, scheduling, inventory, compliance) is built on top of the SSOT — never at the expense of truth or regulatory safety.

## Domain Objects (Core of the Ontology — Expand in /ontology/ directory)
- PatientJourney  
- ClinicalEncounter  
- AestheticProcedure / DentalService  
- Provider (with credentials, delegation rules, multi-state licensing)  
- ClinicLocation (multi-state compliance flags)  
- ConsumableInventory (Botox, fillers, implants — lot tracking, expiration)  
- FinancialEvent (billing, collections, revenue cycle)  
- ComplianceRecord  

(See /ontology/schema.yml for full typed definitions + relationships.)

## Repo Philosophy & Enforcement
This README is the constitution.  
- Link to it from CONTRIBUTING.md, every major module, PR templates, and architecture diagrams.  
- All code comments and docs must reference back to “protecting the Ontology SSOT.”  
- Any PR that risks fragmentation triggers automatic rejection.

Protect the SSOT. Everything else compounds from here.
