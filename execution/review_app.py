import json
import os
import sys
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, load_config, SHEET_NAME_DEFAULT
from execution.post_analysis import analyze_post_vs_article


STUB_FILE = os.path.join("execution", "stub_posts.json")
PORT = int(os.getenv("REVIEW_PORT", "8765"))
TARGET_DRAFT_TAB = "posts_draft"


HTML_TEMPLATE_HEAD = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Review: Posts vs Articles</title>
  <style>
    body { font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f3f2ef; padding: 20px; color: rgba(0,0,0,0.9); }
    .container { max-width: 1200px; margin: 0 auto; }
    h1 { color: #000000bf; font-size: 20px; text-align:center; padding-bottom:20px;}

    .review-row { display: flex; gap: 16px; margin-bottom: 20px; align-items: stretch; }
    .article-col { flex: 1 1 auto; min-width: 380px; }
    .post-col { flex: 0 0 500px; }
    @media (max-width: 980px) {
        .review-row { flex-direction: column; }
        .article-col, .post-col { flex: 1 1 auto; min-width: 0; }
    }

    .panel {
        background: white;
        border-radius: 8px;
        box-shadow: 0 0 0 1px rgba(0,0,0,0.08), 0 2px 2px rgba(0,0,0,0.05);
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: 0;
    }
    .panel-header { padding: 12px 16px 8px; border-bottom: 1px solid rgba(0,0,0,0.06); }
    .label { font-size: 12px; color: rgba(0,0,0,0.6); font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
    .title { font-size: 16px; font-weight: 600; margin-top: 6px; color: rgba(0,0,0,0.9); line-height: 1.25; }
    .meta { font-size: 12px; color: rgba(0,0,0,0.6); margin-top: 6px; display: flex; gap: 10px; flex-wrap: wrap; }
    .meta a { color: rgba(0,0,0,0.6); text-decoration: none; }
    .meta a:hover { text-decoration: underline; }
    .body { padding: 12px 16px; font-size: 13px; line-height: 1.4; color: rgba(0,0,0,0.9); white-space: pre-wrap; overflow: auto; flex: 1 1 auto; min-height: 0; }
    .body.collapsed { max-height: calc(1.4em * 18); overflow: hidden; }
    .controls { padding: 8px 16px 12px; border-top: 1px solid rgba(0,0,0,0.06); display:flex; gap: 10px; align-items:center; }
    .btn { background: none; border: none; color: rgba(0,0,0,0.6); font-weight: 600; font-size: 14px; cursor: pointer; padding: 4px 0; }
    .btn:hover { text-decoration: underline; }
    .primary { color: #0a66c2; }
    .status { font-size: 12px; color: rgba(0,0,0,0.6); margin-left:auto; }
    .pill { font-size: 12px; background: rgba(10,102,194,0.08); color:#0a66c2; border-radius: 999px; padding: 2px 8px; }
    .saved-ok { color: #137333; }
    .saved-bad { color: #b3261e; }

    /* Post */
    .post-content { padding: 0 16px; font-size: 14px; line-height: 1.4; color: rgba(0,0,0,0.9); white-space: pre-wrap; margin-bottom: 8px; }
    .post-content.collapsed { max-height: calc(1.4em * 8); overflow: hidden; }

    .img { width: 100%; max-height: 360px; object-fit: contain; background: #f3f2ef; border-top: 1px solid rgba(0,0,0,0.06); border-bottom: 1px solid rgba(0,0,0,0.06); }
    .placeholder { height: 280px; background-color: #dbe7f1; display:flex; align-items:center; justify-content:center; color:#5e6d7a; font-weight:500; }
  </style>
  <script>
    const ANALYSIS_MODEL = "__ANALYSIS_MODEL__";
    const REQUIRE_PAID_CONFIRM = __REQUIRE_PAID_CONFIRM__;
    const params = new URLSearchParams(window.location.search);
    const TARGET_DRAFT_ID = params.get('draft_id') || '';
    const AUTO_RUN = params.get('auto') === '1';
    const CONFIRMED_FROM_PREVIEW = params.get('confirmed') === '1';

    function toggle(id, btnId) {
      const el = document.getElementById(id);
      const btn = document.getElementById(btnId);
      if (!el || !btn) return;
      if (el.classList.contains('collapsed')) { el.classList.remove('collapsed'); btn.textContent = '...see less'; }
      else { el.classList.add('collapsed'); btn.textContent = '...see more'; }
      syncRowHeights();
    }

    function syncRowHeights() {
      document.querySelectorAll('.review-row').forEach(function(row) {
        const postPanel = row.querySelector('.post-panel');
        const articlePanel = row.querySelector('.article-panel');
        if (!postPanel || !articlePanel) return;
        const postHeight = postPanel.getBoundingClientRect().height;
        if (postHeight > 0) articlePanel.style.height = postHeight + 'px';
      });
    }

    async function analyze(draftId) {
      const out = document.getElementById('analysis-' + draftId);
      const status = document.getElementById('analysis-status-' + draftId);
      const saved = document.getElementById('analysis-saved-' + draftId);
      const btn = document.getElementById('analyze-btn-' + draftId);
      if (!out || !status) return;
      out.textContent = '';
      status.textContent = 'running analysis...';
      if (saved) { saved.textContent = ''; saved.className = 'status'; }
      if (btn) btn.disabled = true;
      if (REQUIRE_PAID_CONFIRM && !CONFIRMED_FROM_PREVIEW) {
        const ok = window.confirm(`This will call a paid LLM API (${ANALYSIS_MODEL}). Continue?`);
        if (!ok) {
          status.textContent = 'cancelled';
          if (btn) btn.disabled = false;
          return;
        }
      }
      try {
        const resp = await fetch('/api/analyze', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({draft_id: draftId})
        });
        const data = await resp.json();
        out.textContent = data.analysis || data.error || 'No response';
        status.textContent = 'done';
        if (saved) {
          if (data.saved === true) {
            saved.textContent = 'saved ✓';
            saved.className = 'status saved-ok';
          } else if (data.saved === false) {
            saved.textContent = 'not saved';
            saved.className = 'status saved-bad';
          }
        }
      } catch (e) {
        status.textContent = 'error';
        out.textContent = String(e);
      } finally {
        if (btn) btn.disabled = false;
      }
      syncRowHeights();
    }

    window.addEventListener('load', function() {
      syncRowHeights();
      if (TARGET_DRAFT_ID) {
        const el = document.getElementById('row-' + TARGET_DRAFT_ID);
        if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
        if (AUTO_RUN) setTimeout(() => analyze(TARGET_DRAFT_ID), 250);
      }
    });
    window.addEventListener('resize', function() { syncRowHeights(); });
  </script>
</head>
<body>
  <div class="container">
    <h1>Review</h1>
"""

HTML_TEMPLATE_FOOT = """
  </div>
</body>
</html>
"""


def _escape(s: str) -> str:
    import html

    return html.escape(s or "")


def _load_posts_for_review() -> list:
    """
    Prefer posts from `posts_draft` (Sheet/CSV), fall back to legacy stub JSON.
    Normalizes keys to align with the review UI.
    """
    try:
        dm = DataManager()
        df = dm.read_data("posts_draft")
        if not df.empty:
            rows = df.to_dict("records")
            out = []
            for r in rows:
                out.append(
                    {
                        "draft_id": str(r.get("draft_id") or ""),
                        "link": str(r.get("url") or ""),
                        "text": str(r.get("post_text") or ""),
                        "image_path": str(r.get("image_path") or ""),
                        "drafted_at": str(r.get("drafted_at") or r.get("created_at_utc") or ""),
                    }
                )
            return out
    except Exception:
        pass

    if not os.path.exists(STUB_FILE):
        return []
    with open(STUB_FILE, "r", encoding="utf-8") as f:
        return json.load(f) or []


def _selected_map_by_url() -> dict:
    dm = DataManager()
    df = dm.read_data("selected")
    if df.empty:
        return {}
    out = {}
    for row in df.to_dict("records"):
        url = str(row.get("url") or "").strip()
        if url:
            out[url] = row
    return out


def _update_draft_analysis_in_sheet(*, draft_id: str, analysis: str) -> bool:
    """
    Best-effort persistence: writes analysis back into the `posts_draft` tab.
    Adds missing columns if needed.
    """
    try:
        config = load_config()
        analysis_model = str(config.get("ANALYSIS_MODEL", "gpt-4o-mini"))
        ran_at = datetime.now(timezone.utc).isoformat()

        dm = DataManager()
        if not dm.use_sheets or not dm.gc:
            logger.warning("Analysis persistence skipped: not connected to Sheets.")
            return False

        sh = dm.gc.open(SHEET_NAME_DEFAULT)
        ws = sh.worksheet(TARGET_DRAFT_TAB)

        values = ws.get_all_values()
        if not values:
            return False
        headers = values[0]

        def ensure_col(name: str) -> int:
            if name in headers:
                return headers.index(name) + 1
            headers.append(name)
            ws.update("A1", [headers])
            return len(headers)

        draft_col = ensure_col("draft_id")
        report_col = ensure_col("analysis_report")
        model_col = ensure_col("analysis_model")
        ran_col = ensure_col("analysis_ran_at_utc")

        row_idx = None
        for i in range(2, len(values) + 1):
            row = values[i - 1]
            if draft_col <= len(row) and str(row[draft_col - 1]).strip() == draft_id:
                row_idx = i
                break
        if not row_idx:
            return False

        ws.update_cell(row_idx, report_col, analysis)
        ws.update_cell(row_idx, model_col, analysis_model)
        ws.update_cell(row_idx, ran_col, ran_at)
        return True
    except Exception as e:
        logger.warning(f"Analysis persistence failed for draft_id={draft_id}: {e}")
        return False


def build_page_html() -> str:
    config = load_config()
    analysis_model = str(config.get("ANALYSIS_MODEL", "gpt-4o-mini"))
    require_paid_confirm = bool(config.get("REQUIRES_USER_APPROVAL_BEFORE_PAID_SPEND", True))

    posts = _load_posts_for_review()
    posts.sort(key=lambda x: x.get("drafted_at") or x.get("published_at") or "", reverse=True)
    selected = _selected_map_by_url()

    head = (
        HTML_TEMPLATE_HEAD.replace("__ANALYSIS_MODEL__", analysis_model)
        .replace("__REQUIRE_PAID_CONFIRM__", "true" if require_paid_confirm else "false")
    )
    chunks = [head]

    for p in posts:
        draft_id = str(p.get("draft_id") or "")
        link = str(p.get("link") or "")
        sel = selected.get(link, {}) if link else {}

        title = str(sel.get("title") or "Article")
        bucket = str(sel.get("bucket") or "")
        source_date = str(sel.get("source_date") or "")
        article_text = str(sel.get("article_text_truncated") or "")
        post_text = str(p.get("text") or "")

        domain = ""
        try:
            if link:
                domain = urlparse(link).netloc.upper().replace("WWW.", "")
        except Exception:
            domain = ""

        image_path = str(p.get("image_path") or "")
        image_html = f'<div class="placeholder">Article Image Preview</div>'
        if image_path and os.path.exists(image_path):
            basename = os.path.basename(image_path)
            image_html = f'<img class="img" src="/images/{_escape(basename)}" alt="Post image"/>'

        chunks.append(f'<div class="review-row" id="row-{_escape(draft_id)}">')

        # Article panel
        chunks.append('<div class="article-col">')
        chunks.append(f'<div class="panel article-panel" id="article-panel-{_escape(draft_id)}">')
        chunks.append('<div class="panel-header">')
        chunks.append('<div class="label">Article</div>')
        chunks.append(f'<div class="title">{_escape(title)}</div>')
        chunks.append('<div class="meta">')
        if bucket:
            chunks.append(f'<span>{_escape(bucket)}</span>')
        if source_date:
            chunks.append(f'<span>{_escape(source_date)}</span>')
        if link:
            chunks.append(f'<a href="{_escape(link)}" target="_blank">{_escape(domain or link)}</a>')
        chunks.append('</div></div>')
        chunks.append(f'<div class="body collapsed" id="article-{_escape(draft_id)}">{_escape(article_text) if article_text else "(no article text)"}' + '</div>')
        chunks.append('<div class="controls">')
        chunks.append(f'<button class="btn" id="article-btn-{_escape(draft_id)}" onclick="toggle(\'article-{_escape(draft_id)}\', \'article-btn-{_escape(draft_id)}\')">...see more</button>')
        chunks.append('</div></div></div>')

        # Post panel
        chunks.append('<div class="post-col">')
        chunks.append(f'<div class="panel post-panel" id="post-panel-{_escape(draft_id)}">')
        chunks.append('<div class="panel-header">')
        chunks.append('<div class="label">Post</div>')
        chunks.append(f'<div class="title">{_escape(bucket) if bucket else "Post"}</div>')
        chunks.append('<div class="meta">')
        chunks.append(f'<span class="pill">{_escape(draft_id)}</span>')
        if link:
            chunks.append(f'<a href="{_escape(link)}" target="_blank">{_escape(domain or link)}</a>')
        chunks.append('</div></div>')
        chunks.append(f'<div class="post-content collapsed" id="post-{_escape(draft_id)}">{_escape(post_text) if post_text else "(no post text)"}' + '</div>')
        chunks.append(image_html)
        chunks.append('<div class="controls">')
        chunks.append(f'<button class="btn" id="post-btn-{_escape(draft_id)}" onclick="toggle(\'post-{_escape(draft_id)}\', \'post-btn-{_escape(draft_id)}\')">...see more</button>')
        chunks.append(f'<button class="btn primary" id="analyze-btn-{_escape(draft_id)}" onclick="analyze(\'{_escape(draft_id)}\')">Analyze vs article ({_escape(analysis_model)})</button>')
        chunks.append(f'<span class="status" id="analysis-status-{_escape(draft_id)}"></span>')
        chunks.append(f'<span class="status" id="analysis-saved-{_escape(draft_id)}"></span>')
        chunks.append('</div>')
        chunks.append(f'<div class="body" id="analysis-{_escape(draft_id)}" style="border-top:1px solid rgba(0,0,0,0.06); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px;"></div>')
        chunks.append('</div></div>')

        chunks.append('</div>')

    chunks.append(HTML_TEMPLATE_FOOT)
    return "\n".join(chunks)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, content_type: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/images/"):
            basename = self.path.replace("/images/", "", 1).split("?", 1)[0].strip()
            if not basename or "/" in basename or "\\" in basename:
                return self._send(400, "text/plain; charset=utf-8", b"Bad image path")
            img_path = os.path.join("execution", "images", basename)
            if not os.path.exists(img_path):
                return self._send(404, "text/plain; charset=utf-8", b"Image not found")
            ctype, _ = mimetypes.guess_type(img_path)
            ctype = ctype or "application/octet-stream"
            with open(img_path, "rb") as f:
                body = f.read()
            return self._send(200, ctype, body)

        if self.path == "/" or self.path.startswith("/?"):
            page = build_page_html().encode("utf-8")
            return self._send(200, "text/html; charset=utf-8", page)
        return self._send(404, "text/plain; charset=utf-8", b"Not Found")

    def do_POST(self):
        if self.path != "/api/analyze":
            return self._send(404, "text/plain; charset=utf-8", b"Not Found")

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8"))
            draft_id = str(data.get("draft_id") or "").strip()
            if not draft_id:
                raise ValueError("Missing draft_id")

            posts = _load_posts_for_review()
            post = next((p for p in posts if str(p.get("draft_id") or "") == draft_id), None)
            if not post:
                raise ValueError(f"draft_id not found: {draft_id}")

            link = str(post.get("link") or "").strip()
            selected = _selected_map_by_url()
            sel = selected.get(link, {}) if link else {}

            payload = {
                "bucket": str(sel.get("bucket") or ""),
                "title": str(sel.get("title") or ""),
                "url": link,
                "post_text": str(post.get("text") or ""),
                "article_text": str(sel.get("article_text_truncated") or ""),
            }

            analysis = analyze_post_vs_article(payload)
            saved = _update_draft_analysis_in_sheet(draft_id=draft_id, analysis=analysis)
            resp = json.dumps({"analysis": analysis, "saved": saved}, ensure_ascii=False).encode("utf-8")
            return self._send(200, "application/json; charset=utf-8", resp)
        except Exception as e:
            resp = json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8")
            return self._send(400, "application/json; charset=utf-8", resp)


def main():
    httpd = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    logger.info(f"Review server running: {url}")

    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        pass

    httpd.serve_forever()


if __name__ == "__main__":
    main()
