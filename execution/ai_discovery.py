#!/usr/bin/env python3
"""
AI Discovery Pipeline - Cloud-safe execution script.

This script discovers AI/ML articles relevant to oilfield services and appends
them to the AI_Discovery Google Sheet tab. Designed for headless cloud execution.

All configuration comes from environment variables:
- TAVILY_API_KEY: Tavily API key (required)
- GOOGLE_SHEET_ID: Google Sheet ID (optional, uses default if not set)
- GOOGLE_CREDENTIALS_JSON: Google OAuth credentials as JSON string (optional, uses service account if available)

Usage:
    python execution/ai_discovery.py

Exit codes:
    0: Success
    1: Configuration error (missing required env vars)
    2: API error (Tavily or Google Sheets)
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlunparse, parse_qs
from typing import Dict, List, Set
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, SHEET_NAME_DEFAULT

try:
    from tavily import TavilyClient
except ImportError:
    logger.error("tavily package not installed. Install with: pip install tavily-python")
    sys.exit(1)

# Configuration from environment
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")  # Optional, uses default if not set
OUTPUT_TAB = "AI_Discovery"

# Blocked domains (PR wires)
BLOCKED_DOMAINS = {
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "newswire.ca",
    "einpresswire.com"
}

# Search queries for AI in oilfield services
SEARCH_QUERIES = [
    "AI oilfield services",
    "machine learning drilling operations",
    "artificial intelligence upstream oil gas",
    "AI predictive maintenance oilfield",
    "ML completion optimization",
    "Halliburton AI machine learning",
    "SLB artificial intelligence",
    "Baker Hughes AI",
    "AI drilling optimization",
    "machine learning production optimization oilfield"
]

# Target volume
TARGET_NET_NEW = 10


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication: lowercase, remove trailing slash, remove tracking params."""
    if not url:
        return ""
    
    # Parse URL
    parsed = urlparse(url.lower().strip())
    
    # Remove common tracking parameters
    query_params = parse_qs(parsed.query)
    tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 
                       'ref', 'source', 'fbclid', 'gclid', '_ga']
    for param in tracking_params:
        query_params.pop(param, None)
    
    # Reconstruct URL without tracking params
    clean_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items()])
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip('/'),  # Remove trailing slash
        parsed.params,
        clean_query,
        ''  # Remove fragment
    ))
    
    return normalized


