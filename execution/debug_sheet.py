import os
import sys
import logging
import pandas as pd

# Add parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.utils import DataManager, logger

def inspect_sheet():
    logger.info("Inspecting 'raw_candidates'...")
    dm = DataManager()
    
    # Read Data
    df = dm.read_data("raw_candidates")
    if df.empty:
        logger.info("Sheet is empty.")
        return

    logger.info(f"Columns: {df.columns.tolist()}")
    logger.info(f"Row Count: {len(df)}")
    
    if 'timestamp' in df.columns:
        logger.info(f"First 5 timestamps: {df['timestamp'].head(5).tolist()}")
        logger.info(f"Last 5 timestamps: {df['timestamp'].tail(5).tolist()}")
        # Check types
        logger.info(f"Timestamp col type: {df['timestamp'].dtype}")
    else:
        logger.warning("'timestamp' column NOT found.")
        # Print first row keys to see what we have
        logger.info(f"First row keys: {df.iloc[0].to_dict().keys()}")

if __name__ == "__main__":
    inspect_sheet()
