import os
import json
import html
import sys
import webbrowser
from datetime import datetime

STUB_FILE = "execution/stub_posts.json"
OUTPUT_HTML = "execution/preview.html"

# Ensure we can import `execution.utils` when running as `python execution/preview_stub.py`
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execution.utils import load_config

# CSS and SVG Icons for LinkedIn Look-and-Feel
CSS = """
    body { font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Fira Sans", Ubuntu, Oxygen, "Oxygen Sans", Cantarell, "Droid Sans", "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Lucida Grande", Helvetica, Arial, sans-serif; background: #f3f2ef; padding: 20px; color: rgba(0,0,0,0.9); }
    .container { max-width: 1200px; margin: 0 auto; }
    h1 { color: #000000bf; font-size: 20px; text-align:center; padding-bottom:20px;}

    /* Review Layout */
    .review-row { display: flex; gap: 16px; margin-bottom: 20px; align-items: stretch; }
    .article-col { flex: 1 1 auto; min-width: 380px; }
    .post-col { flex: 0 0 500px; }
    @media (max-width: 980px) {
        .review-row { flex-direction: column; }
        .article-col, .post-col { flex: 1 1 auto; min-width: 0; }
    }

    .article-panel {
        background: white;
        border-radius: 8px;
        box-shadow: 0 0 0 1px rgba(0,0,0,0.08), 0 2px 2px rgba(0,0,0,0.05);
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: 0;
    }
    .article-header { padding: 12px 16px 8px; border-bottom: 1px solid rgba(0,0,0,0.06); }
    .article-label { font-size: 12px; color: rgba(0,0,0,0.6); font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
    .article-title { font-size: 16px; font-weight: 600; margin-top: 6px; color: rgba(0,0,0,0.9); line-height: 1.25; }
    .article-meta { font-size: 12px; color: rgba(0,0,0,0.6); margin-top: 6px; display: flex; gap: 10px; flex-wrap: wrap; }
    .article-meta a { color: rgba(0,0,0,0.6); text-decoration: none; }
    .article-meta a:hover { text-decoration: underline; }
    .article-body { padding: 12px 16px; font-size: 13px; line-height: 1.4; color: rgba(0,0,0,0.9); white-space: pre-wrap; overflow: auto; flex: 1 1 auto; min-height: 0; }
    .article-body.collapsed { max-height: calc(1.4em * 18); overflow: hidden; }
    .article-controls { padding: 8px 16px 12px; border-top: 1px solid rgba(0,0,0,0.06); }
    .article-toggle-btn { background: none; border: none; color: rgba(0,0,0,0.6); font-weight: 600; font-size: 14px; cursor: pointer; padding: 4px 0; }
    .article-toggle-btn:hover { text-decoration: underline; }
    .analyze-btn { background: none; border: none; color: #0a66c2; font-weight: 700; font-size: 14px; cursor: pointer; padding: 4px 0; margin-left: 16px; }
    .analyze-btn:hover { text-decoration: underline; }
    
    /* Post Card */
    .post-card { 
        background: white; 
        border-radius: 8px; 
        margin-bottom: 0; 
        box-shadow: 0 0 0 1px rgba(0,0,0,0.08), 0 2px 2px rgba(0,0,0,0.05); 
        overflow: hidden;
    }

    /* Header */
    .post-header { padding: 12px 16px 0; display: flex; margin-bottom: 8px;}
    .avatar { width: 48px; height: 48px; border-radius: 50%; background: #0a66c2; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold; margin-right: 12px; font-size:20px;}
    .header-info { flex: 1; }
    .author-name { font-size: 14px; font-weight: 600; color: rgba(0,0,0,0.9); display:block; }
    .author-desc { font-size: 12px; color: rgba(0,0,0,0.6); display:block; margin-top: 2px;}
    .post-time { font-size: 12px; color: rgba(0,0,0,0.6); display: flex; align-items: center; margin-top:2px;}
    .globe-icon { width: 12px; height: 12px; fill: rgba(0,0,0,0.6); margin-left: 4px; }

    /* Content */
    .post-content { padding: 0 16px; font-size: 14px; line-height: 1.4; color: rgba(0,0,0,0.9); white-space: pre-wrap; margin-bottom: 8px; position: relative; text-indent: 0; }
    .post-content.collapsed { max-height: calc(1.4em * 3); overflow: hidden; }
    .see-more-btn { background: none; border: none; color: rgba(0,0,0,0.6); font-weight: 600; font-size: 14px; cursor: pointer; padding: 4px 0; margin-left: 16px; }
    .see-more-btn:hover { text-decoration: underline; }

    /* Link Preview Card */
    .link-preview { 
        margin-top: 8px;
        background: #eef3f8; /* background for image placeholder */
        border: 1px solid #e0e0e0; /* border for whole card is uncommon in feed, usually full width image + strip */
        border-width: 1px 0; /* Full bleed usually */
        text-decoration: none; 
        display: block; 
        cursor: pointer;
    }
    .lp-image-placeholder {
        height: 280px;
        background-color: #dbe7f1;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #5e6d7a;
        font-weight: 500;
        font-size: 18px;
    }
    .lp-meta {
        background: #f9fafb;
        padding: 12px 16px;
        border-top: 1px solid rgba(0,0,0,0.05);
    }
    .lp-title { font-size: 14px; font-weight: 600; color: rgba(0,0,0,0.9); margin-bottom: 4px; display:block; 
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .lp-domain { font-size: 12px; color: rgba(0,0,0,0.6); display:block;}

    /* Footer Stats/Actions */
    .social-counts { padding: 8px 16px; font-size: 12px; color: rgba(0,0,0,0.6); border-bottom: 1px solid #e0e0e0; list-style:none; display:flex;}
    .social-counts li { margin-right: 10px; }
    
    .action-bar { display: flex; justify-content: space-around; padding: 4px 8px; }
    .action-btn { 
        background: none; border: none; 
        display: flex; align-items: center; 
        padding: 10px 8px; 
        border-radius: 4px; 
        color: rgba(0,0,0,0.6); 
        font-weight: 600; font-size: 14px; 
        cursor: pointer;
    }
    .action-btn:hover { background-color: rgba(0,0,0,0.05); }
    .action-btn svg { width: 24px; height: 24px; margin-right: 8px; fill: rgba(0,0,0,0.6); }

"""

