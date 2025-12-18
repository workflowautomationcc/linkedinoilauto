import os
import sys
import pandas as pd

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, SHEET_NAME_DEFAULT

def cleanup_drafts():
    dm = DataManager()
    tab_name = "posts_draft"
    
    logger.info(f"Reading '{tab_name}' for cleanup...")
    df = dm.read_data(tab_name)
    
    if df.empty:
        logger.warning(f"'{tab_name}' is empty.")
        return

    initial_count = len(df)
    
    # Sort by created_at_utc DESC (keep latest)
    # If no created_at, rely on order (which is usually append order, so last is latest)
    # But reverse it to keep first after drop_duplicates
    # Just use 'keep=last' on original dataframe? No, drop_duplicates keeps first by default.
    # So sort descending (newest first).
    if 'created_at_utc' in df.columns:
        df = df.sort_values(by=['created_at_utc'], ascending=False)
    
    # Dedupe by URL (one draft per article)
    # Or by 'title'? URL is safer.
    df_deduped = df.drop_duplicates(subset=['url'], keep='first')
    
    final_count = len(df_deduped)
    removed = initial_count - final_count
    
    logger.info(f"Found {initial_count} rows. Removing {removed} duplicates.")
    
    if removed > 0:
        if dm.use_sheets:
            try:
                sh = dm.gc.open(SHEET_NAME_DEFAULT)
                worksheet = sh.worksheet(tab_name)
                worksheet.clear()
                worksheet.append_row(df_deduped.columns.tolist())
                worksheet.append_rows(df_deduped.values.tolist())
                logger.info("Sheet overwritten successfully.")
            except Exception as e:
                logger.error(f"Sheet overwrite failed: {e}")
        else:
            path = dm._get_csv_path(tab_name)
            if os.path.exists(path):
                os.remove(path)
            dm.save_data(tab_name, df_deduped.to_dict('records'))
    else:
        logger.info("No duplicates found.")

if __name__ == "__main__":
    cleanup_drafts()
