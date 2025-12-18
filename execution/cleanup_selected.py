import os
import sys
import pandas as pd

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, SHEET_NAME_DEFAULT

def cleanup_selected():
    dm = DataManager()
    tab_name = "selected"
    
    logger.info(f"Reading '{tab_name}' for cleanup...")
    df = dm.read_data(tab_name)
    
    if df.empty:
        logger.warning(f"'{tab_name}' is empty.")
        return

    initial_count = len(df)
    
    # Ensure final_score is numeric
    if 'final_score' in df.columns:
        df['final_score'] = pd.to_numeric(df['final_score'], errors='coerce').fillna(0.0)
    else:
        df['final_score'] = 0.0
        
    # Sort by final_score DESC (so best score is first)
    # Then by timestamp descending (if available) to break ties? usually 'source_date' or we don't have write-time there. 
    # We'll trust Score first.
    df = df.sort_values(by=['final_score'], ascending=False)
    
    # Drop duplicates on URL, keeping FIRST (which is Highest Score)
    df_deduped = df.drop_duplicates(subset=['url'], keep='first')
    
    final_count = len(df_deduped)
    removed = initial_count - final_count
    
    logger.info(f"Found {initial_count} rows. Removing {removed} duplicates/low-scores.")
    
    if removed > 0:
        # Save back. 
        # Note: DataManager.save_data *appends* unless we use a custom overwrite method or clear first.
        # DataManager doesn't expose Clear.
        # But `reset_sheet.py` clears. 
        # We need to overwrite.
        # I will use direct gspread access via DM object if possible or just use a helper method.
        # DM.save_data appends. 
        # I will modify DM or use a custom overwrite block here.
        
        if dm.use_sheets:
            try:
                sh = dm.gc.open(SHEET_NAME_DEFAULT)
                # Actually SHEET_NAME_DEFAULT is in utils, imported above? No.
                # It's 'Workflow_Automation_Data'.
                worksheet = sh.worksheet(tab_name)
                worksheet.clear()
                worksheet.append_row(df_deduped.columns.tolist())
                worksheet.append_rows(df_deduped.values.tolist())
                logger.info("Sheet overwritten successfully.")
            except Exception as e:
                logger.error(f"Sheet overwrite failed: {e}")
        else:
            # CSV overwrite is easy in DM logic usually implies append mode in save_data... 
            # actually save_data: `mode='a' if file_exists else 'w'`.
            # If I delete the file and call save_data?
            path = dm._get_csv_path(tab_name)
            if os.path.exists(path):
                os.remove(path)
            dm.save_data(tab_name, df_deduped.to_dict('records'))
            
    else:
        logger.info("No duplicates found to remove.")

if __name__ == "__main__":
    cleanup_selected()
