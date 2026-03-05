# RCF System Architecture

## 1. High-Level System Overview

```mermaid
graph TB
    subgraph DOCKER["Docker Container"]
        direction TB

        subgraph SCANNER["Scanner Pipeline"]
            SR[Runner<br/>Batch Orchestrator]
        end

        subgraph API["FastAPI REST API :8000"]
            APP[app.py<br/>CORS + Routing]
        end

        subgraph DB["PostgreSQL :5432"]
            PG[(rcf database)]
        end

        subgraph MKT["Marketplace"]
            MATCH[Matching Engine]
            NOTIFY[Notifications]
        end

        SR -->|writes cases,<br/>permits, properties| PG
        APP -->|reads cases,<br/>properties, lawyers| PG
        MATCH -->|reads lawyers<br/>by municipality| PG
        NOTIFY -.->|future: email| EXT_EMAIL

        SR -.->|triggers| MATCH
        MATCH -.->|triggers| NOTIFY
    end

    subgraph EXTERNAL["External Services"]
        GOVMAP[GovMap API<br/>Address → Cadastral]
        MAVAT[MAVAT API<br/>National Planning DB]
        CLAUDE[Claude API<br/>NLP Classification]
        EXT_EMAIL[SendGrid / Resend<br/>Email Service]
    end

    SR -->|resolve address| GOVMAP
    SR -->|fetch permits| MAVAT
    SR -->|classify decision| CLAUDE

    subgraph USERS["Users"]
        LAWYER[Lawyer]
        OWNER[Property Owner]
        ADMIN[Admin]
    end

    LAWYER -->|register, claim cases| APP
    OWNER -->|check eligibility| APP
    ADMIN -->|run scanner, monitor| SR

    style DOCKER fill:#1a1a2e,stroke:#16213e,color:#fff
    style SCANNER fill:#0f3460,stroke:#16213e,color:#fff
    style API fill:#533483,stroke:#16213e,color:#fff
    style DB fill:#e94560,stroke:#16213e,color:#fff
    style MKT fill:#0f3460,stroke:#16213e,color:#fff
    style EXTERNAL fill:#2d3436,stroke:#636e72,color:#fff
    style USERS fill:#2d3436,stroke:#636e72,color:#fff
```

---

## 2. Scanner Pipeline — Low-Level Design

```mermaid
flowchart TD
    START([run_scanner.py<br/>--city --limit]) --> LOAD[Load pending addresses<br/>from DB]
    LOAD --> BATCH["run_batch(addresses, concurrency)"]

    BATCH --> SEM{asyncio.Semaphore<br/>concurrency=5}

    SEM --> SCAN["scan_address(address, city)"]

    SCAN --> S1["1. upsert_property(address, city)"]
    S1 --> S2["2. address_resolver.resolve(address)"]
    S2 --> S2_CHECK{Result?}
    S2_CHECK -->|None| ERR1[mark_property_error<br/>skip address]
    S2_CHECK -->|CadastralInfo| S3["3. update_property_cadastral()<br/>block, plot, municipality"]

    S3 --> S4["4. permit_fetcher.fetch_permits()<br/>block, plot → MAVAT API"]
    S4 --> S4_LOOP["For each rejected/withdrawn permit:"]

    S4_LOOP --> S5{"5. limitations.is_within_window()<br/>decision_date + 7y > today?"}
    S5 -->|expired| SKIP[Skip permit]
    S5 -->|valid| S6["6. insert_permit()"]

    S6 --> S7["7. decision_parser.extract_decision_text()<br/>Download PDF/HTML → plain text"]
    S7 --> S7_CHECK{Text extracted?}
    S7_CHECK -->|None| S7_SKIP["Insert case as 'unclear'<br/>confidence=0.0"]
    S7_CHECK -->|text| S8["8. classifier.classify(text)<br/>Claude API → JSON"]

    S8 --> S9{"9. Classification?"}
    S9 -->|authority_rejected<br/>confidence ≥ 0.7| S10["10. refund_estimator.estimate()<br/>fee schedule × CPI"]
    S9 -->|applicant_abandoned<br/>or unclear| S10B["Insert case<br/>is_eligible=false"]

    S10 --> S11["11. insert_refund_case()<br/>is_eligible=true<br/>estimated_refund=₪X"]

    S11 --> DONE[mark_property_scanned]
    S10B --> DONE
    ERR1 --> NEXT[Next address]
    SKIP --> S4_LOOP
    S7_SKIP --> DONE
    DONE --> NEXT

    NEXT --> SEM

    style START fill:#e94560,color:#fff
    style S2 fill:#0f3460,color:#fff
    style S4 fill:#0f3460,color:#fff
    style S7 fill:#0f3460,color:#fff
    style S8 fill:#533483,color:#fff
    style S10 fill:#0f3460,color:#fff
    style S11 fill:#e94560,color:#fff
```

