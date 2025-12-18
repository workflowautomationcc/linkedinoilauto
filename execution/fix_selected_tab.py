import os
import sys
import csv
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, SHEET_NAME_DEFAULT, logger
from newspaper import Article


TAB_NAME = "selected"

CANONICAL_HEADERS = [
    "selected_at",
    "bucket",
    "selection_role",
    "final_score",
    "ready_for_write",
    "bucket_reason",
    "url",
    "title",
    "source_date",
    "key_evidence_notes",
    "article_text_truncated",
    "article_text_hash",
]


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _truncate_for_sheet(text: str, max_chars: int = 45000) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _fetch_full_text(url: str) -> str:
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text or ""
    except Exception as e:
        logger.warning(f"FullText fetch failed for {url}: {e}")
        return ""


def _ensure_backup_dir() -> str:
    path = os.path.join("execution", "backups")
    os.makedirs(path, exist_ok=True)
    return path


def _backup(values: List[List[str]]) -> None:
    backup_dir = _ensure_backup_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = os.path.join(backup_dir, f"selected_backup_{stamp}.json")
    csv_path = os.path.join(backup_dir, f"selected_backup_{stamp}.csv")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(values, f, ensure_ascii=False, indent=2)

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(values)

    logger.info(f"Backed up '{TAB_NAME}' to {json_path} and {csv_path}")


def _row_to_map(headers: List[str], row: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for i, h in enumerate(headers):
        if not h:
            continue
        out[h] = row[i] if i < len(row) else ""
    return out


def fix_selected_tab(backfill_article_text: bool = True) -> None:
    dm = DataManager()
    if not dm.use_sheets or not dm.gc:
        raise RuntimeError("Not connected to Google Sheets (OAuth/service account required).")

    sh = dm.gc.open(SHEET_NAME_DEFAULT)
    ws = sh.worksheet(TAB_NAME)

    values = ws.get_all_values()
    if not values:
        logger.info(f"'{TAB_NAME}' is empty. Writing canonical headers.")
        ws.update("A1", [CANONICAL_HEADERS])
        return

    _backup(values)

    old_headers = values[0]
    data_rows = values[1:]

    new_rows: List[List[str]] = []
    for row in data_rows:
        row_map = _row_to_map(old_headers, row)

        def _is_url(value: str) -> bool:
            v = (value or "").strip().lower()
            return v.startswith("http://") or v.startswith("https://")

        # Repair common one-column left shift where headers existed but the sheet had an extra/missing column.
        # Symptom: `title` contains a URL, while `url` contains prose.
        if _is_url(row_map.get("title", "")) and not _is_url(row_map.get("url", "")):
            repaired = dict(row_map)
            repaired["selected_at"] = repaired.get("bucket", "")
            repaired["bucket"] = repaired.get("selection_role", "")
            repaired["selection_role"] = repaired.get("final_score", "")
            repaired["final_score"] = repaired.get("ready_for_write", "")
            repaired["ready_for_write"] = repaired.get("bucket_reason", "")
            repaired["bucket_reason"] = repaired.get("url", "")
            repaired["url"] = repaired.get("title", "")
            repaired["title"] = repaired.get("source_date", "")
            repaired["source_date"] = repaired.get("key_evidence_notes", "")
            repaired["key_evidence_notes"] = ""
            row_map = repaired

        url = (row_map.get("url") or "").strip()
        article_text = (row_map.get("article_text_truncated") or "").strip()
        article_hash = (row_map.get("article_text_hash") or "").strip()

        if backfill_article_text and url and (not article_text or not article_hash):
            full_text = _fetch_full_text(url)
            if full_text:
                article_text = _truncate_for_sheet(full_text)
                article_hash = _sha256(full_text)

        out_map = dict(row_map)
        out_map["article_text_truncated"] = article_text
        out_map["article_text_hash"] = article_hash
        out_map.setdefault("selected_at", "")

        new_rows.append([str(out_map.get(h, "")) for h in CANONICAL_HEADERS])

    ws.clear()
    ws.update("A1", [CANONICAL_HEADERS])
    if new_rows:
        ws.append_rows(new_rows)
    logger.info(f"Rewrote '{TAB_NAME}' with {len(new_rows)} row(s) and canonical headers.")


if __name__ == "__main__":
    fix_selected_tab()
