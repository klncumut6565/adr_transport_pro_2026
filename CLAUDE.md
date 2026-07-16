# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

ADR Transport Pro 2026 — hazardous-goods (ADR) road transport document management. There are **two parallel applications sharing the same regulatory engine logic**, and understanding which one you're editing is the single most important thing here:

1. **Desktop app (FROZEN)** — `adr_transport_pro_2026.py`, a single ~13,400-line file: PyQt6 UI + SQLite (`~/.adr_transport_pro/adr_database.db`) + all business logic (login/license/security, ADR engine, security-plan engine, mixed-load checker, PDF/Excel export, print preview). **No new development goes here** (see `FAZ_PLANI_WEB.md` line 3: "Qt masaüstü DONDURULDU (bozulmaz, yeni geliştirme yapılmaz)"). Only touch it for the desktop-only tests still living in `tests/`.
2. **Web app (ACTIVE)** — Streamlit, deployed to Streamlit Cloud, backed by PostgreSQL (Supabase), multi-tenant. Entry point `app.py`, pages in `sayfalar/*.py`, shared engine/business logic in `webcore/`. **This is where all current work happens.**

`webcore/` was extracted line-by-line from the desktop monolith (see `webcore/__init__.py` header for exact source line ranges in the desktop file) — the computational engines are intentionally near-identical to the desktop versions except for one documented deviation (see "Known intentional desktop/web divergence" below). Do not "clean up" webcore code to look less like a port; the line-for-line correspondence is deliberate and documented.

The `adr_mix_pro/` package (mixed-load compatibility checker, ADR 7.5.2) is a third, older, self-contained engine that both the desktop app and `webcore/mix_adapter.py` wrap with their own database adapters — see "adr_mix_pro" section below.

## Commands

Desktop app:
```
pip install -r requirements-desktop.txt
python adr_transport_pro_2026.py
```

Web app (local):
```
pip install -r requirements.txt
streamlit run app.py
```
Requires `.streamlit/secrets.toml` with `[db] dsn = "postgresql://..."` (Supabase connection string). Never commit this file.

Tests:
```
pip install pytest
python -m pytest tests/ -v            # desktop app tests (Qt, offscreen)
python -m pytest tests_webcore/ -v    # web/webcore tests (Streamlit AppTest, headless)
```
Run a single test: `python -m pytest tests/test_mixload_ana_program.py::TestClassName::test_name -v`

`tests/` and `tests_webcore/` are independent suites targeting the two different apps — a change to shared logic (e.g. `adr_mix_pro/`) usually needs both run. When `resources/data/segregation_rules.csv` (the ADR 7.5.2.1 segregation rule table) changes, always run the full suite — `TestRuleFileIntegrity` in `tests/test_invariants.py` / `tests_webcore/test_invariants.py` checks for rule gaps, contradictions, and the "Class 1 is never OK with a non-Class-1 substance" regulatory invariant.

Data migration (desktop SQLite → Supabase Postgres, one-time per real cutover):
```
python araclar/migrate_desktop_to_pg.py --sqlite adr_database.db --dsn "SUPABASE_POOLER_DSN" --tenant 1 --temizle
```
Backup all Postgres tables to a timestamped CSV zip: `python araclar/yedek_al.py`.

## Architecture

### webcore/ (web engine layer, Qt-free)

