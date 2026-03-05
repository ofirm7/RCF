# RCF Web Frontend

> Placeholder — the frontend will be built here.

## Planned Stack

- **Framework**: Next.js (React)
- **Styling**: Tailwind CSS
- **Auth**: Supabase Auth (email + Google)
- **API**: Connects to the FastAPI backend at `/api/*`

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page — "Check if you're owed a refund" |
| `/search` | Address search — lookup eligibility |
| `/case/:id` | Case detail — evidence, estimated refund, connect with lawyer |
| `/lawyers` | Lawyer portal — browse available cases, manage pipeline |
| `/lawyers/register` | Lawyer registration form |
| `/dashboard` | Admin dashboard — KPIs, case quality, payments |

## Setup

```bash
cd web
npm install
npm run dev
```

Will be implemented in a future phase.
