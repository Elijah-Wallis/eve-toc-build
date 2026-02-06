# SOP: Intellectual Property (IP) Protection & Enterprise Value

## Purpose
Protect core IP so the enterprise value compounds with every iteration.

## Scope
Code, prompts, workflows, datasets, SOPs, and proprietary methods.

## Owner
Elijah (OpenClaw)

## Policy (Always)
1) **Source of Truth**: All IP lives in the repo + backup.
2) **Least Access**: Only required access granted.
3) **Attribution**: Third‑party code and data must be documented.
4) **Traceability**: Every material change should have a commit message.

## Procedure
### 1) Inventory (Weekly)
- Identify new assets: code, prompts, workflows, datasets, SOPs.
- Record in `Business_Code/REFERENCE_INDEX.md`.

### 2) Ownership & Licensing (Monthly)
- Verify all new libraries and data sources have valid licenses.
- Log any restrictions in `Business_Code/SOP_IP.md` under Notes.

### 3) Trade Secret Handling (Always)
- Keep proprietary logic private.
- Avoid exposing raw strategy in public channels.

### 4) Access Control (Always)
- Store secrets in `.openclaw_env` (local only).
- Do not embed secrets in versioned files.

### 5) Backup & Redundancy (Weekly)
- Repo remains the canonical IP store.
- Ensure cloud backup of the repo is current.

### 6) Audits (Quarterly)
- Check for public exposure of sensitive files.
- Confirm that no keys or tokens exist in versioned artifacts.

## Evidence of Compliance
- Git history for code
- `Business_Code/REFERENCE_INDEX.md` for asset inventory
- `supabase/` migration history
- `Business_Code/SOP_TRAFFIC_TO_MCP_COMPILER.md` for deterministic API-to-MCP process IP

## Notes
- Add any IP‑relevant incidents, disclosures, or exceptions here.
- Deterministic compiler logic and generated manifests are protected operational IP.
