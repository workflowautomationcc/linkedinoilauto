import os
import sys
import logging
import gspread

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, SHEET_NAME_DEFAULT

def fix_headers():
    logger.info("Checking Sheet headers...")
    dm = DataManager()
    
    if not dm.use_sheets:
        logger.error("Not connected to Sheets. Cannot fix headers.")
        return

    try:
        sh = dm.gc.open(SHEET_NAME_DEFAULT)
        worksheet = sh.worksheet("raw_candidates")
        
        headers = worksheet.row_values(1)
        logger.info(f"Current headers: {headers}")
        
        expected_cols = ["bucket", "title", "url", "snippet", "source_date", "timestamp"]
        
        # Check if timestamp is missing
        if "timestamp" not in headers:
            logger.info("'timestamp' header missing. Appending it.")
            # We assume the data is there (appended by previous runs), just header is missing.
            # If we just append to the header row, gspread should handle it.
            
            # Find the next column index
            next_col = len(headers) + 1
            worksheet.update_cell(1, next_col, "timestamp")
            logger.info("Updated header row.")
        else:
            logger.info("'timestamp' header already exists.")
            
    except Exception as e:
        logger.error(f"Error fixing headers: {e}")

if __name__ == "__main__":
    fix_headers()