SVG_GLOBE = '<svg class="globe-icon" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg"><path d="M8 1a7 7 0 107 7 7 7 0 00-7-7zM3 8a5 5 0 011-3l.55.55A1.5 1.5 0 015 6.62v1.07a.75.75 0 00.22.53l.56.56a.75.75 0 00.53.22H7a.75.75 0 001-.75v-.63a1.5 1.5 0 011.5-1.5H10a1.5 1.5 0 011.5 1.5v.55L10.5 9A1.5 1.5 0 019 10.5H5.62l-2-2A4.94 4.94 0 013 8zm9.32 2l-1.07-1.06a.76.76 0 00-.53-.22H10.5a.25.25 0 00-.25-.25v-.55a.25.25 0 00-.25-.25H9.5a.25.25 0 00-.25.25v.63a2 2 0 01-1.35 1.9l-.65.22a.24.24 0 00-.17.22v.79A.75.75 0 007.83 13a5 5 0 01-3.6-1.57l2.8-2.8a2 2 0 011.41-.59h1a2 2 0 012 2v.22a5 5 0 01-.12 1.06z"/></svg>'
SVG_LIKE = '<svg viewBox="0 0 24 24"><path d="M19.46 11l-3.91-3.91a7 7 0 01-1.69-2.74l-.49-1.47A2.76 2.76 0 0010.76 1 2.75 2.75 0 008 3.74v1.12a2.75 2.75 0 002.75 2.75h2.03l-2.03 2.03a2.75 2.75 0 002.03 4.7h3.12a1 1 0 01.71.29l3.91 3.91A1 1 0 0119.8 19H17v2h2.8a3 3 0 002.12-.88l4.42-4.42A3 3 0 0027.22 13h-4.94a1 1 0 01-.71-.29l-2.11-2.11zM10 7.5A4.75 4.75 0 015.25 2.75V1H3.75A2.75 2.75 0 001 3.75v14.5A2.75 2.75 0 003.75 21H7v-9.5A4.75 4.75 0 011.75 6.75V5.63A4.75 4.75 0 016.5 1h.63A2.88 2.88 0 0110 3.88v3.62z"/></svg>' 
# Using simpler paths or generic standard ones for reliability
SVG_LIKE_SIMPLE = '<svg viewBox="0 0 24 24"><path d="M7 22h-4v-12h4v12zm10.707-16.707c-1.87 0-3.293 1.293-3.293 1.293v-1.586h-4v12h4v-7.293c0-2.31 2.759-2.222 2.759 0v7.293h4v-8.293c0-3.325-3.076-3.413-3.466-3.413z"/></svg>' # This is actually Share/Linkedin Logo? No.
# Authentics from LinkedIn are complex paths. I will use Text Labels with simple SVGs for standard icons.
SVG_THUMB = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>'
SVG_COMMENT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>'
SVG_REPOST = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>'
SVG_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>'

def _safe_text(value: str) -> str:
    return html.escape(value or "")

