# RCF — Refund Claim Finder
## Business Plan

---

## 1. Executive Summary

RCF (Refund Claim Finder) is an Israeli PropTech startup that automatically scans every address in Israel to detect unclaimed building permit fee refunds. The platform stores eligible cases in a centralized database and operates a marketplace connecting property owners with specialized lawyers who recover the funds. Property owners use the platform for free; RCF earns a success fee as a percentage of recovered refunds from the lawyer side.

Millions of shekels in legitimate refunds sit unclaimed in municipal coffers due to information asymmetry, bureaucratic complexity, and lack of awareness. RCF eliminates these barriers through automation and creates a win-win-win: property owners recover money they didn't know they were owed, lawyers gain a steady pipeline of pre-qualified cases, and municipalities clear outstanding liabilities.

---

## 2. Problem Statement

When building permit applications in Israel are rejected by local planning committees, applicants are legally entitled to refunds of fees paid ("agrot binyan"). However, the vast majority of these refunds go unclaimed because:

- **Lack of awareness**: Property owners don't know refunds exist or that they qualify
- **Bureaucratic complexity**: The process requires navigating 120+ local planning committees, each with different procedures
- **Legal nuance**: A 2024 Supreme Court ruling draws a fine line between authority-initiated rejections (refund owed) and applicant abandonment (no refund) — most owners can't make this distinction
- **Time pressure**: A 7-year statute of limitations means eligible claims expire silently
- **Fragmented data**: Permit decisions are scattered across municipal databases with no centralized lookup

The result: significant capital remains locked in local authority budgets that legally belongs to property owners.

---

## 3. Solution

RCF is a three-layer platform:

1. **Automated Scanner** — Continuously crawls national and municipal planning databases, analyzing every address in Israel to identify building permit fee refund eligibility
2. **Eligibility Database** — A centralized, searchable repository of all identified refund opportunities with supporting evidence
3. **Lawyer-Owner Marketplace** — Connects property owners with vetted lawyers who specialize in municipal fee recovery, handling the entire claims process

The system uses NLP to analyze planning committee decisions, classify rejection types per the 2024 Supreme Court ruling, and flag actionable cases — all within the 7-year statute of limitations window.

---

## 4. How It Works

### For Property Owners (Free)
1. **Discover** — Owner searches their address on RCF or receives an outbound notification that a refund opportunity exists
2. **Review** — Platform shows the estimated refund amount, supporting evidence, and likelihood of success
3. **Connect** — Owner is matched with a vetted lawyer who handles the entire claim process at no upfront cost

### For Lawyers (Success Fee)
1. **Browse** — Lawyers access a pipeline of pre-qualified refund cases with supporting documentation
2. **Claim** — Lawyer takes on a case and handles the municipal refund process
3. **Collect** — Upon successful recovery, RCF takes a percentage of the lawyer's fee

### The RCF Engine (Behind the Scenes)
1. **Ingest** — Convert every Israeli address to cadastral plot/block numbers via GovMap APIs
2. **Analyze** — Query MAVAT (national planning database), municipal open data portals, and committee protocols
3. **Classify** — NLP engine reads committee decisions to determine if rejection was authority-initiated (refund eligible) or applicant-abandoned (not eligible)
4. **Store** — Eligible cases are inserted into the RCF database with all supporting evidence
5. **Match** — Algorithm pairs cases with the best-fit lawyers based on municipality, case complexity, and lawyer track record

---

## 5. Revenue Model

**Success-fee marketplace model — free for property owners.**

| Revenue Stream | Description | Estimated Take Rate |
|---|---|---|
| **Lawyer success fee** | Percentage of the lawyer's fee on each successful recovery | 20–30% of lawyer fee |
| **Premium lawyer placement** | Priority listing and case routing for lawyers willing to pay a subscription | ₪500–2,000/month |
| **Data licensing** (future) | Anonymized municipal planning analytics for real estate firms | TBD |

**Why free for owners?**
- Maximizes platform adoption and database completeness
- Property owners have zero incentive to use the platform if there's upfront cost for uncertain outcomes
- Lawyers are willing to pay because RCF delivers pre-qualified, documented cases — dramatically reducing their customer acquisition cost

**Example unit economics:**
- Average refund amount: ₪15,000–50,000
- Lawyer typically charges 15–25% of recovered amount
- RCF takes 25% of lawyer's fee
- **RCF revenue per case: ₪560–3,125**

---

## 6. Market Size

### Total Addressable Market (TAM)
- ~80,000 building permit applications filed annually in Israel
- Historical backlog: 7 years × 80,000 = ~560,000 permits in the eligibility window
- Estimated rejection/withdrawal rate: 15–25%
- **Eligible cases in backlog: ~84,000–140,000**
- Average refund: ₪25,000
- **TAM: ₪2.1B–3.5B in unclaimed refunds**

