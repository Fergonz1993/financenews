# Local Demo (Backend + Frontend + Search)

This repository now includes a one-shot/interactive script to run both services and perform a data sanity check.

## 1) Configure environment

```bash
cp .env.example .env
```

Edit `.env` as needed:
- Set `NEWS_INGEST_FEEDS` to your preferred RSS sources.
- Keep `NEWS_INGEST_ENABLE_FULL_TEXT_FETCH=true` if you want article body fallback scraping.
- `NEWS_INGEST_INTERVAL_SECONDS=0` for manual demo mode.
- Use SEC placeholders if you want to test SEC endpoints later (`SEC_*`).

## 2) Run full local demo

```bash
DEMO_ONCE=1 ./scripts/run_demo_local.sh
```

What this command does:
- Starts FastAPI backend on `127.0.0.1:8000`.
- Starts Next.js frontend on `127.0.0.1:3000`.
- Runs `POST /api/ingest` using URL-encoded `source_urls` so `&` chars do not break query parsing.
- Prints:
  - `/api/sources`
  - `/api/topics`
  - `/api/articles?search=SEC&limit=5`

Set `DEMO_ONCE=0` (or omit it) if you want the script to remain running as a local server.

## 3) Open frontend

- App: `http://127.0.0.1:3000`
- API status: `http://127.0.0.1:8000/health`

## Why no full SEC web scraper yet?

SEC publishes structured APIs (mostly free) and some press pages/rules around scraping.  
This repo keeps the current ingest path RSS-first and adds optional full-text HTML fallback per article.  
That gives legal/operational stability while still delivering full text enrichment.
