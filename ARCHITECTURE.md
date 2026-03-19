# Cover Regulatory Engine — Architecture

> Three diagrams showing the system from different perspectives: logical components, production deployment, and data flow.

---

## 1. Logical Architecture

How the system's components relate to each other.

```mermaid
graph TB
    subgraph "Frontend — Vue 3 + Vite + TypeScript"
        UI[Address Search]
        MAP[Interactive Map<br/>Mapbox GL JS]
        ASSESS[Assessment Panel]
        CHAT[Chat Panel<br/>SSE Streaming]
        FEEDBACK[Feedback Widget]
        ADMIN[Admin Panel]
        PROJ[Project Inputs]
    end

    subgraph "API Layer — FastAPI"
        REST[REST API]
        SSE[SSE Streaming]
        REST --- SSE
    end

    subgraph "Core Engine"
        RESOLVER[Rule Resolution<br/>Orchestrator]

        subgraph "Layer 1 — Deterministic"
            L1[Structured Rules<br/>Lookup]
        end

        subgraph "Layer 2 — Computational"
            L2[Conditional Rule<br/>Evaluator<br/>Shapely]
        end

        subgraph "Layer 3 — Interpretive"
            L3_RAG[RAG Retriever<br/>pgvector]
            L3_LLM[LLM Service<br/>Provider-Agnostic]
            L3_RAG --> L3_LLM
        end

        GEOM[Geometry Engine<br/>Setback Polygons<br/>Buildable Envelope]
    end

    subgraph "Parcel Service"
        GEO[Mapbox Geocoder]
        ZIMAS_C[ZIMAS Client<br/>ArcGIS REST]
        CACHE[Parcel Cache<br/>30-day TTL]
    end

    subgraph "Ingestion Pipeline"
        SCRAPER[LAMC Scraper]
        PARSER[HTML Parser]
        CHUNKER[Chunker + Embedder<br/>text-embedding-3-small]
        SCHED[Change Detector<br/>Hash Comparison]
        SCRAPER --> PARSER --> CHUNKER
        SCHED --> SCRAPER
    end

    subgraph "Data Layer — PostgreSQL + pgvector"
        DB_RULES[(Zone Rules<br/>45 seeded)]
        DB_PARCELS[(Parcels)]
        DB_CHUNKS[(Regulatory<br/>Chunks + Vectors)]
        DB_ASSESS[(Assessments +<br/>Constraints)]
        DB_CHAT[(Chat Sessions)]
        DB_FEEDBACK[(User Feedback)]
        DB_RAW[(Raw Sources)]
        DB_LOG[(Ingestion Log)]
    end

    subgraph "External Services"
        EXT_ZIMAS[ZIMAS ArcGIS<br/>LA City]
        EXT_MAPBOX[Mapbox<br/>Geocoding + Maps]
        EXT_AMLEGAL[American Legal<br/>LAMC Text]
        EXT_OPENAI[OpenAI<br/>GPT-4o + Embeddings]
    end

    UI --> REST
    MAP --> REST
    CHAT --> SSE
    FEEDBACK --> REST
    ADMIN --> REST
    PROJ --> REST
    ASSESS --> REST

    REST --> RESOLVER
    REST --> DB_FEEDBACK
    SSE --> RESOLVER

    RESOLVER --> L1
    RESOLVER --> L2
    RESOLVER --> L3_RAG
    RESOLVER --> GEOM

    L1 --> DB_RULES
    L2 --> DB_RULES
    L2 --> DB_PARCELS
    L3_RAG --> DB_CHUNKS
    L3_LLM --> EXT_OPENAI
    GEOM --> DB_PARCELS

    RESOLVER --> GEO
    GEO --> EXT_MAPBOX
    ZIMAS_C --> EXT_ZIMAS
    CACHE --> DB_PARCELS

    SCRAPER --> EXT_AMLEGAL
    CHUNKER --> EXT_OPENAI
    CHUNKER --> DB_CHUNKS
    PARSER --> DB_RAW
    SCHED --> DB_LOG
```

---