### Serviceable Addressable Market (SAM)
- Targeting the top 30 municipalities (covering ~60% of permits) in the first 3 years
- Data accessibility limits coverage to municipalities with digital records
- **SAM: ~₪1.3B–2.1B**

### Serviceable Obtainable Market (SOM) — Year 3
- Realistic penetration: 5–10% of SAM
- **SOM: ₪65M–210M in recovered refunds**
- **RCF Year 3 revenue at 25% lawyer take rate × 20% RCF cut: ₪3.25M–10.5M**

*Note: These are rough estimates. Actual figures depend on municipal data access and refund amounts, which vary significantly.*

---

## 7. Competitive Landscape

| Player | Approach | Weakness |
|---|---|---|
| **Tax consulting firms** | Manual case-by-case review | Slow, expensive, can't scale, limited to clients who already know they're owed money |
| **Municipal lawyers** | Handle refunds as part of broader practice | Not specialized, no proactive case discovery |
| **Property management firms** | May flag refunds for managed properties | Limited to their portfolio, not systematic |

**RCF's competitive advantages:**
- **Proactive discovery**: We find cases owners don't know about — competitors wait for clients to come to them
- **Scale**: Automated scanning covers every address in Israel, not just known cases
- **Speed**: Algorithmic triage in seconds vs. weeks of manual review
- **Data moat**: The database of eligible cases grows over time and is extremely difficult to replicate

---

## 8. Technical Architecture (High Level)

```
┌─────────────────────────────────────────────────┐
│                   DATA INGESTION                 │
│                                                  │
│  GovMap API ──→ Address-to-Cadastral Converter   │
│  MAVAT DB   ──→ Permit & Decision Scraper        │
│  Municipal  ──→ Committee Protocol Crawler        │
│  Open Data  ──→ CKAN API Integration             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│                 ANALYSIS ENGINE                   │
│                                                  │
│  NLP Classifier ──→ Rejection Type Detection     │
│  Rule Engine    ──→ Statute of Limitations Check │
│  Estimator      ──→ Refund Amount Calculation    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              ELIGIBILITY DATABASE                 │
│                                                  │
│  Property Records │ Refund Cases │ Evidence Docs  │
│  Owner Contacts   │ Case Status  │ Lawyer Matches │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              MARKETPLACE PLATFORM                │
│                                                  │
│  Owner Portal ──→ Search, Review, Connect        │
│  Lawyer Portal──→ Browse Cases, Manage Pipeline  │
│  Admin Panel  ──→ Case Tracking, Payments, KPIs  │
└─────────────────────────────────────────────────┘
```

**Key technical components:**
- Address-to-cadastral conversion via GovMap APIs
- NLP pipeline for Hebrew-language committee decision analysis
- Statute of limitations filter (7-year rolling window)
- Matching algorithm for lawyer-case pairing
- Human-in-the-loop verification layer for edge cases

---

## 9. Legal & Regulatory Considerations

### Favorable Factors
- **2024 Supreme Court ruling** clearly defines when refunds are owed — this is our classification benchmark
- **Public data**: Planning committee decisions and protocols are public records
- **No unauthorized practice of law**: RCF is a technology platform that connects parties, not a law firm

### Constraints to Navigate
- **Privacy Protection Law**: Financial transaction data (who paid what fees) is protected. RCF cannot access municipal payment records directly — we identify *eligibility*, lawyers handle the verification of actual payments with client authorization
- **Data fragmentation**: 120+ municipalities with inconsistent data standards. Must build custom adapters per municipality
- **Professional licensing**: Must ensure the platform doesn't cross into unauthorized legal advice. All legal work is performed by licensed lawyers.

### Regulatory Strategy
- Engage Israel Bar Association early for compliance guidance
- Implement clear disclaimers: RCF provides information, not legal advice
- Build relationships with municipal legal departments for smoother claims processing

---

## 10. Go-to-Market Strategy

### Phase 1: Foundation (Months 1–6)
- Build scanner for top 5 municipalities (Tel Aviv, Jerusalem, Haifa, Rishon LeZion, Petah Tikva)
- Onboard 10–20 specialized lawyers as launch partners
- Validate refund detection accuracy with manual case review
- **Target: 500 eligible cases identified, 50 cases initiated**

### Phase 2: Growth (Months 7–12)
- Expand to top 20 municipalities
- Launch owner-facing portal with address search
- Begin outbound notifications to property owners (direct mail, email)
- PR campaign: "Are you owed money from your municipality?"
- **Target: 5,000 eligible cases, 500 active cases**

### Phase 3: Scale (Months 13–24)
- Cover 60+ municipalities
- Lawyer self-service onboarding
- Mobile app for owners
- API partnerships with real estate platforms (Yad2, Madlan)
- **Target: 25,000 eligible cases, 2,500 active cases**

