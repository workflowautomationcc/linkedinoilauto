import os
import sys
import argparse
import logging
import webbrowser

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import logger

# Import step functions
import importlib
source_news = importlib.import_module("execution.01_source_news")
score_select = importlib.import_module("execution.02_score_and_select")
write_post = importlib.import_module("execution.03_write_linkedin_post")
publish_post = importlib.import_module("execution.04_publish_post")

def main():
    parser = argparse.ArgumentParser(description="Run the content workflow pipeline.")
    parser.add_argument("--mode", choices=["TEST", "PROD"], help="Override RUN_SIZE")
    parser.add_argument("--step", choices=["01", "02", "03", "04", "all"], default="all", help="Run specific step or all")
    parser.add_argument("--force", action="store_true", help="Force sourcing even if recent run exists")
    
    args = parser.parse_args()
    
    # 1. Handle Overrides
    if args.mode:
        os.environ["RUN_SIZE"] = args.mode
        logger.info(f"Override: RUN_SIZE set to {args.mode}")

    # 2. Run Steps
    try:
        if args.step in ["01", "all"]:
            logger.info("=== Running Step 01: Sourcing ===")
            # Pass force flag if module supports it
            if hasattr(source_news, 'run_sourcing'):
                 # Check signature or just try? 
                 # We updated it to take force kwarg.
                 source_news.run_sourcing(force=args.force)
            
        if args.step in ["02", "all"]:
            logger.info("=== Running Step 02: Scoring & Selection ===")
            score_select.run_scoring()
            
        if args.step in ["03", "all"]:
            logger.info("=== Running Step 03: Drafting ===")
            write_post.run_drafting()
            
        if args.step in ["04", "all"]:
            logger.info("=== Running Step 04: Publishing (Stub/Real) ===")
            publish_post.run_publishing()
            
        
        logger.info("Pipeline Complete.")
        
        # Auto-open preview if Step 04 ran
        if args.step in ["04", "all"]:
            preview_path = os.path.abspath("execution/preview.html")
            if os.path.exists(preview_path):
                # Generate preview
                os.system("./venv/bin/python execution/preview_stub.py")
                # Open in browser
                webbrowser.open(f"file://{preview_path}")
                logger.info(f"Preview opened in browser: {preview_path}")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