### Scanner Module Dependencies

```mermaid
graph LR
    RUNNER[runner.py] --> AR[address_resolver.py]
    RUNNER --> PF[permit_fetcher.py]
    RUNNER --> DP[decision_parser.py]
    RUNNER --> CL[classifier.py]
    RUNNER --> RE[refund_estimator.py]
    RUNNER --> LM[limitations.py]
    RUNNER --> REPO[repository.py]

    AR -->|httpx| GOVMAP((GovMap API))
    PF -->|httpx| MAVAT((MAVAT API))
    DP -->|httpx| DOCS((Document URLs))
    CL -->|anthropic| CLAUDE((Claude API))

    AR --> MODELS[models.py<br/>CadastralInfo]
    PF --> MODELS2[models.py<br/>PermitCreate]
    CL --> MODELS3[models.py<br/>ClassificationResult]
    RUNNER --> MODELS4[models.py<br/>PropertyCreate<br/>RefundCaseCreate]

    AR --> CONFIG[config.py]
    PF --> CONFIG
    CL --> CONFIG
    RUNNER --> CONFIG

    style RUNNER fill:#e94560,color:#fff
    style GOVMAP fill:#636e72,color:#fff
    style MAVAT fill:#636e72,color:#fff
    style DOCS fill:#636e72,color:#fff
    style CLAUDE fill:#636e72,color:#fff
```

---

## 3. Database Schema — Low-Level Design

```mermaid
erDiagram
    properties {
        UUID id PK
        TEXT address_text "NOT NULL, UNIQUE(address_text,city)"
        TEXT city "NOT NULL"
        TEXT block "cadastral gush"
        TEXT plot "cadastral helka"
        TEXT municipality_id
        DOUBLE geo_lat
        DOUBLE geo_lng
        TEXT scan_status "pending|scanned|error"
        TIMESTAMPTZ scanned_at
        TIMESTAMPTZ created_at
    }

    permits {
        UUID id PK
        UUID property_id FK
        TEXT permit_number
        DATE application_date
        DATE decision_date
        TEXT decision_type "approved|rejected|withdrawn|abandoned"
        TEXT committee_name
        TEXT source_url
        TEXT raw_decision "full committee text"
        TIMESTAMPTZ created_at
    }

    refund_cases {
        UUID id PK
        UUID permit_id FK
        UUID property_id FK
        TEXT classification "authority_rejected|applicant_abandoned|unclear"
        REAL confidence_score "0.0-1.0"
        BOOLEAN is_eligible
        INTEGER estimated_refund "ILS"
        DATE statute_expires_at "decision + 7 years"
        TEXT evidence_summary
        BOOLEAN human_verified "default false"
        TEXT status "detected|verified|claimed|recovered|expired"
        TIMESTAMPTZ created_at
    }

    lawyers {
        UUID id PK
        UUID user_id
        TEXT full_name "NOT NULL"
        TEXT email "UNIQUE, NOT NULL"
        TEXT phone
        TEXT bar_number
        TEXT_ARRAY specializations
        TEXT_ARRAY municipalities "cities covered"
        BOOLEAN is_verified "default false"
        TEXT subscription "free|premium"
        TIMESTAMPTZ created_at
    }

    owners {
        UUID id PK
        UUID user_id
        TEXT full_name
        TEXT email
        TEXT phone
        TIMESTAMPTZ created_at
    }

    case_claims {
        UUID id PK
        UUID refund_case_id FK
        UUID lawyer_id FK
        UUID owner_id FK
        TEXT status "pending|active|filed|recovered|closed"
        INTEGER recovered_amount
        INTEGER lawyer_fee
        INTEGER rcf_fee
        TIMESTAMPTZ claimed_at
        TIMESTAMPTZ recovered_at
        TIMESTAMPTZ created_at
    }

    properties ||--o{ permits : "has"
    properties ||--o{ refund_cases : "has"
    permits ||--o| refund_cases : "analyzed as"
    refund_cases ||--o{ case_claims : "claimed via"
    lawyers ||--o{ case_claims : "handles"
    owners ||--o{ case_claims : "benefits from"
```

### Key Indexes

```
properties(city)                              — filter by city
properties(block, plot)                       — cadastral lookup
properties(scan_status)                       — pending queue
permits(property_id)                          — permits per property
permits(decision_type)                        — filter rejected
refund_cases(is_eligible) WHERE TRUE          — partial index
refund_cases(status)                          — case workflow
refund_cases(property_id)                     — cases per property
lawyers USING GIN(municipalities)             — array containment
case_claims(lawyer_id)                        — lawyer portfolio
case_claims(status)                           — claim workflow
```

