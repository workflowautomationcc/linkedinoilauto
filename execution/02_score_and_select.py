import os
import sys
import json
import logging
import hashlib
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import load_config, DataManager, query_llm, logger
from newspaper import Article

INPUT_TAB = "raw_candidates"
OUTPUT_TAB = "selected"

def load_prompt_template(prompt_name: str) -> str:
    """Loads a prompt template from directives/prompts/."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "directives",
        "prompts",
        f"{prompt_name}.md"
    )
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt template not found: {prompt_path}")
        raise

def fetch_full_text(url: str) -> str:
    """Fetches article text using newspaper3k."""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        logger.warning(f"FullText fetch failed for {url}: {e}")
        return ""

def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

def _truncate_for_sheet(text: str, max_chars: int = 45000) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]

def score_item(item: Dict, full_text: str = "") -> Dict:
    """Uses LLM to score the item."""
    
    # Load appropriate prompt template
    if full_text:
        # Pass 2: full text available
        prompt_template = load_prompt_template("pass2_scoring")
        content = full_text
    else:
        # Pass 1: metadata only
        prompt_template = load_prompt_template("pass1_scoring")
        content = item.get('snippet', '')
    
    # Build context to inject into prompt
    article_context = f"""
Title: {item.get('title', 'N/A')}
Source: {item.get('source_name', 'N/A')}
Publish Date: {item.get('source_date', 'N/A')}
Query Bucket Hint: {item.get('bucket', 'N/A')}

