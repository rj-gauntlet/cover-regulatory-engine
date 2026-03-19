# Cover Regulatory Engine

A fullstack buildability assessment tool for Los Angeles residential parcels. Enter an address, get a structured analysis of zoning constraints (setbacks, height limits, FAR, density, parking) with cited LAMC sections, interactive map overlays, and LLM-powered follow-up chat.

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys (see Environment Variables below)

# 2. Launch all services
docker compose up --build

# 3. Open the app
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Vue 3)                        │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Address  │ │  Assessment  │ │   Chat   │ │  Interactive  │  │
│  │ Search   │ │    Panel     │ │  Panel   │ │     Map       │  │
│  └────┬─────┘ └──────┬───────┘ └────┬─────┘ └───────┬───────┘  │
│       │              │              │               │           │
│       └──────────────┴──────────────┴───────────────┘           │
│                              │                                  │
└──────────────────────────────┼──────────────────────────────────┘
                               │ REST + SSE
┌──────────────────────────────┼──────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Hybrid Rule Resolution Engine               │   │
│  │  ┌─────────────┐ ┌────────────┐ ┌────────────────────┐  │   │
│  │  │   Layer 1   │ │  Layer 2   │ │     Layer 3        │  │   │
│  │  │Deterministic│ │ Conditional│ │  RAG + LLM         │  │   │
│  │  │   Lookup    │ │ Computation│ │  Interpretation    │  │   │
│  │  └─────────────┘ └────────────┘ └────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Parcel   │ │ Geocoder │ │  ZIMAS   │ │ Ingestion Pipeline│  │
│  │ Service  │ │ (Mapbox) │ │  Client  │ │ (Scrape→Parse→    │  │
│  │          │ │          │ │          │ │  Embed→Store)     │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────┐
│                    PostgreSQL + pgvector                        │
│  ┌────────┐ ┌──────────┐ ┌────────────┐ ┌───────────────────┐  │
│  │Parcels │ │Zone Rules│ │ Regulatory │ │   Assessments +   │  │
│  │        │ │(45 seeded│ │   Chunks   │ │   Constraints +   │  │
│  │        │ │  rules)  │ │ (embedded) │ │   Chat Sessions   │  │
│  └────────┘ └──────────┘ └────────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Hybrid Rule Resolution Engine

The core innovation is a three-layer engine that maximizes accuracy:

| Layer | Strategy | Confidence | Use Case |
|-------|----------|------------|----------|
| **Layer 1** | Deterministic lookup | 100% | Known rules (setbacks, height, FAR) matched by zone class |
| **Layer 2** | Conditional computation | 90-95% | Rules that depend on lot dimensions, slope, or building type |
| **Layer 3** | RAG + LLM interpretation | 70-85% | Edge cases, overlays, specific plan areas, nuanced regulations |

Layer 1 fires first with seeded LAMC rules, Layer 2 applies computed adjustments, and Layer 3 fills gaps using vector-similar regulatory text chunks sent to GPT-4o. A database savepoint isolates Layer 3 failures so assessments always return Layer 1+2 results at minimum.

### Data Flow

```
User enters address
  → Mapbox Geocoding API (address → lat/lng)
  → ZIMAS ArcGIS REST API (lat/lng → zone code, parcel boundary)
    ├─ Layer 1102: Zoning classification
    └─ Layer 105: Landbase (individual parcel geometry)
  → Hybrid Engine resolves constraints
  → Setback geometry computed via Shapely (parcel polygon buffered inward)
  → Assessment stored in PostgreSQL
  → Response with constraints, citations, GeoJSON geometries
```

## Tech Stack

Chosen to align with Cover's production stack:

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Frontend | **Vue 3** + TypeScript + Vite | Cover uses Vue |
| Styling | **Tailwind CSS** | Rapid, consistent UI |
| Maps | **Mapbox GL JS** | Interactive, GeoJSON-native |
| Backend | **FastAPI** (Python) | Cover uses FastAPI; async-native |
| ORM | **SQLAlchemy** 2.0 async | Cover uses SQLAlchemy |
| Database | **PostgreSQL** + pgvector | Cover uses Postgres; pgvector for RAG |
| LLM | **OpenAI GPT-4o** | Best code understanding for regulation parsing |
| Embeddings | **text-embedding-3-small** | Cost-effective, high-quality embeddings |
| GIS | **Shapely**, ArcGIS REST | Geometry computation, ZIMAS integration |
| Deployment | **Docker Compose** | One-command local orchestration |

