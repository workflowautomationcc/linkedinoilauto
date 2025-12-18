import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, SHEET_NAME_DEFAULT, logger


DRAFTS_TAB = "posts_draft"
PUBLISHED_TAB = "posts_published"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _as_map(headers: List[str], row: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for i, h in enumerate(headers):
        h = (h or "").strip()
        if not h:
            continue
        out[h] = row[i] if i < len(row) else ""
    return out


def _ensure_cols(headers: List[str], cols: List[str]) -> List[str]:
    out = list(headers)
    for c in cols:
        if c not in out:
            out.append(c)
    return out


def migrate_to_draft_only() -> None:
    dm = DataManager()
    if not dm.use_sheets or not dm.gc:
        raise RuntimeError("Not connected to Google Sheets.")

    sh = dm.gc.open(SHEET_NAME_DEFAULT)

    ws_drafts = sh.worksheet(DRAFTS_TAB)
    drafts_vals = ws_drafts.get_all_values()
    draft_headers = drafts_vals[0] if drafts_vals else []
    draft_rows = drafts_vals[1:] if len(drafts_vals) > 1 else []

    try:
        ws_pub = sh.worksheet(PUBLISHED_TAB)
        pub_vals = ws_pub.get_all_values()
        pub_headers = pub_vals[0] if pub_vals else []
        pub_rows = pub_vals[1:] if len(pub_vals) > 1 else []
    except Exception:
        ws_pub = None
        pub_headers = []
        pub_rows = []

    draft_by_id: Dict[str, Dict[str, str]] = {}
    for r in draft_rows:
        m = _as_map(draft_headers, r)
        did = (m.get("draft_id") or "").strip()
        if did:
            draft_by_id[did] = m

    pub_by_id: Dict[str, Dict[str, str]] = {}
    for r in pub_rows:
        m = _as_map(pub_headers, r)
        did = (m.get("draft_id") or "").strip()
        if did:
            pub_by_id[did] = m

    # Canonical draft schema: keep current drafts columns, but extend with useful fields from published + analysis.
    merged_headers = _ensure_cols(
        [h for h in draft_headers if (h or "").strip()],
        [
            "image_source",
            "image_prompt",
            "image_origin_url",
            "analysis_report",
            "analysis_model",
            "analysis_ran_at_utc",
        ],
    )

    merged_rows: List[List[str]] = []
    for did, d in draft_by_id.items():
        p = pub_by_id.get(did, {})

        merged = dict(d)
        for k in ["post_text", "url", "title", "bucket", "image_path"]:
            if not merged.get(k) and p.get(k):
                merged[k] = p.get(k, "")

        for k in ["image_source", "image_prompt", "image_origin_url"]:
            if p.get(k) and not merged.get(k):
                merged[k] = p.get(k, "")

        # If it was previously logged as published_stub, treat it as draft needing review.
        status = str(merged.get("status") or "")
        if status.startswith("published"):
            merged["status"] = "needs_review"

        merged_rows.append([str(merged.get(h, "")) for h in merged_headers])

    # Backup existing tabs into local files (CSV/JSON-ish via raw values)
    backup_dir = os.path.join("execution", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = _now_stamp()
    with open(os.path.join(backup_dir, f"{DRAFTS_TAB}_{stamp}.txt"), "w", encoding="utf-8") as f:
        for row in drafts_vals:
            f.write("\t".join(row) + "\n")
    if ws_pub:
        with open(os.path.join(backup_dir, f"{PUBLISHED_TAB}_{stamp}.txt"), "w", encoding="utf-8") as f:
            for row in pub_vals:
                f.write("\t".join(row) + "\n")

    # Overwrite drafts tab with merged schema
    ws_drafts.clear()
    ws_drafts.update("A1", [merged_headers])
    if merged_rows:
        ws_drafts.append_rows(merged_rows)

    # Archive published tab (rename) instead of deleting, for safety.
    if ws_pub:
        legacy_name = f"{PUBLISHED_TAB}_legacy_{stamp}"
        ws_pub.update_title(legacy_name)
        logger.info(f"Renamed '{PUBLISHED_TAB}' -> '{legacy_name}'")

    logger.info(f"Migrated to draft-only workflow. Draft rows: {len(merged_rows)}")


if __name__ == "__main__":
    migrate_to_draft_only()

