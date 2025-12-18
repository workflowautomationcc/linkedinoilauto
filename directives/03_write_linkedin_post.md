# 03_write_linkedin_post.md (Directive)

## Goal
Turn the **Selected** winners (from `02_score_and_select.md`) into **publishable LinkedIn posts**.

Posts must be grounded in the article evidence. No invented operational impact.

## Run rules (always follow)
- Before doing anything, read `directives/_run_config.md`.
- Obey TEST vs PROD limits.
- Do not use paid APIs or image generation unless `_run_config.md` allows it.
- If any step requires posting to LinkedIn automatically, do not post unless `_run_config.md` explicitly allows autoposting.

## Inputs
- Google Sheet from previous steps, especially the **Selected** tab.
- Selected rows include (at minimum):
  - bucket
  - winner vs backup
  - url
  - title
  - source
  - published_at
  - key evidence notes / excerpt (paraphrased or quoted short)
  - score + rationale

## Outputs
- A new tab in the same Google Sheet called **Posts_Draft** (append-only).
- One row per drafted post, with:
  - `draft_id`
  - `bucket`
  - `url`
  - `title`
  - `source`
  - `published_at`
  - `post_text`
  - `hook_line` (first 1–2 lines)
  - `evidence_bullets` (3–6 bullets, concise)
  - `assumptions_made` (should be empty ideally; otherwise explicit)
  - `status` = drafted | needs_review | approved | scheduled | posted
  - `created_at_utc`

## How many posts to write
- **TEST mode:** write **1 total post** (choose the single strongest winner across all buckets).
- **PROD mode:** write **1 post per bucket winner** (up to 4 total), unless `_run_config.md` says otherwise.

## Style requirements (global)
- Tone: **neutral, professional, pragmatic** (no “operator style” / no telling people what to do).
- Length target: **180–250 words**.
- Structure:
  1) Hook (first 1–2 lines must be strong; optimize for the “visible” preview)
  2) 2–4 short paragraphs or tight bullets
  3) One thoughtful question at the end to invite comments
- Avoid:
  - hype, “AI will change everything” vagueness
  - made-up numbers, made-up savings, made-up outcomes
  - implying firsthand involvement (“I built…”, “we implemented…”) unless explicitly provided by user
- Prefer:
  - concrete phrasing (“the article reports…”, “the operator/service company claims…”, “regulators propose…”, “field trial results showed…”) with correct uncertainty

## Evidence rules (no hallucinations)
- Every post must have an **Evidence Pack** (3–6 bullets) derived from the article.
- If the article does NOT explicitly state an operational improvement (efficiency, downtime, safety, quality, cost, cycle time, reliability, scalability), do not claim one.
- If only qualitative benefit is stated, keep it qualitative.
- If the article is ambiguous, flag it in `assumptions_made` and soften claims.

## Bucket-specific guidance

### 1) upstream
Goal: highlight something that changes field operations (drilling/completions/production ops that touch services).
Emphasize:
- reliability, downtime reduction, HSE, logistics, execution efficiency
Avoid:
- reservoir macro commentary unless it ties to field/service operations

### 2) general
Goal: oilfield services business + operations + tech adoption.
Emphasize:
- what happened, why it matters operationally, what it signals for services teams
Avoid:
- finance-only takes with no operational relevance

### 3) ai_automation (AI must be explicit)
Goal: practical AI in services/ops (deployment, workflow integration, decision support, automation).
Must include at least one of:
- AI system described (model, approach, vendor, product, deployment context)
- workflow touchpoint (where AI fits into ops)
- constraint/risk (data quality, safety, reliability, governance)
Avoid:
- generic “digital transformation” unless AI is explicitly stated

### 4) regulation
Goal: interpret regulatory changes as operational implications for services teams.
Emphasize:
- what changed (proposal/final rule/standard)
- who is impacted (operators, contractors, service providers)
- operational implications (reporting, equipment, procedures, HSE, permitting)
Avoid:
- partisan tone

## Drafting process
1) Read `_run_config.md` to determine TEST vs PROD behavior.
2) Read Selected tab and pull the winner rows (and optionally backups if allowed).
3) For each post:
   - Build Evidence Pack (3–6 bullets).
   - Write hook optimized for preview visibility.
   - Write 180–250 word post text using Evidence Pack.
   - End with one question that invites operational discussion (not salesy).
4) Write output row to Posts_Draft tab and set status `needs_review`.

## Optional: add a “source link” line
- Default: include the source link in the sheet, not necessarily in the post text.
- If included in post, keep it simple and non-spammy (no tracking links).

## Failure handling / self-annealing guidance
- If article text is not accessible or paywalled:
  - fall back to snippet + any available excerpt from earlier steps
  - mark `assumptions_made` and reduce confidence/strength of claims
  - if too thin, mark status `needs_review` and optionally swap in backup
- If posts feel repetitive:
  - vary the framing by bucket:
    - upstream: “execution impact”
    - general: “operating model impact”
    - ai_automation: “where AI fits + constraints”
    - regulation: “compliance-to-ops translation”
  - update this directive with improved templates

## Done condition
- Posts_Draft contains the required number of drafted posts per run mode.
- Each drafted post has:
  - strong hook
  - Evidence Pack
  - 180–250 words
  - one thoughtful question
  - no invented operational impact