- `constants.py`, `models.py` — dataclasses/enums extracted verbatim from the desktop file.
- `db.py` — `DatabaseManager`, SQLite-backed, mirrors the desktop app's DB layer 1:1.
- `pg.py` — `PgDatabaseManager(DatabaseManager)`, the Postgres/Supabase backend. All 56 business methods are inherited unchanged from `DatabaseManager`; only the cursor layer differs. Key internals:
  - `TranslatingCursor` rewrites SQLite-flavored SQL to Postgres at the lowest layer (`?`→`%s`, `LIKE`→`ILIKE`, `INSERT OR REPLACE/IGNORE`→`ON CONFLICT`, `strftime`→`to_char`, etc.) so the inherited business methods don't need to change.
  - **Multi-tenancy is enforced via Postgres Row Level Security**, not application-level filtering. Every business table has a `tenant_id` column and an RLS policy (`FORCE RLS`, own-the-table included). The tenant is set with `SET LOCAL app.tenant_id = <id>` **inside every single query's own transaction** (`_tenanted_cursor`) — deliberately *not* a one-time session-level `set_config`, because Supabase's transaction-mode pooler can route different queries from the same logical connection to different backend processes, silently losing session state. Don't reintroduce session-scoped tenant config; see the "KRİTİK ALTYAPI BULGUSU" and "Nihai düzeltme" entries in `FAZ_PLANI_WEB.md` for the incident history.
  - `chemicals` (the official ADR Table A data) is deliberately **not** tenant-scoped — it's shared regulatory reference data, auto-seeded from `ADR_A_TABLOSU.xlsx` if the table looks empty/corrupt (threshold check, not `== 0`, to survive partial-import corruption).
  - Self-healing migrations run at `init_database()` and are gated by a schema-version marker in `settings` so they don't re-scan on every reboot (this used to cause multi-second hangs / lock waits on every Cloud restart).
  - Use `toplu_okuma()` (bulk-read context manager) to batch multiple reads into one transaction instead of one `SET LOCAL` round-trip per call — this was a real, measured perf fix (16 round-trips → 6 for a single page load).
- `engines.py` — `ADREngine` (ADR 1.1.3.6 exemption scoring, tunnel codes, validation, LQ/EQ) and `SecurityPlanEngine` (ADR 1.10.3/1.10.4 security-plan requirement + inventory screening), extracted line-for-line from the desktop file.
- `auth.py` — `AuthManager`: `tenants` + `web_users` tables (intentionally *outside* RLS — tenant isn't known yet at login time), PBKDF2-HMAC-SHA256 (600k iterations, per-user salt), roles (admin/user/viewer), 5-strikes/15-min lockout.
- `session.py` — `get_db()`/`get_auth()`. **Must** use `st.session_state`, not `st.cache_resource` — the latter creates one global singleton connection shared across all concurrent Streamlit Cloud user sessions (real production incident: `OutOfOrderTransactionNesting`). One DB connection per browser session is the invariant to preserve.
- `mix_adapter.py` — web's `AnaDbChemicalAdapter` equivalent, adapts `adr_mix_pro`'s `ProductDatabase` interface onto the Postgres `chemicals` table (desktop uses SQLite directly). Because one UN number can map to multiple Table A rows (different classification code/packing group), records are **not** bulk-preloaded — each UN must be explicitly resolved via `register_variant()` before use, so a wrong variant is never silently picked.
- `pdf.py` — `html_to_pdf_bytes` (WeasyPrint, A4) + `build_letterhead_watermark_b64` (Pillow letterhead/DRAFT-stamp watermark, ported from desktop) + `wrap_for_screen_preview()` (injects screen-only CSS so the live HTML preview visually matches the `@page`-constrained PDF output, which browsers otherwise ignore).
- `transport_doc.py` — `build_transport_document_html`, ported from the desktop's `_build_print_html` (Qt/QTextDocument HTML, **not** ReportLab — the two apps use structurally different PDF pipelines, don't assume desktop PDF code transfers directly).
- `errors.py` — `turkce_hata_metni(exc)`: translates common exception types to Turkish; **all** user-facing error dialogs/messages must go through this — never surface raw `str(exc)` to a user.

### sayfalar/ (Streamlit pages)

