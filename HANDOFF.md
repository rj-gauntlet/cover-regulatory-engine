# Cover Regulatory Engine — Handoff Document

> Last updated: March 24, 2026 | Commit: `18a348a`

## What This Project Is

A fullstack regulatory engine for the City of Los Angeles that takes a residential parcel (address or APN) and produces a structured, evidence-backed buildability assessment — what can be built, with what constraints, at what confidence, citing specific LAMC regulations.

Built as a hiring challenge for **Cover** (buildcover.com). All bonus features are implemented.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, Mapbox GL JS |
| Database | PostgreSQL + pgvector (vector embeddings) + uuid-ossp |
| AI/ML | OpenAI GPT-4o (completions), text-embedding-3-small (embeddings) |
| GIS | Mapbox Geocoding, ZIMAS ArcGIS REST, LA County ArcGIS (parcels + buildings) |
| Infra | Docker Compose (3 containers: db, backend, frontend) |

---

## How to Run

```bash
# 1. Copy .env.example to .env and fill in API keys
cp .env.example .env
# Required: OPENAI_API_KEY, MAPBOX_ACCESS_TOKEN

# 2. Start everything
docker compose up --build

# 3. Access
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Architecture (3-Layer Rule Resolution)

```
Address → Geocode → Parcel Lookup → Rule Resolution → Assessment
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
              Layer 1              Layer 1b             Layer 2
          Deterministic         Auto-Seed           Conditional
           ZoneRule DB        (fetch LAMC →         Computation
                              LLM extract →        (refine with
                              save to DB)          parcel dims)
                                                        │
                                                   Layer 3
                                                  RAG + LLM
                                               (supplementary
                                                constraints)
```

**Layer 1**: Queries `zone_rules` table for the parcel's zone class.
**Layer 1b** (NEW): If Layer 1 returns nothing, auto-seeds rules by fetching the LAMC section text (falls back to LLM knowledge if amlegal.com blocks), extracting structured rules via GPT-4o, saving to `zone_rules` with `is_verified=false`, then re-runs Layer 1.
**Layer 2**: Refines constraints using parcel dimensions (e.g., max_floor_area = lot_area × FAR).
**Layer 3**: RAG retrieval from `regulatory_chunks` (299 chunks, 32 zone codes) + LLM interpretation for supplementary constraints (overlay zones, special plans, exceptions).

---

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, lifespan (DB init + seeder) |
| `backend/app/services/engine/resolver.py` | 3-layer rule resolution orchestrator |
| `backend/app/services/engine/auto_seed.py` | **NEW** — On-demand zone rule auto-seeding via LAMC + LLM |
| `backend/app/services/engine/rules.py` | Layer 1: deterministic lookup |
| `backend/app/services/engine/compute.py` | Layer 2: conditional computation |
| `backend/app/services/engine/retriever.py` | Layer 3: RAG + LLM interpretation |
| `backend/app/services/engine/geometry.py` | Setback polygon computation (Shapely) |
| `backend/app/services/parcel/service.py` | Parcel lookup, caching, address matching, rich 404 |
| `backend/app/services/parcel/lacounty.py` | LA County ArcGIS client (parcels + buildings) |
| `backend/app/services/parcel/zimas.py` | ZIMAS ArcGIS client (zoning data) |
| `backend/app/services/parcel/geocoder.py` | Mapbox geocoding |
| `backend/app/services/ingestion/embedder.py` | Ingestion pipeline: scrape OR LLM → parse → chunk → embed |
| `backend/app/services/ingestion/scraper.py` | LAMC HTML scraper (amlegal.com — currently 403 blocked) |
| `backend/app/services/ingestion/parser.py` | Regulation parser: zone detection, topic detection |
| `backend/app/api/routes/assess.py` | POST /api/assess (main endpoint), rich 404 responses |
| `backend/app/api/routes/admin.py` | Pipeline trigger, rules CRUD, stats |
| `backend/app/api/routes/chat.py` | SSE streaming chat |
| `backend/data/seed/zone_rules.py` | Hand-curated rules (R1, R2, RD1.5, RE variants, A1, C2, C4) |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/views/HomeView.vue` | Main view: search + map + assessment panel |
| `frontend/src/views/AdminView.vue` | Admin panel: pipeline, rules, feedback |
| `frontend/src/components/MapView.vue` | Mapbox map: parcel/setback/building overlays, nearby labels |
| `frontend/src/components/AssessmentPanel.vue` | Constraint cards grouped by category |
| `frontend/src/components/ChatPanel.vue` | SSE streaming chat interface |
| `frontend/src/services/api.ts` | API client, ParcelNotFoundError |
| `frontend/src/types/index.ts` | TypeScript interfaces |

---

## Database Tables

