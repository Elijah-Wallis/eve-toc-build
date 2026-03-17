# Rust Migration Baseline

This repository now includes a Rust-first operational CLI:

- `cargo run -- validate-runtime-config`

## What changed

1. Added a root Rust package (`Cargo.toml`) and source tree under `src/`.
2. Ported the runtime config validation flow from Python to Rust.
3. Kept `scripts/validate_runtime_config.py` as a compatibility shim that forwards to Rust.
4. Added `.gitattributes` overrides so non-Rust legacy assets are excluded from GitHub language accounting while migration is underway.

## Next migration steps

- Port `src/runtime/*.py` modules to a Rust crate-by-crate layout.
- Replace Python launch scripts with Rust binaries in `src/bin/`.
- Convert dashboard runtime services to Rust web components.