### Phase 4: Expansion (Months 25–36)
- Full national coverage (120+ municipalities)
- Expand to adjacent fee types (development levies, infrastructure charges)
- Explore international markets with similar municipal fee structures

### Customer Acquisition Channels
- **Property owners**: SEO, social media, partnerships with real estate agents, direct mail to flagged addresses
- **Lawyers**: Legal industry conferences, bar association partnerships, LinkedIn outreach, referral bonuses

---

## 11. Team Requirements

### Founding Team (Pre-seed)
| Role | Focus |
|---|---|
| **CEO / Business Lead** | Strategy, fundraising, lawyer partnerships |
| **CTO / Tech Lead** | System architecture, data pipeline, NLP |
| **Legal Advisor** (part-time) | Regulatory compliance, Bar Association liaison |

### Early Hires (Seed Stage)
| Role | Focus |
|---|---|
| **Backend Engineer** | Data ingestion, API integrations, database |
| **NLP / ML Engineer** | Hebrew NLP, decision classification models |
| **Business Development** | Lawyer onboarding, municipal relationships |
| **Product Designer** | Owner and lawyer portal UX |

### Growth Hires (Series A)
- Sales team for lawyer partnerships
- Customer success for property owners
- Data engineering team for municipal adapter maintenance
- Operations manager for case quality assurance

---

## 12. Financial Projections (3-Year)

| Metric | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Municipalities covered | 10 | 40 | 100+ |
| Eligible cases identified | 5,000 | 25,000 | 80,000 |
| Active cases (lawyer engaged) | 300 | 2,500 | 10,000 |
| Successful recoveries | 100 | 1,200 | 5,000 |
| Avg refund recovered | ₪25,000 | ₪25,000 | ₪25,000 |
| Total recovered | ₪2.5M | ₪30M | ₪125M |
| **RCF Revenue** | **₪125K** | **₪1.5M** | **₪6.25M** |
| Operating costs | ₪1.5M | ₪3M | ₪5M |
| **Net** | **-₪1.375M** | **-₪1.5M** | **+₪1.25M** |

*Assumes: lawyers charge 20% of recovery, RCF takes 25% of lawyer fee = 5% effective take rate on recovered amount. Breakeven expected mid-Year 3.*

### Funding Requirements
- **Pre-seed**: ₪500K — MVP, initial data pipeline, 5-municipality proof of concept
- **Seed**: ₪2–3M — Scale to 40 municipalities, hire core team, launch marketplace
- **Series A**: ₪8–12M — National coverage, adjacent fee types, growth marketing

---

## 13. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Municipal data access blocked** | Cannot scan addresses | Build direct relationships with municipalities; use only public data sources; FOI requests as backup |
| **NLP accuracy too low** | False positives erode trust | Human-in-the-loop verification; start with high-confidence cases only; continuous model training |
| **Lawyers don't join platform** | No supply side | Offer first 10 cases free; demonstrate pre-qualified leads; competitive referral fees |
| **Property owners don't engage** | No demand side | Platform is free; proactive outbound; partner with real estate agents who have owner relationships |
| **Regulatory pushback** | Cease and desist | Proactive Bar Association engagement; clear "information platform" positioning; legal counsel on board |
| **Competitor copies model** | Market share loss | Data moat (historical database); first-mover network effects; lawyer relationships |
| **Low actual refund amounts** | Unit economics don't work | Validate average refund sizes in Phase 1 before scaling; pivot to higher-value fee types if needed |

---

## 14. Milestones & Timeline

```
Month 1–2    ║ MVP: Scanner for Tel Aviv + basic DB
Month 3–4    ║ NLP classifier for committee decisions (Hebrew)
Month 5–6    ║ Lawyer portal MVP, onboard 10 pilot lawyers
             ║ ★ MILESTONE: First 50 cases filed
Month 7–9    ║ Owner portal launch, expand to 10 municipalities
Month 10–12  ║ Seed round, marketing launch
             ║ ★ MILESTONE: First 100 successful recoveries
Month 13–18  ║ Scale to 40 municipalities, mobile app
             ║ ★ MILESTONE: ₪10M+ in total recovered refunds
Month 19–24  ║ National expansion, API partnerships
             ║ ★ MILESTONE: 2,500 active cases, platform profitability path clear
Month 25–36  ║ Full national coverage, adjacent fee types
             ║ ★ MILESTONE: Breakeven, ₪100M+ recovered
```

---

## Appendix: Key Legal References

- **Planning and Building Law, 1965** — Governs building permit fees and planning committee authority
- **Supreme Court Ruling, July 2024** — Established that refunds are due only when authorities actively reject applications on planning grounds; not when applicants abandon projects
- **Privacy Protection Law, 1981** — Restricts access to financial transaction data; shapes system design toward eligibility detection (not payment verification)
- **Statute of Limitations (7 years)** — Civil claims window that defines the historical search depth

---

*RCF — Turning bureaucratic complexity into recovered capital.*