---

## 4. API Layer — Low-Level Design

```mermaid
graph TD
    subgraph FastAPI["FastAPI App — :8000"]
        HEALTH["GET /health"]

        subgraph CASES["/api/cases"]
            C1["GET /api/cases<br/>?city=&status=&limit=&offset="]
            C2["GET /api/cases/{id}"]
            C3["POST /api/cases/{id}/claim<br/>?lawyer_id=&owner_id="]
        end

        subgraph PROPS["/api/properties"]
            P1["GET /api/properties/{address}<br/>ILIKE search + LEFT JOIN refund_cases"]
        end

        subgraph LAWYERS["/api/lawyers"]
            L1["POST /api/lawyers<br/>Body: LawyerCreate"]
            L2["GET /api/lawyers/{id}"]
            L3["GET /api/lawyers/{id}/cases"]
        end

        subgraph OWNERS["/api/owners"]
            O1["POST /api/owners<br/>Body: OwnerCreate"]
            O2["GET /api/owners/{id}"]
            O3["GET /api/owners/{id}/cases"]
        end
    end

    C1 --> REPO[repository.py]
    C2 --> REPO
    C3 --> REPO
    L1 --> REPO
    L2 --> REPO
    L3 --> REPO
    O1 --> REPO
    O2 --> REPO
    O3 --> REPO
    P1 --> CLIENT[client.py<br/>execute]

    REPO --> CLIENT
    CLIENT --> PG[(PostgreSQL)]

    style FastAPI fill:#533483,stroke:#16213e,color:#fff
    style CASES fill:#0f3460,color:#fff
    style PROPS fill:#0f3460,color:#fff
    style LAWYERS fill:#0f3460,color:#fff
    style OWNERS fill:#0f3460,color:#fff
    style PG fill:#e94560,color:#fff
```

### API Route Details

| Method | Endpoint | Auth | Query Params | Response |
|--------|----------|------|-------------|----------|
| `GET` | `/health` | None | — | `{"status": "ok"}` |
| `GET` | `/api/cases` | — | `city`, `status`, `limit` (≤200), `offset` | `[{case + property}]` |
| `GET` | `/api/cases/{id}` | — | — | `{case + property + permit}` or 404 |
| `POST` | `/api/cases/{id}/claim` | — | `lawyer_id`, `owner_id?` | `{claim}` or 400/404 |
| `GET` | `/api/properties/{address}` | — | — | `[{property + refund_case}]` or 404 |
| `POST` | `/api/lawyers` | — | Body: JSON | `{lawyer}` |
| `GET` | `/api/lawyers/{id}` | — | — | `{lawyer}` or 404 |
| `GET` | `/api/lawyers/{id}/cases` | — | — | `[{claim + case + property}]` |
| `POST` | `/api/owners` | — | Body: JSON | `{owner}` |
| `GET` | `/api/owners/{id}` | — | — | `{owner}` or 404 |
| `GET` | `/api/owners/{id}/cases` | — | — | `[{claim + case + property + lawyer}]` |

---

## 5. Marketplace — Low-Level Design

```mermaid
sequenceDiagram
    participant Scanner as Scanner Pipeline
    participant DB as PostgreSQL
    participant Matcher as matching.py
    participant Notifier as notifications.py
    participant Email as Email Service

    Scanner->>DB: insert_refund_case(is_eligible=true)
    Note over Scanner,Matcher: Future: auto-trigger on eligible case

    Matcher->>DB: get_lawyers_for_municipality(city)
    DB-->>Matcher: [lawyers covering city]

    Matcher->>Matcher: Rank lawyers<br/>1. is_verified (desc)<br/>2. subscription=premium (desc)

    Matcher-->>Scanner: top 5 matching lawyers

    loop For each matched lawyer
        Notifier->>Email: notify_lawyer_new_case()<br/>"New case in {city}<br/>Est. refund: ₪{amount}"
    end

    Note over Notifier: Also notify owner if registered
    Notifier->>Email: notify_owner_refund_found()<br/>"Refund found at {address}"
```

### Matching Algorithm

```
find_matching_lawyers(city, limit=5):
    1. Query: lawyers WHERE city = ANY(municipalities)
    2. Sort by: (is_verified DESC, subscription='premium' DESC)
    3. Return top `limit` lawyers

match_case_to_lawyers(refund_case):
    1. Extract city from refund_case → properties → city
    2. Delegate to find_matching_lawyers(city)
```

---

