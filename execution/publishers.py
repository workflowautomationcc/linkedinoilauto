import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List

from execution.publisher_interface import Post, Publisher

logger = logging.getLogger("workflow")

class LinkedInPublisherStub(Publisher):
    """Local stub that saves posts to a JSON file instead of the API."""
    
    def __init__(self, stub_file_path: str = "execution/stub_posts.json"):
        self.stub_file = stub_file_path
        
    def publish(self, post: Post) -> Post:
        logger.info(f"STUB: Publishing post {post.internal_draft_id}...")
        
        # Simulate ID generation
        fake_id = f"urn:li:share:STUB-{uuid.uuid4()}"
        now_str = datetime.now(timezone.utc).isoformat()
        
        # Update post object
        post.provider_post_id = fake_id
        post.published_at_utc = now_str
        post.status = "published_stub"
        
        # Persist to local JSON
        self._append_to_stub(post)
        
        return post

    def _append_to_stub(self, post: Post):
        data = []
        if os.path.exists(self.stub_file):
            with open(self.stub_file, 'r') as f:
                data = json.load(f)
            
        # Serialize new post
        record = {
            "id": post.provider_post_id,
            "text": post.text,
            "author": post.author_urn,
            "draft_id": post.internal_draft_id,
            "link": post.article_link,
            "image_path": post.media_url,  # Include image
            "published_at": post.published_at_utc,
            "raw_preview": post.text[:50] + "..."
        }
        data.append(record)
        
        with open(self.stub_file, 'w') as f:
            json.dump(data, f, indent=2)


class LinkedInPublisherReal(Publisher):
    """Real implementation (Blocked pending permissions)."""
    
    def __init__(self):
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        
    def publish(self, post: Post) -> Post:
        if not self.access_token:
            post.status = "failed"
            post.error_msg = "Missing LINKEDIN_ACCESS_TOKEN"
            return post
            
        # TODO: Implement actual API call using requests
        # Endpoint: https://api.linkedin.com/v2/ugcPosts or /rest/posts
        
        logger.warning("REAL PUBLISHER NOT IMPLEMENTED YET. Use stub.")
        raise NotImplementedError("LinkedIn API integration pending permissions.")