Each file is one `st.Page`. `_ortak.py` holds shared helpers:
- Session-scoped manual caching (`_onbellekli`/`onbellek_temizle`) for companies/drivers/vehicles/Table-A-count lookups. **Do not use `st.cache_data`** for these — it pickles return values into a `CachedResult` wrapper that broke in production on Streamlit Cloud's Python runtime in a way that couldn't be reproduced locally; session_state-based caching was adopted specifically to avoid needing pickling at all.
- `sayfaya_taze_girildi(page_name)` — detects fresh navigation into a page vs. staying on it, used to force "Add new" forms closed when the user navigates away and back (session_state persists a form's open/closed flag across the whole session otherwise).
- Cache entries are keyed by `tenant_id` — never drop that from a cache key, or one tenant's list data leaks into another's session.

`sevkiyat_editor.py` (Taşıma Evrakı / shipment editor) is the largest and most load-bearing page: left column is the form + item list, right column is a live "ADR Kontrol Merkezi" panel (1.1.3.6 score, tunnel restriction, driver/vehicle certificate expiry, validation errors, 7.5.2 compatibility check, live HTML document preview) that recomputes on every Streamlit rerun with no button — this is intentional, not a missed "Validate" button.

### adr_mix_pro/ (mixed-load / segregation engine)

Originally a standalone app ("ADR Mix Checker Pro v2.4.1"), now vendored as a library used by both the desktop app and `webcore/mix_adapter.py`. Core logic lives in `adr_mix_pro/core/`: `rule_engine.py` (`SegregationRuleEngine`, reads `resources/data/segregation_rules.csv`), `checker.py` (`MixChecker`), `explosive_footnotes.py` (Class 1 a/b/c/d footnotes), `food_rules.py` (CV28 foodstuff segregation), `tunnel_rules.py`, `compatibility_groups.py`, `advisory_engine.py`, `risk_engine.py`. `adr_mix_pro/reports/` and `adr_mix_pro/ui/` are only used by the desktop app's `MixLoadCheckPage`/`SafetyPlansPage`, not by the web app (web renders its own HTML/PDF via `webcore/pdf.py` + `webcore/transport_doc.py`).

Both consumers implement the same `ProductDatabase` interface (`try_get_record`/`all_records`/`search`) against their own storage: desktop's `AnaDbChemicalAdapter` (SQLite) in `adr_transport_pro_2026.py`, web's adapter in `webcore/mix_adapter.py` (Postgres). `tests/conftest.py` and `tests_webcore/conftest.py` each provide an independent in-memory `SimpleProductDatabase` fixture for exercising the core engine without either adapter.

### Known intentional desktop/web divergence

`webcore/engines.py::ADREngine.check_compatibility` deduplicates/orders the incompatibility-message list deterministically; the desktop version uses `list(set(errors))` (unordered, can include A+B/B+A mirror duplicates). This is a deliberate, single documented deviation — message *content* and rule logic are unchanged, only dedup/ordering. Locked by `tests_webcore/test_webcore_smoke.py::TestCompatibilityDedup`. Do not "fix" the desktop version to match (it's frozen) or accidentally revert the web version to match desktop's behavior.

### Data sources / seeding

- `ADR_A_TABLOSU.xlsx` — official ADR Table A (2939 rows). Auto-imported on first run/empty-table detection on both apps. Not all rows are unique on (UN, classification_code, packing_group) — official Table A has genuinely distinct rows sharing that triple, distinguished only by special provisions (e.g. UN1133 has 6 real variants). Because of this, `import_table_a_excel` on the web side is **not idempotent** by row-uniqueness (re-running duplicates rows) — the Ayarlar (Settings) page's "clear before reimport" warning exists because of this; the desktop version uses full-row-signature-based idempotency instead (see `ENTEGRASYON_NOTLARI.md` v4.0.9 and `FAZ_PLANI_WEB.md` Faz 4 notes for why these two approaches differ).
- `ASUTEK_Kimyasal_İnceleme_Kimyasal_Envanter__ADR_rev1.xlsx` — sample real-world company chemical inventory, used by both apps' inventory-import and security-plan-screening features/tests.
- `resources/data/segregation_rules.csv` — the segregation rule table `adr_mix_pro` reads; treat as regulatory data, not code — validate with `TestRuleFileIntegrity` after any edit.

## Working conventions specific to this repo

- All user-facing strings, error messages, and comments in this codebase are Turkish. Match that when adding UI text or in-code comments for consistency with the existing surface area.
- When you find and fix a real bug, add a regression test rather than just fixing it — both `tests/` and `tests_webcore/` are structured as an accumulating regression suite (see `tests/README.md`: "Yeni bir hata bulunduğunda buraya test ekleyin — hiçbir testi silmeyin").
- Detailed rationale for *why* things are built the way they are (including several resolved production incidents on the Postgres/RLS/pooler side) lives in `FAZ_PLANI_WEB.md` — check it before changing `webcore/pg.py` connection/transaction handling, it's easy to reintroduce an already-fixed bug.
