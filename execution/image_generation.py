"""
Image generation utilities for LinkedIn posts.
Hybrid approach: Try scraping article image, fallback to AI generation.
"""

import os
import requests
from typing import Optional, Dict, Any, List, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

# Import after adding to path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execution.utils import query_llm

logger = logging.getLogger("workflow")

IMAGES_DIR = "execution/images"

def ensure_images_dir():
    """Create images directory if it doesn't exist."""
    os.makedirs(IMAGES_DIR, exist_ok=True)

def _is_http_url(value: str) -> bool:
    v = (value or "").strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def _looks_like_logo(url: str) -> bool:
    u = (url or "").lower()
    tokens = ["logo", "brand", "icon", "favicon", "sprite", "seal", "mark", "wordmark"]
    if any(t in u for t in tokens):
        return True
    # Known patterns for share images that are usually brand/stock tiles rather than article imagery
    if any(t in u for t in ["mcguirewoods", "researchandmarkets", "research-and-markets"]):
        return True
    if u.endswith(".svg") or "svg" in u:
        return True
    return False


def _get_image_dimensions(path: str) -> Optional[Tuple[int, int]]:
    """
    Lightweight image dimension parsing without external deps.
    Supports: PNG, JPEG, GIF, WEBP.
    """
    try:
        with open(path, "rb") as f:
            header = f.read(64)
            f.seek(0)
            data = f.read()

        # PNG
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            return width, height

        # GIF
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            if len(data) >= 10:
                width = int.from_bytes(data[6:8], "little")
                height = int.from_bytes(data[8:10], "little")
                return width, height

        # WEBP (RIFF)
        if data.startswith(b"RIFF") and b"WEBP" in data[8:16]:
            # Basic parsing for VP8X/VP8/VP8L chunks
            # VP8X: width-1 and height-1 at offsets 24..30
            if b"VP8X" in data[12:32] and len(data) >= 30:
                width = 1 + int.from_bytes(data[24:27], "little")
                height = 1 + int.from_bytes(data[27:30], "little")
                return width, height

        # JPEG: scan for SOF marker
        if data.startswith(b"\xff\xd8"):
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                # Standalone markers
                if marker in (0xD8, 0xD9):
                    i += 2
                    continue
                if i + 4 > len(data):
                    break
                seg_len = int.from_bytes(data[i + 2 : i + 4], "big")
                if seg_len < 2:
                    break
                # SOF0, SOF2
                if marker in (0xC0, 0xC2) and i + 2 + seg_len <= len(data):
                    # precision = data[i+4]
                    height = int.from_bytes(data[i + 5 : i + 7], "big")
                    width = int.from_bytes(data[i + 7 : i + 9], "big")
                    return width, height
                i += 2 + seg_len
    except Exception:
        return None

    return None