Snippet/Content:
{content[:2000] if not full_text else content[:5000]}
"""
    
    # Combine prompt template + article context
    full_prompt = f"{prompt_template}\n\n{'-'*60}\nARTICLE TO SCORE:\n{'-'*60}\n\n{article_context}"
    
    try:
        response = query_llm(full_prompt, temperature=0.0)
        
        # Parse JSON
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
            
        data = json.loads(response)
        return data
    except Exception as e:
        logger.error(f"Scoring failed for {item.get('url')}: {e}")
        return {
            "final_bucket": "reject",
            "bucket_reason": f"Scoring error: {str(e)}",
            "relevance_score": 1,
            "freshness_score": 1,
            "credibility_score": 1,
            "practicality_score": 1,
            "linkedin_worthiness_score": 1
        }


def run_scoring():
    config = load_config()
    run_size = config.get("RUN_SIZE", "TEST")
    
    logger.info(f"Starting Scoring. Mode: {run_size}")
    
    dm = DataManager()
    df_raw = dm.read_data(INPUT_TAB)
    
    if df_raw.empty:
        logger.warning("No raw candidates to score.")
        return

    # Check for existing processed items in Output Tab
    df_existing = dm.read_data(OUTPUT_TAB)
    processed_urls = set()
    if not df_existing.empty and 'url' in df_existing.columns:
        processed_urls = set(df_existing['url'].astype(str).tolist())
    
    # Filter df_raw
    original_count = len(df_raw)
    df_raw = df_raw[~df_raw['url'].isin(processed_urls)]
    filtered_count = len(df_raw)
    
    if filtered_count < original_count:
        logger.info(f"Skipping {original_count - filtered_count} already processed items.")
        
    if df_raw.empty:
        logger.info("No NEW candidates to score.")
        return

    # Process per bucket
    buckets = df_raw['bucket'].unique().tolist()
    if not buckets:
        buckets = [] # empty
        
    winners = []
    
    # Convert 'status' column if missing
    if 'status' not in df_raw.columns:
        df_raw['status'] = 'new'
        
    for bucket in buckets:
        logger.info(f"Processing bucket: {bucket}")
        
        # Filter candidates for this bucket that are 'new'
        # Note: raw_candidates might not have 'status' yet if just sourced.
        mask = (df_raw['bucket'] == bucket)
        candidates = df_raw[mask].to_dict('records')
        
        if not candidates:
            continue
            
        # Pass 1: Score all 'new'
        scored_candidates = []
        for c in candidates:
            # Simple Pass 1 scoring
            res = score_item(c)
            
            # Handle reject
            if res.get('final_bucket') == 'reject':
                logger.info(f"Rejected: {c['url']} - {res.get('bucket_reason', 'N/A')}")
                continue
            
            # Update bucket if Pass 1 overrode it
            c['bucket'] = res.get('final_bucket', c['bucket'])
            
            # Calculate total score from individual dimensions
            total_score = (
                res.get('relevance_score', 0) * 2.0 +  # Weight relevance higher
                res.get('freshness_score', 0) * 1.0 +
                res.get('credibility_score', 0) * 1.5 +
                res.get('practicality_score', 0) * 1.5 +
                res.get('linkedin_worthiness_score', 0) * 1.0
            ) / 7.0  # Normalize 
            
            c['score_pass1'] = total_score
            c['bucket_reason'] = res.get('bucket_reason', '')
            c['relevance_score'] = res.get('relevance_score', 0)
            c['freshness_score'] = res.get('freshness_score', 0)
            c['credibility_score'] = res.get('credibility_score', 0)
            c['practicality_score'] = res.get('practicality_score', 0)
            c['linkedin_worthiness_score'] = res.get('linkedin_worthiness_score', 0)
            scored_candidates.append(c)
            
        # Sort by Score
        scored_candidates.sort(key=lambda x: x.get('score_pass1', 0), reverse=True)
        
        # Shortlist Logic
        # Test: Top 2, Prod: Top 5
        shortlist_count = 2 if run_size == "TEST" else 5
        shortlist = scored_candidates[:shortlist_count]
        
        # Pass 2: Full Text
        final_pool = []
        for i, item in enumerate(shortlist):
            limit_fetch = config.get(f"FULLTEXT_FETCH_PER_BUCKET_{run_size}", 1)
            
            # Fetch?
            full_text = ""
            if i < limit_fetch:
                logger.info(f"Fetching full text for {item['url']}")
                full_text = fetch_full_text(item['url'])
                
                # If fetch failed (paywall, 403, etc.), reject immediately
                if not full_text:
                    logger.warning(f"Rejected due to paywall/fetch failure: {item['url']}")
                    continue
            
            # Rescore with evidence (full text is required now)
            if full_text:
                res2 = score_item(item, full_text)
                
                # Handle reject in Pass 2
                if res2.get('final_bucket') == 'reject':
                    logger.info(f"Rejected in Pass 2: {item['url']} - {res2.get('bucket_reason', 'N/A')}")
                    continue
                    
                # Update bucket if Pass 2 overrode it
                item['bucket'] = res2.get('final_bucket', item['bucket'])
                
                # Recalculate total score
                # Note: Pass 2 doesn't re-score freshness (metadata-based), reuse from Pass 1
                total_score_p2 = (
                    res2.get('relevance_score', 0) * 2.0 +
                    item.get('freshness_score', 3) * 1.0 +  # Reuse from Pass 1
                    res2.get('credibility_score', 0) * 1.5 +
                    res2.get('practicality_score', 0) * 1.5 +
                    res2.get('linkedin_worthiness_score', 0) * 1.0
                ) / 7.0
                
                item['score_pass2'] = total_score_p2
                
                # Handle evidence_notes (array in Pass 2)
                evidence = res2.get('evidence_notes', [])
                if isinstance(evidence, list):
                    item['key_evidence_notes'] = "; ".join(evidence)
                else:
                    item['key_evidence_notes'] = str(evidence)
                    
                item['bucket_reason'] = res2.get('bucket_reason', '')
                item['final_score'] = item['score_pass2']
                item['article_text_hash'] = _sha256(full_text)
                item['article_text_truncated'] = _truncate_for_sheet(full_text)
            else:
                # Should not reach here anymore, but safety fallback
                logger.warning(f"Skipping item without full text: {item['url']}")
                continue

            final_pool.append(item)
            
        # Select Winners
        # Sort by final score
        final_pool.sort(key=lambda x: x.get('final_score', 0), reverse=True)
        
        if final_pool:
            w = final_pool[0]
            w['selection_role'] = 'winner'
            w['status'] = 'selected_winner'
            winners.append(w)
            
            # Backups
            backups_count = config.get("BACKUPS_PER_BUCKET", 2)
            for b in final_pool[1:1+backups_count]:
                b['selection_role'] = 'backup'
                b['status'] = 'selected_backup'
                winners.append(b)

    # Save Selected
    if winners:
        
        # Determine Ready For Write
        # Test: Only 1 total. Prod: All winners.
        # Find absolute max score among winners
        best_winner = max([w for w in winners if w['selection_role'] == 'winner'], key=lambda x: x.get('final_score', 0), default=None)
        
        # Timestamp for when items were selected
        selected_at = datetime.now(timezone.utc).isoformat()
        
        selected_rows = []
        for w in winners:
            is_ready = "NO"
            if run_size == "TEST":
                if w == best_winner and w['selection_role'] == 'winner':
                    is_ready = "YES"
            else:
                if w['selection_role'] == 'winner':
                    is_ready = "YES"

            selected_rows.append({
                "selected_at": selected_at,
                "bucket": w['bucket'],
                "selection_role": w['selection_role'],
                "final_score": w.get('final_score'),
                "ready_for_write": is_ready,
                "bucket_reason": w.get('bucket_reason'),
                "url": w['url'],
                "title": w['title'],
                "source_date": w['source_date'],
                "key_evidence_notes": w.get('key_evidence_notes', ''),
                "article_text_truncated": w.get("article_text_truncated", ""),
                "article_text_hash": w.get("article_text_hash", ""),
            })
            
        logger.info(f"Saving {len(selected_rows)} selected items to '{OUTPUT_TAB}'.")
        dm.save_data(OUTPUT_TAB, selected_rows)
        
        # Update Raw Statuses (Optional implementation detail: requires updating original rows)
        # For MVP, we skip updating raw sheet in place to avoid row mismatch complexity 
        # unless dealing with real Google Sheets row IDs.
        # Since we are likely using CSV or Append-Only sheets, modifying past rows is hard without unique IDs.
        # We'll just leave them as 'new' or implement a separate status update if strict.
        # BUT: For the pipeline to work, we need to know what's selected. 
        # The 'Selected' tab acts as the source of truth for Step 03.
        
    else:
        logger.info("No winners selected.")
        
if __name__ == "__main__":
    run_scoring()