def title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity between two titles (0.0 to 1.0)."""
    if not title1 or not title2:
        return 0.0
    return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()


def is_blocked_domain(url: str) -> bool:
    """Check if URL is from a blocked PR wire domain."""
    try:
        domain = urlparse(url).netloc.lower()
        # Remove www. prefix for comparison
        domain = domain.replace('www.', '')
        return domain in BLOCKED_DOMAINS
    except:
        return False


def has_explicit_ai(text: str) -> bool:
    """Check if text explicitly mentions AI/ML (not just generic automation)."""
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Explicit AI/ML terms (required)
    ai_terms = [
        "artificial intelligence",
        "ai ",
        " machine learning",
        " ml ",
        "deep learning",
        "neural network",
        "neural networks",
        "ml model",
        "ai model",
        "ai-powered",
        "ai-driven",
        "ai-enabled"
    ]
    
    # Check for explicit AI mention
    has_ai = any(term in text_lower for term in ai_terms)
    
    if not has_ai:
        return False
    
    # Reject if it's just generic automation without AI context
    generic_only = ["automation", "digital transformation", "iot", "control system"]
    if any(term in text_lower for term in generic_only) and not has_ai:
        return False
    
    return True


def score_relevance(title: str, snippet: str) -> int:
    """Simple relevance score 1-5 based on AI mention and oilfield relevance."""
    text = f"{title} {snippet}".lower()
    
    score = 0
    
    # AI/ML mention (required, but already filtered)
    if has_explicit_ai(text):
        score += 2
    
    # Oilfield services keywords
    oilfield_terms = [
        "oilfield", "upstream", "drilling", "completion", "fracturing", "fracking",
        "well", "rig", "production", "oil and gas", "oil & gas", "petroleum",
        "halliburton", "slb", "schlumberger", "baker hughes", "weatherford",
        "oilfield services", "field operations", "field execution"
    ]
    
    matches = sum(1 for term in oilfield_terms if term in text)
    if matches >= 3:
        score += 3
    elif matches >= 2:
        score += 2
    elif matches >= 1:
        score += 1
    
    # Practical applicability
    practical_terms = ["deployment", "implementation", "case study", "field trial", 
                       "operational", "production", "efficiency", "optimization"]
    if any(term in text for term in practical_terms):
        score += 1
    
    return min(score, 5)  # Cap at 5


def search_with_tavily(query: str, tavily_client: TavilyClient) -> List[Dict]:
    """Search using Tavily API and return results."""
    try:
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=10
        )
        
        results = []
        for r in response.get("results", []):
            results.append({
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("content", "")[:500],  # Limit snippet length
                "published_at": r.get("published_date", ""),
                "source_name": urlparse(r.get("url", "")).netloc.replace("www.", "")
            })
        
        return results
    except Exception as e:
        logger.error(f"Tavily search failed for query '{query}': {e}")
        return []


def deduplicate_candidates(candidates: List[Dict], existing_df) -> List[Dict]:
    """Deduplicate candidates against existing AI_Discovery rows."""
    if existing_df.empty:
        return candidates
    
    # Build sets of existing URLs and titles
    existing_urls = set()
    existing_titles = []
    
    if 'url' in existing_df.columns:
        existing_urls = {normalize_url(url) for url in existing_df['url'].dropna().astype(str)}
    
    if 'title' in existing_df.columns:
        existing_titles = existing_df['title'].dropna().astype(str).tolist()
    
    # Filter candidates
    net_new = []
    for candidate in candidates:
        url = candidate.get('url', '')
        title = candidate.get('title', '')
        
        # Check URL
        normalized_url = normalize_url(url)
        if normalized_url in existing_urls:
            logger.debug(f"Skipping duplicate URL: {url}")
            continue
        
        # Check title similarity
        is_duplicate = False
        for existing_title in existing_titles:
            if title_similarity(title, existing_title) > 0.9:
                logger.debug(f"Skipping similar title: {title} (similar to: {existing_title})")
                is_duplicate = True
                break
        
        if is_duplicate:
            continue
        
        net_new.append(candidate)
    
    return net_new


def run_discovery():
    """Main execution function."""
    logger.info("=== Starting AI Discovery Pipeline ===")
    
    # Validate configuration
    if not TAVILY_API_KEY:
        logger.error("TAVILY_API_KEY environment variable not set. Exiting.")
        sys.exit(1)
    
    # Initialize Tavily client
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Tavily client: {e}")
        sys.exit(2)
    
    # Initialize DataManager
    try:
        dm = DataManager()
        if not dm.use_sheets:
            logger.error("Google Sheets not available. This pipeline requires Google Sheets.")
            sys.exit(2)
    except Exception as e:
        logger.error(f"Failed to initialize DataManager: {e}")
        sys.exit(2)
    
    # Read existing discoveries for deduplication
    try:
        existing_df = dm.read_data(OUTPUT_TAB)
        logger.info(f"Found {len(existing_df)} existing discoveries in {OUTPUT_TAB} tab")
    except Exception as e:
        logger.warning(f"Could not read existing discoveries (tab may not exist yet): {e}")
        existing_df = pd.DataFrame()
    
    # Search and collect candidates
    all_candidates = []
    seen_urls = set()
    
    logger.info(f"Searching with {len(SEARCH_QUERIES)} queries...")
    for query in SEARCH_QUERIES:
        logger.info(f"Query: {query}")
        results = search_with_tavily(query, tavily_client)
        
        for result in results:
            url = result.get('url', '')
            normalized_url = normalize_url(url)
            
            # Skip if already seen in this run
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)
            
            # Skip blocked domains
            if is_blocked_domain(url):
                logger.debug(f"Skipping blocked domain: {url}")
                continue
            
            # Check for explicit AI mention
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            combined_text = f"{title} {snippet}"
            
            if not has_explicit_ai(combined_text):
                logger.debug(f"Skipping (no explicit AI): {title}")
                continue
            
            # Check date (within last 7 days)
            published_at = result.get('published_at', '')
            # If no published date, allow it (we discovered it recently)
            if published_at:
                try:
                    pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    if pub_date < datetime.now(timezone.utc) - timedelta(days=7):
                        logger.debug(f"Skipping (too old): {title}")
                        continue
                except:
                    pass  # If date parsing fails, allow it
            
            # Score relevance
            relevance_score = score_relevance(title, snippet)
            
            # Add to candidates
            all_candidates.append({
                **result,
                'relevance_score': relevance_score,
                'search_query_used': query
            })
    
    logger.info(f"Found {len(all_candidates)} candidates after filtering")
    
    # Deduplicate against existing discoveries
    net_new = deduplicate_candidates(all_candidates, existing_df)
    logger.info(f"After deduplication: {len(net_new)} net-new candidates")
    
    # Sort by relevance score and limit to target
    net_new.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    net_new = net_new[:TARGET_NET_NEW]
    
    if not net_new:
        logger.info("No net-new articles to add. Exiting.")
        return
    
    # Prepare rows for sheet
    discovered_at = datetime.now(timezone.utc).isoformat()
    rows_to_write = []
    
    for candidate in net_new:
        # Extract AI mentions from title/snippet
        ai_mentions = "AI/ML mentioned"
        text = f"{candidate.get('title', '')} {candidate.get('snippet', '')}".lower()
        if "predictive maintenance" in text:
            ai_mentions = "Predictive maintenance"
        elif "drilling optimization" in text or "drilling" in text:
            ai_mentions = "Drilling optimization"
        elif "production optimization" in text:
            ai_mentions = "Production optimization"
        elif "anomaly detection" in text:
            ai_mentions = "Anomaly detection"
        elif "digital twin" in text:
            ai_mentions = "Digital twin"
        
        row = {
            "discovered_at_utc": discovered_at,
            "url": candidate.get('url', ''),
            "title": candidate.get('title', ''),
            "source_name": candidate.get('source_name', ''),
            "published_at": candidate.get('published_at', ''),
            "snippet": candidate.get('snippet', ''),
            "ai_mentions": ai_mentions,
            "relevance_score": candidate.get('relevance_score', 0),
            "access_status": "unknown",  # Could be enhanced with actual access check
            "search_query_used": candidate.get('search_query_used', '')
        }
        rows_to_write.append(row)
    
    # Write to sheet
    try:
        dm.save_data(OUTPUT_TAB, rows_to_write)
        logger.info(f"✓ Successfully wrote {len(rows_to_write)} net-new articles to {OUTPUT_TAB} tab")
        
        # Log summary
        logger.info(f"Summary: found={len(all_candidates)}, rejected={len(all_candidates) - len(net_new)}, deduped={len(all_candidates) - len(net_new)}, written={len(rows_to_write)}")
    except Exception as e:
        logger.error(f"Failed to write to sheet: {e}")
        sys.exit(2)


if __name__ == "__main__":
    try:
        run_discovery()
        logger.info("=== AI Discovery Pipeline Complete ===")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(2)

