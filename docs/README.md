# 3-GAL — Documentation

This folder contains the documentation for the 3-GAL project. Start here.

| Document | What it covers |
|---|---|
| **[SECURITY_AUDIT.md](./SECURITY_AUDIT.md)** | The original security audit — 24 findings across the codebase. Read this to understand what was wrong before patches were applied. |
| **[FINAL_REPORT.md](./FINAL_REPORT.md)** | The wrap-up summary of all patches shipped (Phase 1 + Hotfix + Phase 2) — what's fixed, what's deferred, how to verify. |
| **[PATCHES_Phase1.md](./PATCHES_Phase1.md)** | Per-phase installation notes for Phase 1 (security patches). |
| **[PATCHES_Hotfix.md](./PATCHES_Hotfix.md)** | Per-phase installation notes for the Hotfix (sort + PDF viewer bugs). |
| **[PATCHES_Phase2.md](./PATCHES_Phase2.md)** | Per-phase installation notes for Phase 2 (reliability + defense-in-depth). |

## Reading order

If you're new to the project and want to understand the full hardening story:

1. **README.md** (in the project root) — what the app does, how to install, how to use
2. **SECURITY_AUDIT.md** — what was wrong
3. **PATCHES_Phase1.md**, **PATCHES_Hotfix.md**, **PATCHES_Phase2.md** — what was fixed, in order
4. **FINAL_REPORT.md** — the wrap-up; what was deferred to a later phase

## Phase 3+

Phase 3 added `config.py` for centralized configuration and SHA-pinned all GitHub Actions. Those changes are integrated into the main source files; no separate doc needed.

## What was deliberately left out

- **Architecture diagrams** — the project is small enough that reading `app.py` directly is faster than maintaining a diagram.
- **Contributing guide** — this is a personal/portfolio project; external contributions aren't expected.
- **Changelog** — git log + commit messages serve this purpose.