## 2. Production Deployment (AWS)

How the system would be deployed at scale. The PoC runs locally via Docker Compose; this diagram shows the productionized version.

```mermaid
graph TB
    subgraph "CDN Edge"
        CF[CloudFront CDN]
        S3[S3 Bucket<br/>Vue SPA Static Assets]
        CF --> S3
    end

    subgraph "Load Balancing"
        ALB[Application Load Balancer<br/>TLS Termination<br/>Health Checks]
    end

    subgraph "Compute — ECS Fargate"
        API1[FastAPI Container 1]
        API2[FastAPI Container 2]
        API_N[FastAPI Container N<br/>Auto-scaling]
        WORKER[Ingestion Worker<br/>Dedicated Container]
    end

    subgraph "Data — RDS + ElastiCache"
        RDS[(RDS PostgreSQL<br/>pgvector + PostGIS<br/>Multi-AZ)]
        REDIS[(ElastiCache Redis<br/>Rate Limiting<br/>Session Cache)]
    end

    subgraph "External APIs"
        OPENAI_EXT[OpenAI API]
        MAPBOX_EXT[Mapbox API]
        ZIMAS_EXT[ZIMAS ArcGIS]
    end

    subgraph "Monitoring"
        CW[CloudWatch<br/>Logs + Metrics]
        XRAY[X-Ray<br/>Tracing]
    end

    USER((User)) --> CF
    USER --> ALB

    CF --> ALB
    ALB --> API1
    ALB --> API2
    ALB --> API_N

    API1 --> RDS
    API2 --> RDS
    API_N --> RDS
    API1 --> REDIS
    WORKER --> RDS

    API1 --> OPENAI_EXT
    API1 --> MAPBOX_EXT
    API1 --> ZIMAS_EXT
    WORKER --> OPENAI_EXT

    API1 --> CW
    WORKER --> CW
    API1 --> XRAY
```

### Deployment Notes

| Component | Service | Sizing | Notes |
|-----------|---------|--------|-------|
| Frontend | S3 + CloudFront | N/A | Static SPA, globally cached |
| API | ECS Fargate | 0.5 vCPU / 1GB per task | Auto-scales 2–10 tasks |
| Ingestion | ECS Fargate | 1 vCPU / 2GB | Single long-running task |
| Database | RDS PostgreSQL 16 | db.r6g.large | pgvector + PostGIS extensions |
| Cache | ElastiCache Redis | cache.t3.micro | Rate limiting, session store |
| LLM | OpenAI API | N/A | Provider-agnostic interface allows swapping |

---

## 3. Data Flow — Assessment Request

What happens when a user enters an address and requests an assessment.

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Vue Frontend
    participant API as FastAPI
    participant GEO as Mapbox Geocoder
    participant ZIM as ZIMAS ArcGIS
    participant DB as PostgreSQL
    participant L1 as Layer 1:<br/>Deterministic
    participant L2 as Layer 2:<br/>Computation
    participant L3 as Layer 3:<br/>RAG + LLM
    participant AI as OpenAI GPT-4o
    participant SH as Shapely

    U->>FE: Enter address + building type
    FE->>API: POST /api/assess

    Note over API: Check assessment cache
    API->>DB: Lookup existing assessment
    alt Cache hit (< 1 hour old)
        DB-->>API: Cached assessment
        API-->>FE: Return cached result
    else Cache miss
        API->>GEO: Geocode address
        GEO-->>API: Coordinates (lat/lng)

        API->>ZIM: Query Layer 1102 (zoning)
        ZIM-->>API: Zone code, height district
        API->>ZIM: Query Layer 105 (parcel boundary)
        ZIM-->>API: Parcel polygon geometry

        API->>DB: Store/update parcel data

        Note over API: Three-Layer Resolution

        API->>L1: Lookup zone_class + building_type
        L1->>DB: SELECT FROM zone_rules
        DB-->>L1: Matched rules (confidence: 1.0)
        L1-->>API: Deterministic constraints

        API->>L2: Evaluate conditional rules
        L2->>DB: Get parcel dimensions
        L2-->>API: Computed constraints (confidence: 1.0)

        API->>L3: Interpret remaining regulations
        Note over L3: Savepoint isolation
        L3->>DB: pgvector similarity search
        DB-->>L3: Relevant regulatory chunks
        L3->>AI: Chunks + parcel context → prompt
        AI-->>L3: Structured interpretation
        L3-->>API: Interpreted constraints (confidence: 0.7–0.9)

        API->>SH: Compute setback geometry
        SH-->>API: Setback polygons + buildable area

        API->>DB: Store assessment + constraints
        API-->>FE: Full assessment response
    end

    FE->>FE: Render assessment panel
    FE->>FE: Render map overlays (parcel, setbacks, buildable area)
    FE-->>U: Interactive results
