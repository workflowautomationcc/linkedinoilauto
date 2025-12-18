import os
import sys
import logging
from typing import List

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import load_config, DataManager, logger
from execution.publisher_interface import Post
from execution.publishers import LinkedInPublisherStub, LinkedInPublisherReal

INPUT_TAB = "posts_draft"
OUTPUT_TAB = "posts_published" # Or update status in drafts? 
# Better: Log attempts to new sheet, but also update status in Drafts if we could.
# Since we use append-only CSV/Sheet abstraction mainly, let's write to a "published_log"
# and we can "simulate" draft status update by reading/writing (not optimal for CSV)
# For this sprint: Write to 'posts_published' log.

def run_publishing():
    config = load_config()
    run_size = config.get("RUN_SIZE", "TEST")
    
    # 1. Select Publisher
    # Config flag? Or ENV?
    # ALLOW_LINKEDIN_POSTING: NO by default in _run_config.md
    allow_real_posting = config.get("ALLOW_LINKEDIN_POSTING", False)
    
    if allow_real_posting:
        logger.warning("Config allows REAL posting. Using Real Publisher (if implemented).")
        publisher = LinkedInPublisherReal()
    else:
        logger.info("Real posting disabled. Using STUB Publisher.")
        publisher = LinkedInPublisherStub()
        
    logger.info(f"Starting Publishing. Mode: {run_size}")
    
    # 2. Read Drafts
    dm = DataManager()
    df_drafts = dm.read_data(INPUT_TAB)
    
    if df_drafts.empty:
        logger.warning("No drafts found to publish.")
        return

    # 3. Filter for 'needs_review' (or 'approved' if we had a manual step)
    # For automation, we might auto-publish if confident, BUT:
    # `03` sets status="needs_review".
    # We need a rule. In TEST mode, maybe we auto-publish the 'needs_review' item?
    # User requirement: "all drafts" produced by step 03 are intended to be "sent" to the publisher 
    # (which is the stub right now).
    
    mask = df_drafts['status'] == 'needs_review'
    to_publish = df_drafts[mask].to_dict('records')
    
    logger.info(f"Found {len(to_publish)} drafts needing publish.")

    # Filter out already published Draft IDs
    df_published = dm.read_data(OUTPUT_TAB)
    if not df_published.empty and 'draft_id' in df_published.columns:
        published_ids = set(df_published['draft_id'].astype(str).tolist())
        to_publish = [item for item in to_publish if item.get('draft_id') not in published_ids]
        logger.info(f"Filtered down to {len(to_publish)} items pending publish (others already published).")
    
    published_records = []
    
    for item in to_publish:
        # Convert dict to Post object
        post = Post(
            text=item.get('text') or item.get('post_text') or "",
            author_urn="urn:li:organization:STUB", # Placeholder
            idempotency_key=item.get('draft_id'),
            internal_draft_id=item.get('draft_id'),
            topic_bucket=item.get('bucket'),
            article_link=item.get('url'),
            media_url=item.get('image_path')  # Include generated image
        )
        
        # Publish
        try:
            result_post = publisher.publish(post)
            
            # Log result
            record = {
                "draft_id": result_post.internal_draft_id,
                "provider_post_id": result_post.provider_post_id,
                "status": result_post.status,
                "published_at": result_post.published_at_utc,
                "error": result_post.error_msg,
                "post_text": result_post.text,
                "text_snippet": result_post.text[:50],
                "bucket": item.get("bucket", ""),
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "image_path": item.get("image_path", ""),
                "image_source": item.get("image_source", ""),
                "image_prompt": item.get("image_prompt", ""),
                "image_origin_url": item.get("image_origin_url", ""),
            }
            published_records.append(record)
            
        except Exception as e:
            logger.error(f"Publish failed for {item.get('draft_id')}: {e}")
            
    if published_records:
        logger.info(f"Writing {len(published_records)} records to '{OUTPUT_TAB}'.")
        dm.save_data(OUTPUT_TAB, published_records)

if __name__ == "__main__":
    run_publishing()
