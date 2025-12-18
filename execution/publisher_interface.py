import abc
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Post:
    """Standard internal representation of a social post."""
    text: str
    author_urn: str  # LinkedIn Organization or Person URN
    idempotency_key: str
    
    # Metadata
    internal_draft_id: Optional[str] = None
    topic_bucket: Optional[str] = None
    
    # Media / Links
    article_link: Optional[str] = None
    media_url: Optional[str] = None
    alt_text: Optional[str] = None
    
    # Provider metadata (filled after publish)
    provider_post_id: Optional[str] = None
    published_at_utc: Optional[str] = None
    status: str = "new"  # new, published, failed, skipped
    error_msg: Optional[str] = None

class Publisher(abc.ABC):
    """Abstract base class for publishing adapters."""
    
    @abc.abstractmethod
    def publish(self, post: Post) -> Post:
        """Publishes the post. Returns the updated Post object (with ID/status)."""
        pass