## Features

### Core

- **Address-based assessment**: Enter any LA residential address, get structured buildability analysis
- **Cited constraints**: Every constraint references specific LAMC sections with relevant text excerpts
- **Confidence scoring**: Each constraint shows determination type (deterministic/interpreted) and confidence %
- **Setback visualization**: Computed setback polygons rendered as colored map overlays

### Bonus Features

- **BF-01: Project Inputs Panel** — Configure stories, bedrooms, bathrooms, and proposed sqft. Affects assessment dynamically.
- **BF-02: Feedback Widget** — Thumbs up/down per constraint with optional comment. Stored in DB for review.
- **BF-03: Chat Panel** — SSE-streaming follow-up questions. LLM receives full assessment context + regulatory chunks.
- **BF-04: Interactive Map** — Hover tooltips, click-to-inspect zones, setback distance labels, buildable area polygon, togglable legend with imperial scale.
- **BF-05: Exportable GeoJSON** — Download assessment as a GeoJSON FeatureCollection with parcel boundary, constraints, and metadata.
- **BF-06: Admin Panel** — Pipeline status dashboard, zone rules browser with verification toggle, feedback review table, re-ingestion trigger.

## Environment Variables

Create a `.env` file at the project root:

```bash
# Required
OPENAI_API_KEY=sk-...              # OpenAI API key for GPT-4o and embeddings
MAPBOX_ACCESS_TOKEN=pk.eyJ...      # Mapbox token for maps + geocoding

# Optional (defaults shown)
POSTGRES_DB=cover
POSTGRES_USER=cover
POSTGRES_PASSWORD=cover
DATABASE_URL=postgresql://cover:cover@localhost:5432/cover
```

## Project Structure

```
cover/
├── docker-compose.yml              # Orchestrates all services
├── .env                            # Environment variables (not committed)
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan (auto-migration, seeding)
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings
│   │   │   └── database.py         # Async engine + session factory
│   │   ├── api/
│   │   │   ├── deps.py             # Dependency injection (session, LLM)
│   │   │   └── routes/
│   │   │       ├── assess.py       # POST /api/assess, GET /api/assess/:id, GET /api/assess/:id/geojson
│   │   │       ├── parcel.py       # GET /api/parcel/search, GET /api/parcel/:apn
│   │   │       ├── chat.py         # POST /api/chat/:id (SSE stream), GET /api/chat/:id/history
│   │   │       ├── feedback.py     # POST /api/feedback
│   │   │       └── admin.py        # Pipeline status, rules CRUD, feedback list, re-ingestion
│   │   ├── models/
│   │   │   ├── database.py         # SQLAlchemy ORM models (12 tables)
│   │   │   └── schemas.py          # Pydantic request/response schemas
│   │   └── services/
│   │       ├── engine/
│   │       │   ├── resolver.py     # Three-layer hybrid engine orchestrator
│   │       │   ├── rules.py        # Layer 1: Deterministic rule lookup
│   │       │   ├── compute.py      # Layer 2: Conditional computation
│   │       │   ├── retriever.py    # Layer 3: RAG retrieval + LLM interpretation
│   │       │   └── geometry.py     # Setback polygon computation (Shapely)
│   │       ├── parcel/
│   │       │   ├── service.py      # Parcel CRUD + caching
│   │       │   ├── geocoder.py     # Mapbox geocoding
│   │       │   └── zimas.py        # ZIMAS ArcGIS REST client
│   │       ├── llm/
│   │       │   ├── base.py         # Provider-agnostic LLM interface
│   │       │   └── openai_provider.py  # OpenAI implementation (completion, streaming, embeddings)
│   │       └── ingestion/
│   │           ├── scraper.py      # LAMC HTML scraper
│   │           ├── parser.py       # Regulation text parser + chunker
│   │           ├── embedder.py     # Embedding pipeline + full ingestion orchestrator
│   │           └── scheduler.py    # Background re-ingestion scheduler
│   ├── data/seed/
│   │   ├── seeder.py              # Seeds 45 zone rules on startup
│   │   └── zone_rules.py          # Structured LAMC rules (R1, R2, RD, RE zones)
│   ├── db/
│   │   └── init.sql               # PostgreSQL extensions (pgvector, uuid-ossp)
│   └── scripts/
│       └── init_db.py             # Manual DB init script
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.ts                # App entry point
│       ├── App.vue                # Root component (header + router view)
│       ├── style.css              # Tailwind + custom design tokens
│       ├── router/index.ts        # Vue Router (/ and /admin)
│       ├── services/api.ts        # API client (REST + SSE streaming)
│       ├── types/index.ts         # TypeScript interfaces
│       ├── components/
│       │   ├── AddressSearch.vue   # Search bar with submit
│       │   ├── AssessmentPanel.vue # Constraint groups + confidence + GeoJSON export
│       │   ├── ConstraintCard.vue  # Expandable card: rule text, reasoning, citations, feedback
│       │   ├── ChatPanel.vue       # SSE streaming chat with message history
│       │   ├── MapView.vue         # Mapbox map with layers, legend, tooltips, click interaction
│       │   └── ProjectInputs.vue   # Stories/bedrooms/bathrooms/sqft form
│       └── views/
│           ├── HomeView.vue        # Main assessment view
│           └── AdminView.vue       # Admin panel (pipeline, rules, feedback)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/assess` | Create buildability assessment |
| GET | `/api/assess/:id` | Retrieve assessment by ID |
| GET | `/api/assess/:id/geojson` | Export as GeoJSON FeatureCollection |
| GET | `/api/parcel/search?address=...` | Search parcel by address |
| POST | `/api/chat/:assessmentId` | Send chat message (SSE stream response) |
| GET | `/api/chat/:assessmentId/history` | Get chat history |
| POST | `/api/feedback` | Submit constraint feedback |
| GET | `/api/admin/pipeline/status` | Pipeline stats |
| POST | `/api/admin/pipeline/trigger` | Trigger re-ingestion |
| GET | `/api/admin/rules` | List zone rules |
| PUT | `/api/admin/rules/:id` | Update/verify a rule |
| GET | `/api/admin/feedback` | List user feedback |
| GET | `/api/health` | Health check |