def _extract_image_candidates(page_url: str, html_text: str) -> List[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    candidates: List[str] = []

    def add(u: str):
        if not u:
            return
        u = u.strip()
        if not _is_http_url(u):
            u = urljoin(page_url, u)
        if u not in candidates:
            candidates.append(u)

    # Social preview images (often OK, but sometimes logos)
    for meta in soup.select("meta[property='og:image'], meta[property='og:image:secure_url']"):
        add(meta.get("content", ""))
    for meta in soup.select("meta[name='twitter:image'], meta[name='twitter:image:src']"):
        add(meta.get("content", ""))

    # In-article images (prefer these if social images look like logos)
    for selector in ["article img", "main img", "figure img", ".content img", ".article img"]:
        for img in soup.select(selector):
            add(img.get("src", "") or img.get("data-src", "") or img.get("data-lazy-src", ""))

    return candidates[:12]


def scrape_article_best_image(url: str, draft_id: str) -> Optional[Dict[str, str]]:
    """
    Attempts to find a relevant in-article image.
    Rejects likely logos and too-small images, then downloads the best candidate locally.
    Returns: {"image_path": local path, "image_origin_url": image url} if found; otherwise None.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()

        candidates = _extract_image_candidates(url, response.text)
        if not candidates:
            return None

        ensure_images_dir()
        final_path = os.path.join(IMAGES_DIR, f"{draft_id}_scraped.jpg")

        # Try candidates in order, but skip obvious logos early
        for cand in candidates:
            if _looks_like_logo(cand):
                logger.info(f"Skipping likely logo image: {cand}")
                continue

            tmp_path = os.path.join(IMAGES_DIR, f"{draft_id}_cand.tmp")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            if not download_image(cand, tmp_path):
                continue

            # Basic size gate
            file_size = 0
            try:
                file_size = os.path.getsize(tmp_path)
            except Exception:
                file_size = 0

            dims = _get_image_dimensions(tmp_path)
            if not dims:
                logger.info(f"Rejecting image (unknown dimensions): {cand}")
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                continue

            width, height = dims
            min_width = 700
            min_height = 350
            min_bytes = 80_000

            if width < min_width or height < min_height or file_size < min_bytes:
                logger.info(
                    f"Rejecting image (too small) url={cand} dims={width}x{height} bytes={file_size}"
                )
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                continue

            # Accept: move into final location
            try:
                if os.path.exists(final_path):
                    os.remove(final_path)
            except Exception:
                pass
            os.replace(tmp_path, final_path)
            return {"image_path": final_path, "image_origin_url": cand}

        return None
    except Exception as e:
        logger.warning(f"Failed to scrape image from {url}: {e}")
        return None

def download_image(image_url: str, save_path: str) -> bool:
    """Download image from URL to local path."""
    try:
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Downloaded image to {save_path}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to download image from {image_url}: {e}")
        return False

def generate_image_prompt(post_text: str, bucket: str, article_title: str = "") -> str:
    """
    Use OpenAI to generate a Fal.ai image prompt based on post content.
    """
    # Load prompt template
    prompt_template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "directives",
        "prompts",
        "generate_image_prompt.md"
    )
    
    with open(prompt_template_path, 'r') as f:
        template = f.read()
    
    # Combine template with article data
    full_prompt = f"""{template}

---
INPUT:

**Bucket:** {bucket}
**Article Title:** {article_title}
**Post Text:**
{post_text}

---
Generate the Fal.ai image prompt now (return ONLY the prompt, no explanation):
"""
    
    # Call OpenAI
    image_prompt = query_llm(full_prompt, temperature=0.7)
    return image_prompt.strip()

def generate_image_with_fal(prompt: str, draft_id: str) -> Optional[Dict[str, str]]:
    """
    Generate image using Fal.ai and save locally.
    Returns: {"image_path": local file path, "image_url": remote url} if successful, None otherwise.
    """
    try:
        import fal_client
    except ImportError:
        logger.error("fal_client not installed")
        return None
    
    # Check API key
    api_key = os.getenv("FAL_KEY")
    if not api_key:
        logger.error("FAL_KEY not found in environment")
        return None
    
    try:
        # Generate image
        logger.info(f"Generating image with Fal.ai: {prompt[:60]}...")
        result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "image_size": "landscape_16_9",  # LinkedIn optimized
                "num_inference_steps": 4,
                "num_images": 1,
            },
        )
        
        image_url = result['images'][0]['url']
        logger.info(f"Image generated: {image_url}")
        
        # Download image
        ensure_images_dir()
        local_path = os.path.join(IMAGES_DIR, f"{draft_id}.jpg")
        
        if not download_image(image_url, local_path):
            return None

        return {"image_path": local_path, "image_url": image_url}
            
    except Exception as e:
        logger.error(f"Fal.ai image generation failed: {e}")
        return None

def get_or_generate_image(
    article_url: str,
    article_title: str,
    post_text: str,
    bucket: str,
    draft_id: str
) -> Dict[str, Any]:
    """
    Main function: Try scraping article image, fallback to AI generation.
    Returns a dict with fields:
      - image_path: local image path (or "")
      - image_source: "scraped" | "ai" | "none"
      - image_prompt: prompt used for AI generation (or "")
      - image_origin_url: scraped image url or generated image url (or "")
    """
    ensure_images_dir()
    
    # Strategy 1: Try scraping article image
    logger.info(f"Attempting to scrape image from article: {article_url}")
    scraped = scrape_article_best_image(article_url, draft_id=draft_id)
    if scraped and scraped.get("image_path"):
        logger.info(f"✓ Using scraped article image: {scraped.get('image_path')}")
        return {
            "image_path": scraped.get("image_path", ""),
            "image_source": "scraped",
            "image_prompt": "",
            "image_origin_url": scraped.get("image_origin_url", ""),
        }
    
    # Strategy 2: Generate with AI
    logger.info("Scraping failed, generating image with AI...")
    
    # Generate Fal.ai prompt using OpenAI
    image_prompt = generate_image_prompt(post_text, bucket, article_title)
    logger.info(f"Generated image prompt: {image_prompt}")
    
    # Generate image with Fal.ai
    result = generate_image_with_fal(image_prompt, draft_id)
    
    if not result:
        logger.warning("Both scraping and AI generation failed")
        return {"image_path": "", "image_source": "none", "image_prompt": "", "image_origin_url": ""}

    local_path = result.get("image_path", "")
    image_url = result.get("image_url", "")
    logger.info(f"✓ Generated AI image: {local_path}")
    return {
        "image_path": local_path,
        "image_source": "ai",
        "image_prompt": image_prompt,
        "image_origin_url": image_url,
    }
