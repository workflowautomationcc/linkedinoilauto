import json
import os
import sys
from typing import Dict, Any, List, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, SHEET_NAME_DEFAULT, logger


PUBLISHED_TAB = "posts_published"
DRAFTS_TAB = "posts_draft"
STUB_POSTS_PATH = os.path.join("execution", "stub_posts.json")
WORKFLOW_LOG_PATH = os.path.join("execution", "workflow.log")

REQUIRED_PUBLISHED_COLUMNS = [
    "post_text",
    "image_source",
    "image_prompt",
    "image_origin_url",
    "url",
    "title",
    "bucket",
    "image_path",
]


def _col_to_a1(col_index_1_based: int) -> str:
    result = ""
    n = col_index_1_based
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _ensure_columns(worksheet, required_cols: List[str]) -> List[str]:
    headers = worksheet.row_values(1) or []
    if not headers:
        headers = ["draft_id"] + [c for c in required_cols if c != "draft_id"]
        worksheet.update("A1", [headers])
        return headers

    missing = [c for c in required_cols if c not in headers]
    if not missing:
        return headers

    new_headers = headers + missing
    worksheet.update("A1", [new_headers])
    return new_headers


def _load_stub_posts() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(STUB_POSTS_PATH):
        return {}
    try:
        with open(STUB_POSTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        out: Dict[str, Dict[str, Any]] = {}
        for row in data or []:
            draft_id = str(row.get("draft_id") or "").strip()
            if draft_id:
                out[draft_id] = row
        return out
    except Exception as e:
        logger.warning(f"Failed to load stub posts from {STUB_POSTS_PATH}: {e}")
        return {}


def _infer_image_source(image_path: str) -> str:
    if not image_path:
        return "none"
    if "_scraped" in image_path:
        return "scraped"
    return "ai"


def _load_image_generation_metadata_from_log() -> Dict[str, Dict[str, str]]:
    """
    Best-effort recovery for older runs where we didn't persist image_prompt/image_origin_url.
    Parses `execution/workflow.log` for:
      - Image generation enabled for draft <id>
      - Generated image prompt: "<prompt>"
      - Image generated: <url>
    """
    if not os.path.exists(WORKFLOW_LOG_PATH):
        return {}

    import re

    enabled_re = re.compile(r"Image generation enabled for draft\s+([a-zA-Z0-9_-]+)")
    prompt_re = re.compile(r'Generated image prompt:\s+"(.+)"')
    url_re = re.compile(r"Image generated:\s+(https?://\S+)")

    out: Dict[str, Dict[str, str]] = {}
    current_id = ""

    try:
        with open(WORKFLOW_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = enabled_re.search(line)
                if m:
                    current_id = m.group(1)
                    out.setdefault(current_id, {})
                    continue

                if not current_id:
                    continue

                m = prompt_re.search(line)
                if m and "image_prompt" not in out[current_id]:
                    out[current_id]["image_prompt"] = m.group(1).strip()
                    continue

                m = url_re.search(line)
                if m and "image_origin_url" not in out[current_id]:
                    out[current_id]["image_origin_url"] = m.group(1).strip()
                    continue

        return out
    except Exception as e:
        logger.warning(f"Failed to parse {WORKFLOW_LOG_PATH}: {e}")
        return {}


def backfill_posts_published(limit_rows: int = 0) -> None:
    dm = DataManager()
    if not dm.use_sheets or not dm.gc:
        raise RuntimeError("Not connected to Google Sheets (OAuth/service account required).")

    sh = dm.gc.open(SHEET_NAME_DEFAULT)
    ws_pub = sh.worksheet(PUBLISHED_TAB)

    try:
        ws_drafts = sh.worksheet(DRAFTS_TAB)
        drafts = ws_drafts.get_all_records()
    except Exception as e:
        logger.warning(f"Could not read '{DRAFTS_TAB}' for backfill: {e}")
        drafts = []

    draft_by_id: Dict[str, Dict[str, Any]] = {}
    for row in drafts:
        draft_id = str(row.get("draft_id") or "").strip()
        if draft_id:
            draft_by_id[draft_id] = row

    stub_by_id = _load_stub_posts()
    log_image_meta_by_id = _load_image_generation_metadata_from_log()

    headers = _ensure_columns(ws_pub, REQUIRED_PUBLISHED_COLUMNS)
    header_index = {h: i + 1 for i, h in enumerate(headers) if h}

    values = ws_pub.get_all_values()
    if len(values) <= 1:
        logger.info(f"No data rows found in '{PUBLISHED_TAB}'. Nothing to backfill.")
        return

    first_new_col = min(header_index[c] for c in REQUIRED_PUBLISHED_COLUMNS if c in header_index)
    last_new_col = max(header_index[c] for c in REQUIRED_PUBLISHED_COLUMNS if c in header_index)

    updates: List[Dict[str, Any]] = []
    rows_seen = 0

    for row_num in range(2, len(values) + 1):
        if limit_rows and rows_seen >= limit_rows:
            break

        draft_id_col = header_index.get("draft_id")
        if not draft_id_col:
            logger.error("Missing required column 'draft_id' in posts_published.")
            break

        draft_id = ""
        if draft_id_col <= len(values[row_num - 1]):
            draft_id = str(values[row_num - 1][draft_id_col - 1]).strip()
        if not draft_id:
            continue

        draft_row = draft_by_id.get(draft_id) or {}
        stub_row = stub_by_id.get(draft_id) or {}

        existing_by_col: Dict[str, str] = {}
        for h, idx in header_index.items():
            if idx <= len(values[row_num - 1]):
                existing_by_col[h] = str(values[row_num - 1][idx - 1]).strip()
            else:
                existing_by_col[h] = ""

        post_text = existing_by_col.get("post_text") or draft_row.get("post_text") or stub_row.get("text") or ""
        image_path = existing_by_col.get("image_path") or draft_row.get("image_path") or stub_row.get("image_path") or ""
        image_prompt = (
            existing_by_col.get("image_prompt")
            or draft_row.get("image_prompt")
            or (log_image_meta_by_id.get(draft_id) or {}).get("image_prompt", "")
            or ""
        )
        image_source = (
            existing_by_col.get("image_source")
            or draft_row.get("image_source")
            or _infer_image_source(str(image_path))
        )
        image_origin_url = (
            existing_by_col.get("image_origin_url")
            or draft_row.get("image_origin_url")
            or (log_image_meta_by_id.get(draft_id) or {}).get("image_origin_url", "")
            or ""
        )
        url = existing_by_col.get("url") or draft_row.get("url") or stub_row.get("link") or ""
        title = existing_by_col.get("title") or draft_row.get("title") or ""
        bucket = existing_by_col.get("bucket") or draft_row.get("bucket") or ""

        row_values: List[str] = []
        for col_idx in range(first_new_col, last_new_col + 1):
            header = headers[col_idx - 1]
            if header == "post_text":
                row_values.append(str(post_text))
            elif header == "image_source":
                row_values.append(str(image_source))
            elif header == "image_prompt":
                row_values.append(str(image_prompt))
            elif header == "image_origin_url":
                row_values.append(str(image_origin_url))
            elif header == "url":
                row_values.append(str(url))
            elif header == "title":
                row_values.append(str(title))
            elif header == "bucket":
                row_values.append(str(bucket))
            elif header == "image_path":
                row_values.append(str(image_path))
            else:
                row_values.append(existing_by_col.get(header, ""))

        start = f"{_col_to_a1(first_new_col)}{row_num}"
        end = f"{_col_to_a1(last_new_col)}{row_num}"
        updates.append({"range": f"{start}:{end}", "values": [row_values]})
        rows_seen += 1

    if not updates:
        logger.info("No rows matched for backfill (missing draft_id or already empty sheet).")
        return

    ws_pub.batch_update(updates)
    logger.info(f"Backfilled {len(updates)} row(s) in '{PUBLISHED_TAB}'.")


if __name__ == "__main__":
    backfill_posts_published()
