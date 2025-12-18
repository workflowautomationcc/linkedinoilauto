#!/usr/bin/env python3
"""Test script to verify Fal.ai API is working."""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if fal is installed
try:
    import fal_client
except ImportError:
    print("ERROR: fal_client not installed. Run: pip install fal-client")
    sys.exit(1)

# Check API key (Fal uses FAL_KEY, not FAL_API_KEY)
api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
if not api_key:
    print("ERROR: FAL_KEY not found in .env file")
    print("Please add: FAL_KEY=your-key-here")
    sys.exit(1)

# Set it to FAL_KEY if it was FAL_API_KEY
if not os.getenv("FAL_KEY"):
    os.environ["FAL_KEY"] = api_key

print(f"✓ FAL_KEY found: {api_key[:10]}...")

# Test image generation
print("\nTesting Fal.ai image generation...")
print("Prompt: 'An oil drilling rig at sunset, professional photography'")

try:
    result = fal_client.subscribe(
        "fal-ai/flux/schnell",
        arguments={
            "prompt": "An oil drilling rig at sunset, professional photography",
            "image_size": "landscape_16_9",
            "num_inference_steps": 4,
            "num_images": 1,
        },
    )
    
    print("\n✓ Image generated successfully!")
    print(f"Image URL: {result['images'][0]['url']}")
    print(f"Content type: {result['images'][0].get('content_type', 'N/A')}")
    print(f"\nYou can view the image at the URL above.")
    
    # Save URL to file for reference
    with open("execution/test_image_url.txt", "w") as f:
        f.write(result['images'][0]['url'])
    print(f"\n✓ URL saved to execution/test_image_url.txt")
    
except Exception as e:
    print(f"\n✗ Error generating image: {e}")
    sys.exit(1)
