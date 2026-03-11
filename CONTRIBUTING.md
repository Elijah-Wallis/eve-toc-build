# Contributing

All contributions must preserve the README SSOT Constitution.

## Invariant #1 (non-negotiable)
All data access and transformations MUST route through the Ontology layer. No direct Supabase/REST/DB calls are allowed in production logic.

## Pull Request Requirements
1. Answer: **How does this PR strengthen the SSOT for data fragmentation?**
2. Answer: **Does this PR protect the Ontology SSOT? (Y/N + link)**
3. If data model changes are involved, update `ontology/schema.yml` first.
