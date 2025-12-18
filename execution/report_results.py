import os
import sys
import logging
import pandas as pd

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger

def report_results():
    dm = DataManager()
    
    print("\n=== STEP 2: SELECTED CANDIDATES ===")
    df_sel = dm.read_data("selected")
    if df_sel.empty:
        print("No selections found.")
    else:
        # Show specific cols
        cols = ['bucket', 'final_score', 'ready_for_write', 'title', 'key_evidence_notes']
        # Filter available
        cols = [c for c in cols if c in df_sel.columns]
        print(df_sel[cols].to_string())

    print("\n=== STEP 3: DRAFTED POSTS ===")
    df_drafts = dm.read_data("posts_draft")
    if df_drafts.empty:
        print("No drafts found.")
    else:
        cols = ['status', 'hook_line', 'post_text']
        cols = [c for c in cols if c in df_drafts.columns]
        # Truncate post text
        if 'post_text' in df_drafts.columns:
             # Just show first 100 chars
             df_drafts['post_text_preview'] = df_drafts['post_text'].astype(str).str.slice(0, 100) + "..."
             cols = ['status', 'hook_line', 'post_text_preview']
             
        print(df_drafts[cols].to_string())

if __name__ == "__main__":
    report_results()
