import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger, SHEET_NAME_DEFAULT

def clear_all_sheets():
    dm = DataManager()
    tabs = ["raw_candidates", "selected", "posts_draft", "posts_published"]
    
    if dm.use_sheets:
        try:
            sh = dm.gc.open(SHEET_NAME_DEFAULT)
            for tab in tabs:
                try:
                    worksheet = sh.worksheet(tab)
                    worksheet.clear()
                    logger.info(f"Cleared sheet: {tab}")
                except Exception as e:
                    logger.warning(f"Could not clear {tab}: {e}")
        except Exception as e:
            logger.error(f"Failed to open sheet: {e}")
    else:
        # Clear CSV files
        for tab in tabs:
            path = dm._get_csv_path(tab)
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted CSV: {path}")

if __name__ == "__main__":
    clear_all_sheets()
