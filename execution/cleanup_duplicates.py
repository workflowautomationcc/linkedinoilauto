import os
import sys
import logging
import pandas as pd

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger

def cleanup_duplicates():
    logger.info("Starting duplicate cleanup for 'raw_candidates'...")
    dm = DataManager()
    
    # 1. Read Data
    df = dm.read_data("raw_candidates")
    if df.empty:
        logger.info("No data found.")
        return

    logger.info(f"Loaded {len(df)} rows.")
    
    # 2. Deduplicate
    initial_count = len(df)
    
    # Drop duplicates based on 'url', keep 'first'
    if 'url' in df.columns:
        # Sort by timestamp descending so we keep the most recent (and likely valid) timestamp
        if 'timestamp' in df.columns:
            # Convert to datetime for sorting (handling errors)
            df['timestamp_dt'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
            df = df.sort_values(by='timestamp_dt', ascending=False, na_position='last')
            df = df.drop(columns=['timestamp_dt']) # Clean up helper col
            logger.info("Sorted by timestamp descending to keep freshest data.")
            
        df_clean = df.drop_duplicates(subset=['url'], keep='first')
    else:
        logger.warning("'url' column not found. Deduplicating exact rows.")
        df_clean = df.drop_duplicates(keep='first')
        
    final_count = len(df_clean)
    removed = initial_count - final_count
    
    if removed == 0:
        logger.info("No duplicates found. Exiting.")
        return
        
    logger.info(f"Found {removed} duplicates. Overwriting sheet with {final_count} unique rows.")

    # 3. Overwrite
    # DataManager.save_data appends by default. 
    # To overwrite, we need to access the sheet object directly or implement overwrite in Utils.
    # For a one-off, let's just do it here using the authenticated gc client from dm.
    
    if dm.use_sheets:
        try:
            sh = dm.gc.open("Workflow_Automation_Data")
            worksheet = sh.worksheet("raw_candidates")
            worksheet.clear()
            # Rewrite headers and data
            worksheet.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())
            logger.info("Sheet overwritten successfully.")
        except Exception as e:
            logger.error(f"Failed to overwrite sheet: {e}")
            # Save local backup just in case
            df_clean.to_csv("execution/cleaned_backup.csv", index=False)
            logger.info("Saved local backup to execution/cleaned_backup.csv")
    else:
        # CSV mode overwrite
        path = dm._get_csv_path("raw_candidates")
        df_clean.to_csv(path, index=False)
        logger.info(f"CSV overwritten: {path}")

if __name__ == "__main__":
    cleanup_duplicates()