## Design Decisions

1. **Hybrid engine over pure LLM**: Zoning rules are deterministic — a 5ft setback is always 5ft. Using an LLM for this introduces unnecessary hallucination risk. The three-layer approach gives 100% confidence on known rules while still handling edge cases.

2. **ZIMAS Landbase layer for parcel geometry**: The ZIMAS API doesn't expose a clean "parcels" layer. Layer 105 (Landbase) provides individual lot polygons that match real property boundaries, while Layer 1102 provides zoning classification.

3. **Savepoint isolation for Layer 3**: RAG + LLM is inherently unreliable. Wrapping it in a database savepoint ensures that SQL errors in vector similarity search don't corrupt the main assessment transaction.

4. **SSE over WebSocket for chat**: SSE is simpler, works through proxies, and is sufficient for one-directional streaming (server → client). The client sends messages via POST.

5. **Frontend state in Vue refs (no Pinia)**: The app has a single primary view with straightforward state flow. A global store would be overengineering at this scale.

6. **Seeded rules vs. dynamic extraction**: 45 rules are seeded on startup covering R1, R2, RD, RE zones. The ingestion pipeline can extract more rules from scraped LAMC text, but seeded rules ensure the system works immediately without any API calls.

## Testing

To test the system with different LA residential zones:

| Zone | Example Address | Expected Constraints |
|------|----------------|---------------------|
| R1 | 11348 Elderwood St, Los Angeles | 5ft front, 15ft rear, 5ft side setbacks; 45ft height; 3:1 FAR |
| R2 | 1234 S Hoover St, Los Angeles | 15ft front, 15ft rear, 5ft side; 45ft height; higher density |
| RD | Various Hancock Park addresses | Reduced density restrictions |
| RE | Large lot areas (Bel Air, etc.) | Larger setbacks, lower density |

## Known Limitations

- **ZIMAS API reliability**: The ZIMAS ArcGIS REST API occasionally returns empty results for valid parcels. The app uses envelope queries (small bounding box) rather than point queries to improve reliability.
- **Zone prefix handling**: Qualified zone codes like `[Q]R1-1` have the prefix stripped for rule matching. Some qualified conditions may not be captured.
- **Parcel boundary accuracy**: Landbase layer 105 provides approximate boundaries; they may not match surveyed property lines exactly.
- **LLM interpretation cost**: Layer 3 calls GPT-4o, which incurs API costs. Without an API key, the system degrades gracefully to Layer 1+2 results only.

## License

Built for the Cover Engineering hiring challenge. Not licensed for production use.