def load_selected_article_map() -> dict:
    """
    Attempts to load article text/title from the `selected` tab.
    Falls back to empty dict if Sheets/CSV isn't available.
    """
    try:
        from execution.utils import DataManager

        dm = DataManager()
        df = dm.read_data("selected")
        if df.empty:
            return {}

        article_map = {}
        for row in df.to_dict("records"):
            url = str(row.get("url") or "").strip()
            if not url:
                continue
            article_map[url] = {
                "title": str(row.get("title") or "").strip(),
                "bucket": str(row.get("bucket") or "").strip(),
                "source_date": str(row.get("source_date") or "").strip(),
                "article_text": str(row.get("article_text_truncated") or "").strip(),
            }
        return article_map
    except Exception:
        return {}

def generate_preview():
    # Prefer posts from `posts_draft` (Sheet/CSV). Fall back to legacy stub JSON.
    posts = []
    try:
        from execution.utils import DataManager

        dm = DataManager()
        df = dm.read_data("posts_draft")
        if not df.empty:
            posts = df.to_dict("records")
    except Exception:
        posts = []

    if not posts:
        if not os.path.exists(STUB_FILE):
            print("No posts found (no posts_draft and no stub file).")
            return
        with open(STUB_FILE, "r", encoding="utf-8") as f:
            posts = json.load(f)

    selected_articles = load_selected_article_map()

    # Sort (drafted_at preferred; fallback to published_at for legacy stub posts)
    posts.sort(key=lambda x: x.get("drafted_at") or x.get("published_at") or "", reverse=True)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LinkedIn Post Preview</title>
        <style>{CSS}</style>
    </head>
    <body>
        <div class="container">
            <h1>Preview ({len(posts)} Posts)</h1>
    """

    config = load_config()
    analysis_model = str(config.get("ANALYSIS_MODEL", "gpt-4o-mini"))

    for p in posts:
        # Extract Domain
        # Normalize between draft rows vs legacy stub rows
        post_text = p.get("post_text") or p.get("text") or "No content"
        link = p.get("url") or p.get("link") or "#"
        domain = "EXAMPLE.COM"
        try:
            from urllib.parse import urlparse
            if link and link != '#':
                domain = urlparse(link).netloc.upper().replace('WWW.', '')
        except:
            pass

        draft_id = str(p.get("draft_id", "") or "")
        article_info = selected_articles.get(link, {}) if link and link != "#" else {}
        article_title = article_info.get("title") or "Article"
        article_text = article_info.get("article_text") or "No article text found (store `article_text_truncated` in the Selected tab to enable side-by-side review)."
        article_bucket = article_info.get("bucket") or ""
        article_date = article_info.get("source_date") or ""
        
        # Get image path
        image_path = p.get("image_path", "")
        image_html = ""
        
        if image_path and os.path.exists(image_path):
            # Convert to absolute path for file:// URL
            abs_image_path = os.path.abspath(image_path)
            image_html = f'<img src="file://{abs_image_path}" style="width: 100%; max-height: 400px; object-fit: contain; background: #f3f2ef;" alt="Post image"/>'
        else:
            # Placeholder
            image_html = '<div class="lp-image-placeholder">Article Image Preview</div>'

        # Article Panel (left)
        article_panel = f"""
            <div class="article-col">
                <div class="article-panel" id="article-panel-{_safe_text(draft_id)}">
                    <div class="article-header">
                        <div class="article-label">Article</div>
                        <div class="article-title">{_safe_text(article_title)}</div>
                        <div class="article-meta">
                            {f"<span>{_safe_text(article_bucket)}</span>" if article_bucket else ""}
                            {f"<span>{_safe_text(article_date)}</span>" if article_date else ""}
                            {f'<a href="{_safe_text(link)}" target="_blank">{_safe_text(domain)}</a>' if link and link != "#" else ""}
                        </div>
                    </div>
                    <div class="article-body collapsed" id="article-{_safe_text(draft_id)}">{_safe_text(article_text)}</div>
                    <div class="article-controls">
                        <button class="article-toggle-btn" id="article-btn-{_safe_text(draft_id)}" onclick="toggleArticle('{_safe_text(draft_id)}')">...see more</button>
                    </div>
                </div>
            </div>
        """
            
        # Post Card
        card = f"""
            <div class="post-col">
            <div class="post-card" id="post-card-{_safe_text(draft_id)}">
                <!-- Header -->
                <div class="post-header">
                    <div class="avatar">AI</div>
                    <div class="header-info">
                        <span class="author-name">Workflow Automation Bot</span>
                        <span class="author-desc">AI Content Agent • {(_safe_text(article_bucket) + " • ") if article_bucket else ""}1,234 followers</span>
                        <span class="post-time">Now • {SVG_GLOBE}</span>
                    </div>
                </div>
                
                <!-- Content -->
                <div class="post-content collapsed" id="content-{_safe_text(draft_id)}">
                    {_safe_text(post_text)}
                </div>
                <button class="see-more-btn" id="btn-{_safe_text(draft_id)}" onclick="toggleContent('{_safe_text(draft_id)}')">
                    ...see more
                </button>
                <button class="analyze-btn" onclick="openAnalysis('{_safe_text(draft_id)}')">
                    Analyze vs article ({_safe_text(analysis_model)})
                </button>
                
                <!-- Link Preview -->
                <a class="link-preview" href="{link}" target="_blank">
                    {image_html}
                    <div class="lp-meta">
                        <span class="lp-title">{_safe_text((post_text.split('.')[0] if len(post_text) > 0 else 'Article Title'))}...</span>
                        <span class="lp-domain">{domain}</span>
                    </div>
                </a>
                
                <!-- Footer -->
                <ul class="social-counts">
                    <li><span style="color:#0a66c2">Like</span></li>
                    <li><span style="color:#0a66c2">Comment</span></li>
                </ul>
                
                <div class="action-bar">
                    <button class="action-btn">{SVG_THUMB} Like</button>
                    <button class="action-btn">{SVG_COMMENT} Comment</button>
                    <button class="action-btn">{SVG_REPOST} Repost</button>
                    <button class="action-btn">{SVG_SEND} Send</button>
                </div>
            </div>
            </div>
        """
        html_content += f'<div class="review-row">{article_panel}{card}</div>'

    html_content += """
        </div>
        <script>
        function openAnalysis(draftId) {
            // Analysis requires the local review server (`execution/review_app.py`).
            const ok = window.confirm('PLEASE CONFIRM: running analysis will use a paid API and you may be charged.');
            if (!ok) return;
            const url = 'http://127.0.0.1:8765/?draft_id=' + encodeURIComponent(draftId) + '&auto=1&confirmed=1';
            window.open(url, '_blank');
        }

        function syncRowHeights() {
            document.querySelectorAll('.review-row').forEach(function(row) {
                const postCard = row.querySelector('.post-card');
                const articlePanel = row.querySelector('.article-panel');
                if (!postCard || !articlePanel) return;
                // Let post card define the row height; keep article panel scrollable within that height.
                const postHeight = postCard.getBoundingClientRect().height;
                if (postHeight > 0) {
                    articlePanel.style.height = postHeight + 'px';
                }
            });
        }

        function toggleContent(draftId) {
            const content = document.getElementById('content-' + draftId);
            const btn = document.getElementById('btn-' + draftId);
            
            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                btn.textContent = '...see less';
            } else {
                content.classList.add('collapsed');
                btn.textContent = '...see more';
            }
            syncRowHeights();
        }

        function toggleArticle(draftId) {
            const content = document.getElementById('article-' + draftId);
            const btn = document.getElementById('article-btn-' + draftId);
            if (!content || !btn) return;

            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                btn.textContent = '...see less';
            } else {
                content.classList.add('collapsed');
                btn.textContent = '...see more';
            }
            syncRowHeights();
        }
        
        // Hide see more button if content is short
        window.addEventListener('load', function() {
            document.querySelectorAll('.post-content').forEach(function(content) {
                const btn = document.getElementById('btn-' + content.id.replace('content-', ''));
                if (content.scrollHeight <= 80) { // About 3 lines
                    btn.style.display = 'none';
                    content.classList.remove('collapsed');
                }
            });

            document.querySelectorAll('.article-body').forEach(function(content) {
                const btn = document.getElementById('article-btn-' + content.id.replace('article-', ''));
                if (content.scrollHeight <= 260) { // About 18 lines
                    btn.style.display = 'none';
                    content.classList.remove('collapsed');
                }
            });

            // initial layout after images load
            syncRowHeights();
        });

        window.addEventListener('resize', function() {
            syncRowHeights();
        });
        </script>
    </body>
    </html>
    """

    with open(OUTPUT_HTML, 'w') as f:
        f.write(html_content)
        
    abs_out = os.path.abspath(OUTPUT_HTML)
    print(f"Preview generated at: {abs_out}")

    # Auto-open in default browser unless explicitly disabled.
    # - CLI flag: --no-open
    # - Env var: NO_AUTO_OPEN=1
    if "--no-open" not in sys.argv and os.getenv("NO_AUTO_OPEN") not in {"1", "true", "TRUE", "yes", "YES"}:
        try:
            webbrowser.open(f"file://{abs_out}")
        except Exception:
            pass

if __name__ == "__main__":
    generate_preview()