## 6. Data Layer — Low-Level Design

```mermaid
graph TD
    subgraph Repository["repository.py — CRUD Operations"]
        direction LR

        subgraph PropOps["Property Ops"]
            UP[upsert_property]
            UPC[update_property_cadastral]
            MPS[mark_property_scanned]
            MPE[mark_property_error]
            GPP[get_pending_properties]
        end

        subgraph PermitOps["Permit Ops"]
            IP[insert_permit]
            UPDT[update_permit_decision_text]
            GPF[get_permits_for_property]
        end

        subgraph CaseOps["Refund Case Ops"]
            IRC[insert_refund_case]
            URCS[update_refund_case_status]
            GEC[get_eligible_cases]
            GRC[get_refund_case]
        end

        subgraph LawyerOps["Lawyer Ops"]
            IL[insert_lawyer]
            GLM[get_lawyers_for_municipality]
            GL[get_lawyer]
        end

        subgraph OwnerOps["Owner Ops"]
            IO[insert_owner]
            GO[get_owner]
        end

        subgraph ClaimOps["Claim Ops"]
            ICC[insert_case_claim]
            GCL[get_claims_for_lawyer]
            GCO[get_claims_for_owner]
        end
    end

    subgraph Client["client.py"]
        CONN["get_conn()<br/>psycopg singleton<br/>autocommit=True"]
        EXEC["execute(sql, params)<br/>→ list[dict]"]
        EXEC1["execute_one(sql, params)<br/>→ dict | None"]
    end

    Repository --> Client
    Client --> PG[(PostgreSQL<br/>dict_row mode)]

    subgraph Models["models.py — Pydantic v2"]
        PC[PropertyCreate]
        PMC[PermitCreate]
        RCC[RefundCaseCreate]
        LC[LawyerCreate]
        OC[OwnerCreate]
        CCC[CaseClaimCreate]
        CI[CadastralInfo]
        CR[ClassificationResult]
    end

    UP -.->|accepts| PC
    IP -.->|accepts| PMC
    IRC -.->|accepts| RCC
    IL -.->|accepts| LC
    IO -.->|accepts| OC
    ICC -.->|accepts| CCC

    style Repository fill:#0f3460,color:#fff
    style Client fill:#533483,color:#fff
    style PG fill:#e94560,color:#fff
    style Models fill:#2d3436,color:#fff
```

---

## 7. Docker Deployment — Low-Level Design

```mermaid
graph TD
    subgraph Image["Docker Image: rcf"]
        subgraph Base["python:3.11-slim"]
            PG_BIN["PostgreSQL 17<br/>/usr/lib/postgresql/17/bin/"]
            PY["Python 3.11 + pip packages"]
        end

        subgraph Entrypoint["docker-entrypoint.sh"]
            E1["[1/5] Start PostgreSQL<br/>initdb → pg_ctl start<br/>CREATE USER rcf<br/>CREATE DATABASE rcf"]
            E2["[2/5] Run migrations<br/>001_initial_schema.sql"]
            E3["[3/5] Seed addresses<br/>seed_addresses.py → 10 samples"]
            E4{"[4/5] ANTHROPIC_API_KEY<br/>set?"}
            E4Y["Run scanner<br/>--limit $SCAN_LIMIT"]
            E4N["Skip scanner"]
            E5["[5/5] Start uvicorn<br/>0.0.0.0:8000"]

            E1 --> E2 --> E3 --> E4
            E4 -->|yes| E4Y --> E5
            E4 -->|no| E4N --> E5
        end
    end

    subgraph Env["Environment Variables"]
        EV1["PGDATA=/var/lib/postgresql/data"]
        EV2["DATABASE_URL=postgresql://rcf:rcf@localhost:5432/rcf"]
        EV3["ANTHROPIC_API_KEY= (optional)"]
        EV4["SCAN_CITY= (optional)"]
        EV5["SCAN_LIMIT=10 (optional)"]
    end

    subgraph Ports["Exposed Ports"]
        P8000["8000 → FastAPI + Swagger"]
    end

    Env --> Image
    Image --> P8000

    style Image fill:#1a1a2e,stroke:#16213e,color:#fff
    style Base fill:#0f3460,color:#fff
    style Entrypoint fill:#533483,color:#fff
    style Env fill:#2d3436,color:#fff
    style P8000 fill:#e94560,color:#fff
```

### Run Commands

```bash
# Basic (API only, no scanning)
docker build -t rcf .
docker run -d --name rcf -p 8000:8000 rcf

# With scanner
docker run -d --name rcf -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e SCAN_CITY="תל אביב" \
  -e SCAN_LIMIT=50 \
  rcf
```
