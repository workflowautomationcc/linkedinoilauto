# _run_config.md — Run Config (single source of truth)

## 0) Purpose
This file controls *run size* and *spend/side-effect guardrails*.
It does NOT change the system architecture. It only changes volume, limits, and permissions.

---

## 1) Build target vs run size (IMPORTANT)
# BUILD_TARGET defines what the system is designed for (structure, robustness).
# RUN_SIZE defines how much work to actually do this run (volume/spend).
# Allowed: PRODUCTION
BUILD_TARGET: PRODUCTION

# Allowed: TEST | PROD
RUN_SIZE: PROD

---

## 2) Bucket policy (how many winners/posts)
# Buckets must match directives 01/02/03:
# upstream | general | ai_automation | regulation

# Selection targets (02_score_and_select.md)
WINNERS_PER_BUCKET: 1
BACKUPS_PER_BUCKET: 2

# Writing targets (03_write_linkedin_post.md)
# In TEST: draft only 1 total post (pick strongest winner across all buckets).
# In PROD: draft 1 post per bucket winner (up to 4 total).
DRAFTS_TOTAL_TEST: 1
DRAFTS_PER_BUCKET_PROD: 1

---

## 3) Discovery limits (01_source_news.md)
# Total candidate links to collect per run (across all buckets)
# In TEST keep small; in PROD set to your current real volume.
CANDIDATE_LINKS_TOTAL_TEST: 8
CANDIDATE_LINKS_TOTAL_PROD: 50
SOURCE_NEWS_FREQUENCY_HOURS: 24

# Balance rule in TEST: try to distribute across buckets when possible
# Allowed: BALANCED | BEST_EFFORT
TEST_BUCKET_BALANCE: BALANCED

---

## 4) Full-text fetch limits (02_score_and_select.md)
# Full-text fetching is the expensive step (time + possible paid services).
# These are hard caps.

# TEST: fetch full text only for 1 candidate per bucket (winner-candidate only)
FULLTEXT_FETCH_PER_BUCKET_TEST: 1

# PROD: fetch full text for top 2–3 per bucket (winner-candidates + top backups)
FULLTEXT_FETCH_PER_BUCKET_PROD: 3

# If full text cannot be fetched (paywall/blocked):
# Allowed: SKIP_ITEM | FALLBACK_TO_SNIPPET
FULLTEXT_FAIL_POLICY: FALLBACK_TO_SNIPPET

---

## 5) Spend control (what counts as “paid”)
# "Paid" includes:
# - Tavily, Apify paid actors, SerpAPI, paid news APIs
# - Any LLM API calls billed per token (OpenAI/Anthropic/etc)
# - Any image generation billed per call
# - Any other metered external service

REQUIRES_USER_APPROVAL_BEFORE_PAID_SPEND: YES
PAID_APIS_DEFAULT_ALLOWED: NO

# Cheap/free actions allowed without approval:
# - reading local files, parsing existing sheet rows
# - free/public web access if available via the IDE without paid APIs
# - running local Python scripts

---

## 6) Side effects guardrails
# Side effects include:
# - posting to LinkedIn
# - sending emails/messages
# - writing to external CRMs/databases
# - creating/updating cloud deliverables (Sheets/Slides/Drive) if not explicitly requested in the directive or the user message

REQUIRES_USER_APPROVAL_BEFORE_SIDE_EFFECTS: YES

# Exception: Google Sheet updates are allowed because directives 01/02/03 require them,
# but ONLY to the specific sheet used by this workflow.
ALLOW_GOOGLE_SHEETS_WRITES: YES
ALLOWED_SHEET_SCOPE: WORKFLOW_SHEET_ONLY
ALLOW_GOOGLE_SLIDES_WRITES: NO
ALLOW_LINKEDIN_POSTING: NO

# Image Generation
# If YES, generate images for posts using Fal.ai API (requires FAL_KEY in .env)
GENERATE_IMAGES: YES

# Preview Analysis (LLM-as-reviewer)
# If YES, enables the "Analyze vs article" button to call a paid LLM API for detailed review.
ALLOW_PREVIEW_ANALYSIS: YES

# Default analysis model (override per run if desired)
ANALYSIS_MODEL: gpt-4o-mini
ANALYSIS_TEMPERATURE: 0.2

---

## 7) Override rules (so you don’t have to remember)
# If the user explicitly gives an override in the current message (e.g., "run PROD" or "pull 60 links"):
# - ask ONE confirmation question only if it increases paid spend or triggers side effects
# - otherwise apply the override for this run only
# - do NOT persist changes to this file unless the user explicitly says "save/persist/update _run_config"

PERSIST_OVERRIDES_BY_DEFAULT: NO

---

## 8) Defaults for THIS project (content creation)
# You want: design for production scale, but spend small while tuning.
# Therefore:
# - keep BUILD_TARGET = PRODUCTION always
# - flip RUN_SIZE between TEST and PROD as needed
# - TEST focuses on validating quality end-to-end with minimal volume

---

## 9) Notes (human-readable)
# If RUN_SIZE=TEST:
# - collect up to CANDIDATE_LINKS_TOTAL_TEST links
# - shortlist and full-text fetch per bucket capped by FULLTEXT_FETCH_PER_BUCKET_TEST
# - select winners per bucket, but draft only DRAFTS_TOTAL_TEST post
#
# If RUN_SIZE=PROD:
# - collect up to CANDIDATE_LINKS_TOTAL_PROD links
# - full-text fetch per bucket capped by FULLTEXT_FETCH_PER_BUCKET_PROD
# - draft DRAFTS_PER_BUCKET_PROD posts per bucket winner (up to 4)

---

## 10) Independent pipelines (bypass this config)
# The following pipelines operate independently and do not use this config file:
# - `ai_discovery.md` — AI-only discovery pipeline (measurement-only, cloud-executed)
#   - Uses environment variables for all configuration
#   - Bypasses run size limits and approval gates
#   - Designed for automated daily execution
