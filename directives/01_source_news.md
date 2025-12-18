# 01_source_news.md (Directive)

## Goal
Collect fresh **oilfield-services–relevant** news inputs for LinkedIn content creation.

This step only **discovers and logs candidate links**. It does **not** do deep reading, scoring, or post writing.

## Run rules (always follow)
- Before doing anything, read `directives/_run_config.md`.
- Obey the run mode limits (TEST vs PROD) and **do not exceed them**.
- Do not perform any paid API calls or heavy scraping unless `_run_config.md` explicitly allows it.

## Time window
- Search window: **last 24 hours**.

## Output destination
- Store results in a **Google Sheet** (create if missing, otherwise append).
- One row per candidate item.

## Buckets (used as search lanes, not final classification)
Run **separate searches** for each lane and store a hint column:

1) `upstream` (drilling / completions / well construction / intervention / production ops that touch services)
2) `general` (oilfield services companies, contracts, operations, incidents, tech adoption, supply chain impacting field work)
3) `ai_automation` (must be clearly AI-related in wording; see lane requirement below)
4) `regulation` (policy, compliance, standards, safety/environment regs impacting upstream ops/services)

Add a column `query_bucket_hint` with one of the above values. This is only a hint; final tagging happens later.

## Scope filter (critical) — apply to all lanes
**Purpose:** prevent drift into downstream/refining and generic macro news.

### IN SCOPE (include)
- Oilfield services activity, including (non-exhaustive):
  - drilling services, directional drilling, MWD/LWD
  - completions, cementing, stimulation/fracturing
  - wireline, slickline, coiled tubing, intervention
  - well testing, integrity services, inspection for upstream assets
  - production chemicals, artificial lift services
  - upstream logistics/supply chain that affects field execution
- Upstream operator news **only when** it affects services/field execution:
  - contract awards/tenders that involve service companies
  - operational changes tied to field activity (rig programs, completion campaigns)
  - safety/HSE incidents with operational implications
  - deployment/adoption of tools/workflows used in field execution

### OUT OF SCOPE (exclude unless the item clearly impacts upstream field ops/services)
- Refining, petrochemicals, retail fuels / downstream ops
- Macro oil price / commodities commentary with no OFS-ops impact
- Pure finance/earnings coverage with no mention of:
  - operations, contracts, deployments, incidents, or field execution implications
- Discovery/reserves headlines with no services/tech/field execution angle

**Enforcement in this step:**
- If title/snippet is clearly OUT OF SCOPE → do not log it.
- If ambiguous → allow it through to the sheet (later stages can reject with full context).

## Query strategy (broad web search)
For each lane, generate multiple search queries and collect candidate links.
Keep the search broad, then let later stages filter harder.

- Use multiple queries per lane (e.g., 5–10).
- De-duplicate URLs (and near-duplicate syndicated copies).
- Prefer reputable industry outlets when available, but do not over-restrict (especially for `ai_automation`).

### AI automation lane requirement
For `ai_automation`, the query must include **“AI”** or **“machine learning”** (spelled out).
Do not accept plain “automation” / “control system” articles unless AI is clearly present.

AI scope guidance:
- Allow practical deployments (AI for predictive maintenance, anomaly detection, drilling optimization, production optimization, inspection analytics, computer vision for safety, etc.)
- Allow “enabling” AI in field equipment (e.g., AI-enabled sensors, AI at the edge) if the article is explicitly AI-driven
- Avoid generic “digital transformation” unless AI is explicitly stated

## Language
- **English only**.

## Press release exclusion
Exclude obvious press releases and PR syndication.

### Blocked domains list
Maintain a small list of domains to skip entirely (PR wires / press-release hosts). Start with:
- prnewswire.com
- businesswire.com
- globenewswire.com
- newswire.ca
- einpresswire.com

(Expand this list over time if more PR sources keep appearing.)

### Additional heuristics
Also skip items where the title/snippet clearly indicates “Press Release”, “PRNewswire”, “Business Wire”, “GlobeNewswire”, “sponsored”, or similar.

## What to capture per row (minimum fields)
- `captured_at_utc`
- `query_bucket_hint`
- `source_name` (publisher/outlet if available)
- `title`
- `url`
- `published_at` (if available)
- `snippet` (short excerpt from search results, if available)

Optional (nice-to-have):
- `author`
- `company_mentions` (rough extraction from title/snippet)

## Volume limits
- Use `_run_config.md` to determine how many total items to pull per run.
- In TEST mode, default target is **10 total items** across all lanes (balanced across lanes when possible).

## Success criteria
- Sheet is updated with fresh links from the last 24 hours.
- Minimal junk (no press release wires).
- Enough variety across the 4 lanes to support later scoring/selection.
- No drift into refining/petrochemicals unless clearly upstream-ops/services relevant.

## Failure handling
- If a lane returns near-zero results, broaden queries within that lane and retry.
- If results are dominated by blocked domains, adjust queries and re-run that lane.
- Log what changed (query tweaks or new blocked domains) for future refinement.
