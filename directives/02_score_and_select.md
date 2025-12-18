# 02_score_and_select.md (Directive)

## Goal
Take the raw links collected by `01_source_news.md`, score them, and select winners per bucket for downstream post writing.

This step:
- scores candidates cheaply first
- does controlled full-text fetch only on a shortlist (per `_run_config.md`)
- produces **Selected** winners + backups
- flags what is allowed to move forward to writing based on run size

---

## Run rules (always follow)
- Before doing anything, read `directives/_run_config.md`.
- Obey TEST vs PROD limits (especially caps on full-text fetching and any paid APIs).
- Do not perform any paid API calls unless `_run_config.md` explicitly allows it.
- Do not delete rows; use statuses.
- Also obey the **Scope filter (critical)** from `01_source_news.md`.
  - Any item that matches **OUT OF SCOPE** is an immediate reject:
    - set `status = rejected`
    - set `reject_reason = out_of_scope`
    - do **not** fetch full text for it

---

## Inputs
- Google Sheet produced by `01_source_news.md`
  - Raw rows include (at minimum): `title`, `url`, `snippet`, `published_at`, `source_name`, `query_bucket_hint`

---

## Outputs
- A separate tab in the same Google Sheet called **Selected**
  - Rows represent winners + backups per bucket (append/update, but never delete history)
- Raw tab rows get updated with status + scores (no deletion)

---

## Buckets & selection targets
Buckets (same as lane hints; final tagging may confirm/override later):
- `upstream`
- `general`
- `ai_automation`
- `regulation`

Selection design:
- **WINNERS_PER_BUCKET** = `_run_config.md: WINNERS_PER_BUCKET`
- **BACKUPS_PER_BUCKET** = `_run_config.md: BACKUPS_PER_BUCKET`

Publishing / prep rule:
- In **TEST** runs: still select winners + backups per bucket, but only **one total** item is flagged to move forward to writing.
- In **PROD** runs: winners per bucket can move forward (per `_run_config.md`).

---

## Hard filters (apply before Pass 1 scoring)
### 0) Scope gate (non-negotiable)
- For every candidate row, apply the OUT OF SCOPE rules from `01_source_news.md`.
- If OUT OF SCOPE → reject immediately:
  - `status = rejected`
  - `reject_reason = out_of_scope`
  - skip scoring and skip full-text fetch

### 1) Dedupe gate
- If multiple rows are the same story (syndication / copied PR / identical headline+facts):
  - Keep the single best source row (highest credibility, clearest snippet, cleanest URL)
  - Reject the rest:
    - `status = rejected`
    - `reject_reason = duplicate_story`

### 2) Broken/invalid link gate
- If URL is malformed, dead, or clearly not an article:
  - `status = rejected`
  - `reject_reason = bad_url`

---

## Scoring (high-level, explainable)
Score each candidate with components (0–5 each):

1) **Relevance to bucket**
- Matches the intended bucket meaningfully (not just keyword coincidence)

2) **Freshness**
- Prefer within last 24h; older gets penalized (still keep if unusually important)

3) **Credibility**
- Prefer known industry publishers when available
- Allow smaller sources (esp. AI lane) if they appear legitimate

4) **Practicality / applicability**
- Higher only if the item explicitly discusses operational improvement (qualitative is fine):
  - efficiency, downtime, safety, quality, cost, scalability, cycle time, reliability
- Do **not** invent impact; only score high if the article states it

5) **LinkedIn-worthiness**
- Clear takeaway, useful insight, or contrarian angle that could spark comments

### Weighted total
Total score = weighted sum.

Default weighting intent (don’t overfit):
- `upstream`: emphasize practicality + credibility
- `general`: balanced
- `ai_automation`: emphasize relevance + novelty + usefulness (deployments and forward-looking ideas both allowed)
- `regulation`: emphasize credibility + implications

Store:
- `score_pass1` from Pass 1
- `score_pass2` from Pass 2 (if applicable)

---

## Full-text fetching (controlled)
We score in two passes.

### Pass 1 (cheap)
Use only:
- title + snippet + source + publish date (+ bucket hint)

Do initial scoring and shortlist.

