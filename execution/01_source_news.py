import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import pandas as pd
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from tavily import TavilyClient

# Add parent directory to path so we can import execution.utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import load_config, DataManager, get_bucket_queries, logger

OUTPUT_TAB = "raw_candidates"

def run_sourcing(force=False):
    config = load_config()
    run_size = config.get("RUN_SIZE", "TEST")
    target_total = config.get(f"CANDIDATE_LINKS_TOTAL_{run_size}", 10)
    freq_hours = config.get("SOURCE_NEWS_FREQUENCY_HOURS", 24)
    
    logger.info(f"Starting Sourcing. Mode: {run_size}, Target Total: {target_total}, Freq Check: {freq_hours}h")

    # 0. Load Existing Data for Checks
    dm = DataManager()
    df_existing = dm.read_data(OUTPUT_TAB)
    existing_urls = set()
    last_run_time = None
    
    if not df_existing.empty:
        if 'url' in df_existing.columns:
            existing_urls = set(df_existing['url'].dropna().astype(str))
            
        if 'timestamp' in df_existing.columns:
            try:
                # Assuming timestamp format matches what we save: ISO 8601
                # We need to parse max timestamp
                logger.info(f"Checking timestamps. Sample: {df_existing['timestamp'].head(1).values}")
                timestamps = pd.to_datetime(df_existing['timestamp'], utc=True, errors='coerce')
                last_run_time = timestamps.max()
                logger.info(f"Max timestamp found: {last_run_time}")
            except Exception as e:
                logger.warning(f"Could not parse timestamps: {e}")
        else:
            logger.warning("'timestamp' column missing from existing data.")

    # 1. Frequency Check
    if last_run_time and not force:
        now = datetime.now(timezone.utc)
        # Ensure last_run_time is timezone aware if now is (it should be from utils)
        if last_run_time.tzinfo is None:
             last_run_time = last_run_time.replace(tzinfo=timezone.utc)
             
        diff = now - last_run_time
        if diff < timedelta(hours=freq_hours):
            logger.info(f"Last run was {diff} ago (Limit: {freq_hours}h). Skipping sourcing. Use --force to override.")
            return

    # 2. Sourcing Logic
    buckets = ["upstream", "general", "ai_automation", "regulation"]
    candidates = []
    
    # Simple distribution of target total
    limit_per_bucket = max(1, target_total // len(buckets))

    # Setup Clients
    tavily_key = os.getenv("TAVILY_API_KEY")
    use_paid = config.get("PAID_APIS_DEFAULT_ALLOWED", False)
    
    tavily_client = None
    if tavily_key and use_paid:
        tavily_client = TavilyClient(api_key=tavily_key)
    else:
        logger.info("Paid APIs not enabled by default. Falling back to DDG.")

    blocked_domains = [
        "businesswire.com",
        "prnewswire.com",
        "globenewswire.com",
        "accesswire.com"
    ]

    for lane in buckets:
        logger.info(f"Searching bucket: {lane}")
        queries = get_bucket_queries(lane)
        
        bucket_candidates = []
        
        for q in queries:
            if len(bucket_candidates) >= limit_per_bucket:
                break
                
            logger.info(f"Query: {q}")
            
            items = []
            try:
                if tavily_client:
                    # Tavily
                    resp = tavily_client.search(query=q, search_depth="basic", max_results=5)
                    results = resp.get("results", [])
                    # map to standard dict
                    for r in results:
                        items.append({
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "snippet": r.get("content"),
                            "date": r.get("published_date") # Tavily might provide
                        })
                else:
                    # DuckDuckGo
                    # Note: DDG python lib changes often. Using DDGS context manager
                    with DDGS() as ddgs:
                        ddg_gen = ddgs.news(q, max_results=5)
                        if ddg_gen:
                            for r in ddg_gen:
                                items.append({
                                    "title": r.get("title"),
                                    "url": r.get("url"), # DDG uses 'url' or 'link'? usually 'url' or 'href'
                                    "snippet": r.get("body"),
                                    "date": r.get("date")
                                })
            except Exception as e:
                logger.error(f"Search failed for '{q}': {e}")
                continue

            # Filter candidates
            for item in items:
                url = item.get("url")
                if not url: continue
                
                # Dedupe within this run
                if any(c['url'] == url for c in candidates): continue
                if any(c['url'] == url for c in bucket_candidates): continue
                
                # Check Global Dedupe (Historical)
                if url in existing_urls:
                    # logger.debug(f"Skipping duplicate URL: {url}")
                    continue

                # Blocked Domains
                if any(dom in url for dom in blocked_domains):
                    continue

                # AI Guardrail 
                if lane == "ai_automation":
                    combined = (item.get("title", "") + " " + item.get("snippet", "")).lower()
                    if "ai" not in combined and "intelligence" not in combined and "automation" not in combined:
                         continue

                # Derive Source Name
                try:
                    domain = urlparse(url).netloc
                    # Strip www. and .com roughly for display
                    source_name = domain.replace('www.', '').split('.')[0].title()
                except:
                    source_name = "Unknown"

                candidate = {
                    "bucket": lane,
                    "title": item.get("title"),
                    "source_name": source_name,
                    "url": url,
                    "snippet": item.get("snippet"),
                    "source_date": item.get("date"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                bucket_candidates.append(candidate)
                
                if len(bucket_candidates) >= limit_per_bucket:
                    break
        
        candidates.extend(bucket_candidates)

    if candidates:
        logger.info(f"Found {len(candidates)} NEW candidates (Dedupe filtered). Saving to '{OUTPUT_TAB}'.")
        dm.save_data(OUTPUT_TAB, candidates)
    else:
        logger.info("No new candidates found.")

if __name__ == "__main__":
    # Check for CLI args (e.g. force)
    force_Arg = False
    if "--force" in sys.argv:
        force_Arg = True
    run_sourcing(force=force_Arg)