| Table | Rows (approx) | Purpose |
|-------|---------------|---------|
| `zone_rules` | ~100+ | Structured development standards per zone (Layer 1) |
| `regulatory_chunks` | 299 | Embedded regulatory text for RAG retrieval (Layer 3) |
| `parsed_regulations` | 24 | Parsed LAMC section records |
| `raw_sources` | 24 | Source text (LLM-generated) |
| `parcels` | ~15 | Cached parcel geometries + zoning data |
| `assessments` | ~10 | Cached assessment results |
| `constraints` | ~100 | Individual constraints linked to assessments |

---

## What Was Done in This Session

### 1. Auto-Seed System (Layer 1b)
- `backend/app/services/engine/auto_seed.py` — maps 29 zone classes to LAMC section URLs
- When Layer 1 finds 0 rules: fetches LAMC text → falls back to LLM knowledge → GPT-4o extracts structured rules → saves to `zone_rules` (is_verified=false) → re-runs Layer 1
- Tested: R4 zone (no seed data) → auto-seeded 12 rules → returned 13 constraints
- First query ~25s (LLM call), subsequent queries instant (rules persisted)

### 2. RAG Pipeline Populated
- `run_llm_ingestion()` in `embedder.py` generates regulatory text for 24 LAMC sections via LLM
- 299 chunks created with vector embeddings covering 32 zone codes
- Triggered via: `POST /api/admin/pipeline/trigger?mode=llm`
- Layer 3 confirmed working: retrieves 8 chunks per query, sends to LLM for interpretation

### 3. Address Matching Improvements (prior in session)
- Strict situs-address validation — non-existent addresses return 404 instead of wrong parcel data
- Rich 404: returns geocoded coordinates + nearby parcel addresses for map display
- Frontend `ParcelNotFoundError` for structured 404 handling
- Map shows searched location pin + nearby address labels via DOM markers

### 4. Zone Rule Expansion (prior in session)
- Added seed rules for A1, C2, C4 zones
- Incremental seeder: doesn't skip new zones if some rules exist

---

## Known Issues / Pending Work

### Open Bug
- **Map labels on 404 view**: When an address is not found (rich 404), the DOM-based Mapbox markers for nearby addresses are not consistently rendering on the correct street. The `extractStreet` function and marker placement need debugging. The user said "make note to address this later."

### amlegal.com Blocked
- The LAMC scraper gets 403 Forbidden from amlegal.com (bot protection / JS rendering required). Both the existing scraper and the auto-seed fetcher fall back to LLM-generated text. If scraping becomes available (e.g., via Playwright/headless browser), the pipeline supports it via `?mode=scrape` or `?mode=auto`.

### Auto-Seeded Rules Are Unverified
- Rules created by auto-seed have `is_verified=false` and `notes` indicating their provenance. They should be spot-checked against actual LAMC sections, especially for less common zones.

### Layer 3 Returns 0 Additional Constraints
- This is *correct* behavior for standard residential parcels where Layers 1+2 cover everything. Layer 3 will add value for parcels with overlay zones, specific plans, or unusual conditions that aren't in structured rules.

---

## Important Context for Continuation

1. **This is a hiring challenge for Cover.** The goal is to demonstrate architecture, AI integration, and code quality. All bonus features (BF-01 through BF-06) are implemented.

2. **The project has a PROJECT_PLAN.md** that tracks all requirements and phases. All 7 phases are complete and shipped.

3. **Design system** matches buildcover.com aesthetic: monochromatic palette, Inter + Outfit fonts, warm accents.

4. **Docker Compose** runs everything: `docker compose up --build`. The `.env` file needs `OPENAI_API_KEY` and `MAPBOX_ACCESS_TOKEN`.

5. **Project artifacts**: `PROJECT_PLAN.md`, `IMPLEMENTATION_LOG.md`, `ARCHITECTURE.md`, `REVIEW_REPORT.md`, `TEST_REPORT.md`, `RELEASE.md`, `DASHBOARD.html`.

6. **Git history**: 11 commits on `master`, no remote configured yet. Need to `git remote add origin <url>` and push.

7. **The user** has been hands-off on coding (assistant does all implementation) but provides detailed feedback and directional decisions. They prefer the assistant to recommend approaches and implement after confirmation.

---

## Quick Commands

```bash
# Start the stack
docker compose up --build

# Trigger RAG pipeline (if regulatory_chunks is empty)
curl -X POST http://localhost:8000/api/admin/pipeline/trigger?mode=llm

# Test an assessment
curl -X POST http://localhost:8000/api/assess \
  -H "Content-Type: application/json" \
  -d '{"address": "458 N June St, Los Angeles, CA", "building_type": "SFH"}'

# Check pipeline stats
curl http://localhost:8000/api/admin/pipeline/status

# Check zone rules in DB
docker exec cover-db-1 psql -U cover -d cover -c "SELECT DISTINCT zone_class FROM zone_rules ORDER BY zone_class;"

# Check regulatory chunks
docker exec cover-db-1 psql -U cover -d cover -c "SELECT COUNT(*) FROM regulatory_chunks WHERE embedding IS NOT NULL;"
```
