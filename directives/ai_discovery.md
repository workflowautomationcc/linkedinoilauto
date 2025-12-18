# ai_discovery.md (Directive)

## Goal
**Daily AI-only article discovery for oilfield services** — a measurement pipeline, not a content creation pipeline.

This pipeline is **independent** from the 4-bucket posting pipeline (`01_source_news.md`, `02_score_and_select.md`, `03_write_linkedin_post.md`). It serves a different purpose: tracking AI/ML developments in oilfield services over time.

This directive is designed for **headless cloud execution** (e.g., GitHub Actions). It must not depend on local state, IDE execution, or interactive prompts.

## Run rules (always follow)
- This pipeline **bypasses** `directives/_run_config.md` because it is a low-volume, measurement-only job.
- All configuration comes from environment variables (see Execution section).
- No user approval required — this is an automated background measurement job.
- All credentials must be provided via environment variables (no local files).

## Scope rules (strict)

### IN SCOPE (include)
- **AI/ML must be explicit** in the article:
  - Must contain "AI", "artificial intelligence", "machine learning", "ML", "deep learning", "neural network", or equivalent explicit terminology.
  - Do NOT accept generic "digital transformation", "automation", "control system", or "IoT" unless AI/ML is explicitly mentioned.
- **Oilfield services / upstream relevance required**:
  - Must relate to oilfield services, upstream operations, drilling, completions, production, or field operations.
  - Can include operator deployments if they explicitly involve service companies or field execution.
- **Practical deployments or research**:
  - AI deployments in field operations
  - AI for predictive maintenance, anomaly detection, drilling optimization, production optimization
  - AI-enabled sensors, edge AI, computer vision for safety/inspection
  - Research papers or industry reports explicitly about AI in oilfield services

### OUT OF SCOPE (exclude)
- Generic "digital transformation" without explicit AI/ML mention
- Pure automation/control systems without AI/ML
- Downstream/refining (unless clearly impacting upstream services)
- Finance/earnings coverage with no operational AI angle
- Press releases from PR wires (prnewswire.com, businesswire.com, globenewswire.com, newswire.ca, einpresswire.com)
- Paywalled articles that cannot be accessed (mark as `access_status: blocked`)
- Articles older than 7 days from discovery date

## Time window
- Search window: **last 7 days** (broader than posting pipeline to capture more signal).
- Articles must have a published date within the last 7 days, or if unavailable, discovered within the last 7 days.

## Volume target
- **Target: 10 net-new articles per run** (after deduplication).
- If fewer than 10 found, that's acceptable — quality over quantity.
- If more than 10 found, rank by relevance and freshness, keep top 10.

## Deduplication (critical)
- Must deduplicate across **all previous runs** using a stable hash.
- Primary deduplication key: **URL** (normalized: lowercase, remove trailing slashes, remove common tracking parameters).
- Secondary check: **title similarity** (fuzzy match >90% similarity) to catch syndicated copies.
- Before writing, check existing rows in `AI_Discovery` tab:
  - If URL exists → skip (already discovered).
  - If title is very similar to existing → skip (likely duplicate).
- This ensures we track net-new discoveries over time.

## Search strategy
- Use **Tavily API** for search (paid service, but appropriate for cloud execution).
- Generate 5–10 search queries targeting:
  - "AI oilfield services"
  - "machine learning drilling operations"
  - "artificial intelligence upstream oil gas"
  - "AI predictive maintenance oilfield"
  - "ML completion optimization"
  - Variations with company names (Halliburton AI, SLB AI, Baker Hughes AI, etc.)
- De-duplicate URLs across queries before processing.
- Prefer reputable industry outlets when available, but do not over-restrict.

## Language
- **English only**.

## Output destination
- Append-only writes to a Google Sheet tab named **`AI_Discovery`**.
- One row per discovered article.
- Never delete or modify existing rows (append-only for auditability).

## What to capture per row (minimum fields)
- `discovered_at_utc` — when this run discovered the article (ISO 8601 UTC)
- `url` — normalized URL (primary deduplication key)
- `title` — article title
- `source_name` — publisher/outlet name
- `published_at` — article publish date (if available, ISO 8601)
- `snippet` — short excerpt from search results
- `ai_mentions` — brief note on what AI/ML aspect is mentioned
- `relevance_score` — simple 1–5 score (1=weak, 5=strong) based on:
  - Explicit AI/ML mention (required for inclusion)
  - Oilfield services relevance
  - Practical applicability
- `access_status` — `accessible` | `blocked` | `unknown` (for paywall detection)

Optional (nice-to-have):
- `author`
- `company_mentions` — rough extraction from title/snippet
- `search_query_used` — which query found this article

## Failure handling
- If Tavily API fails: log error, exit gracefully (do not crash).
- If Google Sheets write fails: log error, exit gracefully (do not crash).
- If deduplication check fails: default to writing (better to have duplicates than miss articles).
- Log all errors with timestamps for debugging.

## Success criteria
- Sheet `AI_Discovery` is updated with net-new articles (after deduplication).
- Minimal junk (no press releases, no generic automation).
- All articles have explicit AI/ML mention.
- All articles are oilfield services relevant.
- Deduplication prevents re-discovery of previously found articles.

## Cloud execution requirements
- Must read all credentials from environment variables:
  - `TAVILY_API_KEY` — Tavily API key
  - `GOOGLE_SHEET_ID` — Google Sheet ID (or use default from existing config)
  - `GOOGLE_CREDENTIALS_JSON` — Google OAuth credentials as JSON string (or use service account)
- No local file dependencies (no `.env` file, no local credential files).
- No interactive prompts or user input.
- Deterministic execution (same inputs → same outputs).
- Log summary counts: `found: X, rejected: Y, deduped: Z, written: W`.

## Independence from posting pipeline
- This pipeline does NOT feed into `01_source_news.md`.
- This pipeline does NOT create posts or drafts.
- This pipeline is for **measurement and tracking only**.
- Data in `AI_Discovery` tab is separate from `raw_candidates`, `selected`, `posts_draft`, etc.

