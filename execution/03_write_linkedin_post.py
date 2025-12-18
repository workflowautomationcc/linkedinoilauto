import os
import sys
import json
import uuid
import logging
from datetime import datetime, timezone
import pandas as pd

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import load_config, DataManager, query_llm, logger
from execution.image_generation import get_or_generate_image

INPUT_TAB = "selected"
OUTPUT_TAB = "posts_draft"

def load_prompt_template(bucket: str) -> str:
    """Loads the appropriate post writing prompt based on bucket."""
    # Map bucket names to prompt files
    bucket_map = {
        "Upstream": "write_post_upstream",
        "General": "write_post_general",
        "AI & Automation": "write_post_ai_automation",
        "Regulation": "write_post_regulation"
    }
    
    prompt_name = bucket_map.get(bucket, "write_post_general")  # Default to general
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

def draft_post(item: dict) -> str:
    """Drafts a LinkedIn post using bucket-specific prompt."""
    bucket = item.get('bucket', 'General')
    
    # Load appropriate prompt template
    prompt_template = load_prompt_template(bucket)
    
    # Build article context
    evidence_notes = item.get('key_evidence_notes', 'No evidence provided.')
    
    article_context = f"""
ARTICLE TO WRITE ABOUT:
{'-'*60}

Title: {item.get('title', 'N/A')}
Source: {item.get('source_name', 'N/A')}
Publish Date: {item.get('source_date', 'N/A')}
Bucket: {bucket}

Evidence Notes:
{evidence_notes}

URL: {item.get('url', 'N/A')}
"""
    
    # Combine prompt + article context
    full_prompt = f"{prompt_template}\n\n{article_context}"
    
    try:
        # Request post as plain text (new prompt format)
        response = query_llm(full_prompt, temperature=0.7)
        
        # Return the full response as the post text
        # No JSON parsing needed - prompt returns ready-to-post text
        return response.strip()
    except Exception as e:
        logger.error(f"Drafting failed for {item.get('url')}: {e}")
        return ""

def run_drafting():
    config = load_config()
    run_size = config.get("RUN_SIZE", "TEST")
    
    logger.info(f"Starting Drafting. Mode: {run_size}")
    
    dm = DataManager()
    df_selected = dm.read_data(INPUT_TAB)
    
    if df_selected.empty:
        logger.warning("No selected items to draft.")
        return

    # Filter for ready_for_write == YES
    # Handle casing just in case
    if 'ready_for_write' not in df_selected.columns:
        logger.warning("'ready_for_write' column missing. Drafting nothing.")
        return

    mask = df_selected['ready_for_write'].str.upper() == "YES"
    to_draft = df_selected[mask].to_dict('records')
    
    logger.info(f"Found {len(to_draft)} items ready for write.")
    
    # Filter out already drafted URLs
    df_existing_drafts = dm.read_data(OUTPUT_TAB)
    if not df_existing_drafts.empty and 'url' in df_existing_drafts.columns:
        existing_urls = set(df_existing_drafts['url'].astype(str).tolist())
        to_draft = [item for item in to_draft if item.get('url') not in existing_urls]
        logger.info(f"Filtered down to {len(to_draft)} items pending draft (others already drafted).")
    
    drafts = []
    for item in to_draft:
        logger.info(f"Drafting post for: {item.get('title')}")
        
        post_text = draft_post(item)
        if not post_text:
            continue
            
        # Extract hook (first paragraph) for preview
        lines = post_text.split('\n')
        hook_line = lines[0] if lines else ""
        
        # Generate draft ID
        draft_id = str(uuid.uuid4())[:8]
        
        # Try to generate/scrape image if enabled
        image_info = {"image_path": "", "image_source": "none", "image_prompt": "", "image_origin_url": ""}
        if config.get('GENERATE_IMAGES', False):
            logger.info(f"Image generation enabled for draft {draft_id}")
            try:
                image_info = get_or_generate_image(
                    article_url=item.get('url', ''),
                    article_title=item.get('title', ''),
                    post_text=post_text,
                    bucket=item.get('bucket', 'General'),
                    draft_id=draft_id
                )
                if image_info.get("image_path"):
                    logger.info(f"✓ Image ready: {image_info.get('image_path')}")
                else:
                    logger.warning(f"Image generation/scraping failed for {draft_id}")
            except Exception as e:
                logger.error(f"Image generation error for {draft_id}: {e}")
        else:
            logger.info("Image generation disabled (GENERATE_IMAGES=NO)")
        
        # Timestamp for when post was drafted
        drafted_at = datetime.now(timezone.utc).isoformat()
        
        row = {
            "drafted_at": drafted_at,
            "draft_id": draft_id,
            "bucket": item.get('bucket'),
            "url": item.get('url'),
            "title": item.get('title'),
            "source_date": item.get('source_date'),
            "post_text": post_text,
            "hook_line": hook_line[:100],  # First 100 chars as preview
            "image_path": image_info.get("image_path", ""),
            "image_source": image_info.get("image_source", "none"),
            "image_prompt": image_info.get("image_prompt", ""),
            "image_origin_url": image_info.get("image_origin_url", ""),
            "status": "needs_review",
            "created_at_utc": datetime.now(timezone.utc).isoformat()
        }
        drafts.append(row)
        
    if drafts:
        logger.info(f"Saving {len(drafts)} drafts to '{OUTPUT_TAB}'.")
        dm.save_data(OUTPUT_TAB, drafts)
    else:
        logger.info("No drafts generated.")

if __name__ == "__main__":
    run_drafting()
