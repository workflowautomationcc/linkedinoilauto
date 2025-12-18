import os
import sys
import logging
import gspread

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, SHEET_NAME_DEFAULT

def reset_sheet():
    logger.info("Resetting 'raw_candidates' with correct schema...")
    dm = DataManager()
    
    if not dm.use_sheets:
        logger.error("Not connected to Sheets.")
        return

    try:
        sh = dm.gc.open(SHEET_NAME_DEFAULT)
        worksheet = sh.worksheet("raw_candidates")
        
        # CLEAR ALL
        worksheet.clear()
        
        # Write Headers
        headers = ['bucket', 'title', 'source_name', 'url', 'snippet', 'source_date', 'timestamp']
        worksheet.append_row(headers)
        
        logger.info(f"Sheet cleared and initialized with headers: {headers}")
            
    except Exception as e:
        logger.error(f"Error resetting sheet: {e}")

if __name__ == "__main__":
    reset_sheet()