### Pass 2 (full-text, limited)
Fetch full article text **only for the shortlist**, respecting caps in `_run_config.md`:

- If `RUN_SIZE = TEST`:
  - fetch full text for up to `_run_config.md: FULLTEXT_FETCH_PER_BUCKET_TEST` per bucket
- If `RUN_SIZE = PROD`:
  - fetch full text for up to `_run_config.md: FULLTEXT_FETCH_PER_BUCKET_PROD` per bucket

Then re-score with better evidence (still no guessing).

#### Full-text failure policy (must match `_run_config.md`)
If full-text fetch fails (paywall, blocked, timeout):
- Follow `_run_config.md: FULLTEXT_FAIL_POLICY`

If `FULLTEXT_FAIL_POLICY = FALLBACK_TO_SNIPPET`:
- Do **not** auto-reject solely for paywall/blocking
- Re-score using snippet + any accessible excerpt
- Mark the raw row with:
  - `fulltext_status = failed`
  - `fulltext_fail_reason = paywall|blocked|timeout|other`
- Reduce confidence in scoring and ensure downstream writing is conservative (evidence-thin)

If `FULLTEXT_FAIL_POLICY = SKIP_ITEM`:
- Reject the item and promote next backup:
  - `status = rejected`
  - `reject_reason = fulltext_unavailable`

---

## Selection logic (per bucket)
For each bucket:

1) Build candidate pool
- Start from rows where `query_bucket_hint == bucket`
- Allow re-bucketing only in Pass 2 if evidence strongly indicates a better bucket

2) Pass 1 score & rank
- Compute `score_pass1`
- Set `status = shortlisted` for the top candidates you intend to consider for Pass 2
- Leave others as `new` unless rejected by gates

3) Full-text fetch limited shortlist (per `_run_config.md`)
- Fetch only within caps

4) Pass 2 re-score & finalize
- Compute `score_pass2` for items with full text (or fallback evidence)
- Pick:
  - 1 winner
  - N backups (default 2)
- Write rows into **Selected** tab with:
  - `bucket`
  - `selection_role` = winner | backup
  - `final_score`
  - `rationale_short` (1–2 sentences)
  - `url`, `title`, `source`, `published_at`
  - `key_evidence_notes` (paraphrased; optional short quote if needed and very short)

5) Update raw statuses (auditability)
- Winner: `status = selected_winner`
- Backups: `status = selected_backup`
- Non-selected (but not rejected): keep as `new` or set `status = rejected` with reason `not_selected` (choose one approach and be consistent)
- Never delete rows

---

## “Ready for write” gating (RUN_SIZE behavior)
Add a raw-column (or Selected-column) called:
- `ready_for_write` = YES/NO

Rules:
- If `RUN_SIZE = TEST`:
  - Exactly **one total** item across all buckets gets `ready_for_write = YES`
  - Pick the single strongest winner across buckets (highest confidence + evidence quality)
  - All other winners remain selected but `ready_for_write = NO`
- If `RUN_SIZE = PROD`:
  - Winners per bucket can be `ready_for_write = YES` (subject to `_run_config.md` writing targets)

---

## Status tracking (auditability)
In the raw tab, add/update:
- `status` = new | shortlisted | selected_winner | selected_backup | rejected
- `score_pass1`
- `score_pass2` (if fetched full text or fallback scoring)
- `reject_reason` (short)
Optional but recommended:
- `fulltext_status` = not_fetched | fetched | failed
- `fulltext_fail_reason` (if failed)

Never delete anything.

---

## Failure handling / self-annealing guidance
- If a bucket has too few candidates:
  - broaden within that lane (still within last 24h) and retry
- If too many items are junk:
  - update blocked domains list (in 01)
  - tighten scope heuristics (01)
  - refine scoring heuristics (here)
- If paywalls are common:
  - rely more on snippet and accept “needs_review” downstream
  - or change `_run_config.md` policy intentionally (only if user says persist)

---

## Done condition
- **Selected** tab contains winners + backups per bucket
- Raw tab shows statuses, scores, and reject reasons
- `ready_for_write` is set correctly for the current run size
