# Release — March 10, 2026

## What's New

- **Structured Buildability Assessment Engine** — Enter any LA residential address, get a comprehensive zoning analysis with setbacks, height limits, FAR, density, parking, and use constraints. All constraints cite specific LAMC sections with relevant text excerpts.
- **Three-Layer Hybrid Rule Resolution** — Layer 1 (deterministic lookup, 100% confidence) + Layer 2 (conditional computation, 95% confidence) + Layer 3 (RAG + GPT-4o interpretation, 70-85% confidence). A database savepoint isolates Layer 3 failures so assessments always return at minimum.
- **Interactive Regulatory Map** — Mapbox GL JS with parcel boundaries, colored setback overlays, distance labels, buildable area polygon, hover tooltips, click-to-inspect popups, togglable legend with imperial scale.
- **SSE Streaming Chat** — Follow-up questions about assessment results with full regulatory context. Sessions persist per assessment.
- **Project Inputs** — Configure stories, bedrooms, bathrooms, and proposed sqft. Assessment updates dynamically on change.
- **Feedback Collection** — Thumbs up/down per constraint with optional comment. Stored for admin review.
- **GeoJSON Export** — Download assessment as a GeoJSON FeatureCollection with parcel boundary, constraints, and metadata.
- **Admin Panel** — Pipeline status dashboard, zone rules browser with verification toggle, feedback review table, manual re-ingestion trigger.
- **Cover-Branded Design** — Monochromatic palette, Inter/Outfit typography, geometric logo mark matching buildcover.com.

## Technical Details

- **Stack:** Vue 3 + TypeScript + Vite + Tailwind CSS | FastAPI + SQLAlchemy + Shapely | PostgreSQL + pgvector | OpenAI GPT-4o | Mapbox GL JS | Docker Compose
- **Hosting:** Local Docker Compose (`docker compose up --build`)
- **Database:** PostgreSQL 16 with pgvector extension, auto-creates tables and seeds 45 zone rules on startup
- **Zone Coverage:** R1, R2, RD1.5, RE9, RE11, RE15, RE20, RE40 + Guest House rules across SFH, ADU, and Guest House building types
- **API Surface:** 14 endpoints (assessment, parcel, chat, feedback, admin, health)

## Quality

- **Review:** 0 critical issues, 2 PoC-acceptable warnings (no auth, no retry logic)
- **Testing:** 3/3 smoke, 27/27 integration, 6/6 E2E, 8/8 edge case tests pass
- **Visual:** Zero console errors across all pages and interactions
- **Performance:** Cached assessments return in ~178-229ms

## Known Limitations

- ZIMAS API latency (~20s for uncached parcels) — mitigated with pre-cached representative parcels
- No admin authentication (PoC scope — documented as deferred)
- No retry/backoff on external API calls (ZIMAS, Mapbox, OpenAI)
- Zone prefix handling strips qualified conditions (e.g., `[Q]R1-1` → `R1`)
- Parcel boundaries from ZIMAS Landbase layer are approximate

## Links

- **Local Frontend:** http://localhost:3000
- **Local API Docs:** http://localhost:8000/docs
- **Plan:** PROJECT_PLAN.md
- **Architecture:** ARCHITECTURE.md
- **Review:** REVIEW_REPORT.md
- **Tests:** TEST_REPORT.md