```

---

## 4. Data Flow — Chat Follow-Up

What happens when a user asks a follow-up question via the chat panel.

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Vue Frontend
    participant API as FastAPI
    participant DB as PostgreSQL
    participant AI as OpenAI GPT-4o

    U->>FE: Type follow-up question
    FE->>API: POST /api/chat/{assessmentId}

    API->>DB: Load assessment + constraints + parcel
    API->>DB: Load chat history
    API->>DB: pgvector search (question embedding)
    DB-->>API: Relevant regulatory chunks

    Note over API: Build LLM context:<br/>Assessment + Constraints +<br/>Chat history + Relevant chunks

    API->>AI: Streaming completion request

    loop SSE Stream
        AI-->>API: Token chunk
        API-->>FE: data: {"content": "..."}
        FE-->>U: Render streaming text
    end

    API-->>FE: data: [DONE]
    API->>DB: Store assistant message
```

---

## 5. Ingestion Pipeline

How regulatory data is scraped, parsed, and stored for the RAG system.

```mermaid
flowchart LR
    subgraph "Source"
        AML[American Legal<br/>amlegal.com<br/>LAMC Chapter 1]
    end

    subgraph "Stage 1: Scrape"
        SCRAPE[HTTP Download<br/>12 LAMC Sections]
        HASH[SHA-256 Hash<br/>Change Detection]
    end

    subgraph "Stage 2: Parse"
        PARSE[HTML Parser<br/>Section Hierarchy]
        EXTRACT[Zone Code +<br/>Topic Detection]
    end

    subgraph "Stage 3: Store"
        RAW[(Raw Source<br/>Archive)]
        PARSED[(Parsed<br/>Regulations)]
    end

    subgraph "Stage 4: Embed"
        CHUNK[Semantic Chunker<br/>~512 chars<br/>128 overlap]
        EMBED[OpenAI<br/>text-embedding-3-small<br/>1536 dimensions]
    end

    subgraph "Stage 5: Seed"
        RULES[Structured Rules<br/>Manual Curation +<br/>LLM Extraction]
    end

    subgraph "Storage"
        CHUNKS_DB[(Regulatory Chunks<br/>+ Embeddings<br/>pgvector)]
        RULES_DB[(Zone Rules<br/>45 seeded)]
        LOG_DB[(Ingestion<br/>Audit Log)]
    end

    AML --> SCRAPE
    SCRAPE --> HASH
    HASH --> PARSE
    PARSE --> EXTRACT
    SCRAPE --> RAW
    EXTRACT --> PARSED
    PARSED --> CHUNK
    CHUNK --> EMBED
    EMBED --> CHUNKS_DB
    RULES --> RULES_DB
    HASH --> LOG_DB
```

### Three-Layer Storage

| Layer | What | Why | Reprocessable? |
|-------|------|-----|----------------|
| **Raw** | Original HTML from amlegal.com | Provenance, reproducibility | Source of truth |
| **Parsed** | Structured regulation records with section hierarchy | Human-readable, searchable | From raw layer |
| **Embedded** | Semantic chunks with 1536-dim vectors | RAG similarity search | From parsed layer |

Each layer is independently reprocessable — a change in the parser doesn't require re-scraping, and a change in the embedding model doesn't require re-parsing.
