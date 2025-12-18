import os
import re
import csv
import json
import logging
from time import sleep
import pandas as pd
import gspread # Import at top level to avoid scope issues
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from openai import OpenAI

# Load env vars
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("execution/workflow.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("workflow")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTIVES_DIR = os.path.join(BASE_DIR, "directives")
EXECUTION_DIR = os.path.join(BASE_DIR, "execution")
TMP_DIR = os.path.join(BASE_DIR, ".tmp")
CONFIG_PATH = os.path.join(DIRECTIVES_DIR, "_run_config.md")
SHEET_NAME_DEFAULT = "Workflow_Automation_Data"
FOLDER_NAME_DEFAULT = "Workflow Automation"

# --- Config Parsing ---

def load_config() -> Dict[str, Any]:
    """Parses _run_config.md into a dictionary."""
    config = {}
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"Config file not found at {CONFIG_PATH}. Using empty defaults.")
        return config

    with open(CONFIG_PATH, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        # Look for KEY: VALUE pairs (ignoring comments)
        # Regex handles keys with underscores and values that might be strings or numbers
        match = re.match(r'^([A-Z_]+):\s*(.+)$', line)
        if match and not line.startswith('#'):
            key, value = match.groups()
            # Clean comments from value
            if '#' in value:
                value = value.split('#')[0].strip()
            
            # Type inference
            if value.isdigit():
                config[key] = int(value)
            elif value.upper() in ['YES', 'TRUE', 'ON']:
                config[key] = True
            elif value.upper() in ['NO', 'FALSE', 'OFF']:
                config[key] = False
            else:
                config[key] = value
                
    # Check Env Vars for overrides
    for key in config.keys():
        if key in os.environ:
            val = os.environ[key]
            # Type cast
            if val.isdigit():
                config[key] = int(val)
            elif val.upper() in ['YES', 'TRUE', 'ON']:
                config[key] = True
            elif val.upper() in ['NO', 'FALSE', 'OFF']:
                config[key] = False
            else:
                config[key] = val
                
    return config

# --- Data Access (Sheet vs CSV) ---

class DataManager:
    """Handles reading/writing data to Google Sheets or local CSVs as fallback."""
    
    def __init__(self, mode="auto"):
        self.mode = mode
        self.creds_path = os.path.join(BASE_DIR, "credentials.json") # Old Service Account path
        self.token_path = os.getenv("GOOGLE_TOKEN_PATH") # New OAuth User Token path
        self.use_sheets = False
        self.gc = None
        self.workbook = None
        self.drive_service = None # For folder management
        
        # Check for Authenticated User Token (Preferred)
        if self.token_path and os.path.exists(self.token_path):
            try:
                import gspread
                from google.oauth2.credentials import Credentials
                # Scopes used in authorize_google.py
                SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
                
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                self.gc = gspread.authorize(creds)
                self.drive_service = build('drive', 'v3', credentials=creds) # Init Drive API
                self.use_sheets = True
                logger.info("Connected to Google Sheets via OAuth Token.")
            except Exception as e:
                 logger.warning(f"Failed to connect via OAuth Token: {e}. Checking Service Account...")

        # Fallback to Service Account if Token failed or not present
        if not self.use_sheets and os.path.exists(self.creds_path) and os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
             try:
                import gspread
                self.gc = gspread.service_account(filename=self.creds_path)
                self.use_sheets = True
                logger.info("Connected to Google Sheets via Service Account.")
             except Exception as e:
                 logger.warning(f"Failed to connect via Service Account: {e}. Falling back to CSV.")
                 self.use_sheets = False
        
        if not self.use_sheets:
            logger.info("No valid Google credentials found. Using CSV mode.")

    def _get_csv_path(self, tab_name: str) -> str:
        return os.path.join(BASE_DIR, f"{tab_name}.csv")

    def _get_or_create_folder_id(self, folder_name: str) -> Optional[str]:
        """Finds or creates a folder by name in Drive Root."""
        if not self.drive_service:
            return None
            
        try:
            # Check existence
            # Note: v3 uses 'trashed' not 'trash'
            query = "mimeType='application/vnd.google-apps.folder' and name='Workflow Automation' and trashed=false"
            results = self.drive_service.files().list(q=query, fields="files(id)").execute()
            files = results.get('files', [])
            
            if files:
                return files[0]['id']
            
            # Create
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            file = self.drive_service.files().create(body=file_metadata, fields='id').execute()
            logger.info(f"Created new Drive folder: {folder_name} (ID: {file.get('id')})")
            return file.get('id')
            
        except Exception as e:
            logger.error(f"Drive API error: {e}")
            return None

    def _move_file_to_folder(self, file_id: str, folder_id: str):
        """Moves a file to the specified folder."""
        if not self.drive_service or not folder_id:
            return
            
        try:
            # Retrieve the existing parents to remove
            file = self.drive_service.files().get(fileId=file_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            
            # Move the file by adding the new parent and removing the old one
            self.drive_service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            logger.info(f"Moved file {file_id} to folder {folder_id}.")
        except Exception as e:
            logger.error(f"Failed to move file to folder: {e}")

    def save_data(self, tab_name: str, data: List[Dict]):
        """Appends data to the specified tab (Sheet) or file (CSV)."""
        if not data:
            return

        df_new = pd.DataFrame(data)
        # Avoid NaN causing "nan" strings in Sheets/CSVs
        df_new = df_new.where(pd.notnull(df_new), "")

        if self.use_sheets:
            try:
                # Open or create workbook
                try:
                    sh = self.gc.open(SHEET_NAME_DEFAULT)
                except gspread.SpreadsheetNotFound:
                    # Create in root
                    sh = self.gc.create(SHEET_NAME_DEFAULT)
                    logger.info(f"Created new sheet '{SHEET_NAME_DEFAULT}' (ID: {sh.id}).")
                    
                    # Move to folder if possible
                    if self.drive_service:
                        folder_id = self._get_or_create_folder_id(FOLDER_NAME_DEFAULT)
                        if folder_id:
                            self._move_file_to_folder(sh.id, folder_id)
                
                # Check consistency: if existing sheet is not in folder, we could move it, 
                # but might be risky if user moved it intentionally. 
                # Let's enforce it ONLY on creation for safety, OR if it's clearly in root?
                # For this task: let's enforce moving it if we have the service.
                if self.drive_service:
                    folder_id = self._get_or_create_folder_id(FOLDER_NAME_DEFAULT)
                    if folder_id:
                        self._move_file_to_folder(sh.id, folder_id)

                # Open or create worksheet
                try:
                    worksheet = sh.worksheet(tab_name)
                    headers = worksheet.row_values(1) or []

                    if not headers:
                        headers = df_new.columns.tolist()
                        worksheet.append_row(headers)
                    else:
                        missing_cols = [c for c in df_new.columns.tolist() if c not in headers]
                        if missing_cols:
                            headers = headers + missing_cols
                            worksheet.update("A1", [headers])

                    df_to_append = df_new.reindex(columns=headers, fill_value="")
                    worksheet.append_rows(df_to_append.values.tolist())
                    
                except gspread.WorksheetNotFound:
                    worksheet = sh.add_worksheet(title=tab_name, rows=1000, cols=20)
                    headers = df_new.columns.tolist()
                    worksheet.append_row(headers)
                    worksheet.append_rows(df_new.reindex(columns=headers, fill_value="").values.tolist())
                    
                logger.info(f"Saved {len(data)} rows to Sheet '{SHEET_NAME_DEFAULT}' / '{tab_name}'")

            except Exception as e:
                logger.error(f"Sheet error: {e}. Falling back to CSV save for safety.")
                self._save_csv(tab_name, df_new)
        else:
            self._save_csv(tab_name, df_new)

    def _save_csv(self, tab_name, df_new):
        path = self._get_csv_path(tab_name)
        if not os.path.exists(path):
            df_new.to_csv(path, index=False)
            logger.info(f"Saved {len(df_new)} rows to CSV: {path}")
            return

        try:
            df_old = pd.read_csv(path)
        except Exception:
            df_old = pd.DataFrame()

        all_cols: List[str] = []
        for col in df_old.columns.tolist() + df_new.columns.tolist():
            if col not in all_cols:
                all_cols.append(col)

        df_old = df_old.reindex(columns=all_cols, fill_value="")
        df_new = df_new.reindex(columns=all_cols, fill_value="")

        out = pd.concat([df_old, df_new], ignore_index=True)
        out.to_csv(path, index=False)
        logger.info(f"Saved {len(df_new)} rows to CSV: {path}")

    def read_data(self, tab_name: str) -> pd.DataFrame:
        """Reads data from the specified tab/file."""
        if self.use_sheets:
            try:
                sh = self.gc.open(SHEET_NAME_DEFAULT)
                worksheet = sh.worksheet(tab_name)
                data = worksheet.get_all_records()
                return pd.DataFrame(data)
            except Exception as e:
                logger.warning(f"Could not read from Sheet '{tab_name}': {e}. Trying CSV.")
                pass # Fall through to CSV
        
        path = self._get_csv_path(tab_name)
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame()

# --- Helpers ---

def get_bucket_queries(lane: str) -> List[str]:
    """Returns a list of queries for a given lane. 
    Ideally this would be in a config or directive parsing, 
    but hardcoding logical defaults based on 01_source_news.md for now."""
    
    # Timestamp for fresh search
    # Note: Search APIs usually handle recency, but adding year helps if no date filter
    base = [f"{lane} oilfield services news"]
    
    if lane == "upstream":
        return [
            "oilfield services contract awards last 24h",
            "drilling rig activity news upstream",
            "hydraulic fracturing fleet news",
            "offshore drilling contract news",
            "oil and gas production operations news"
        ]
    elif lane == "general":
        return [
            "oilfield services company news",
            "slb halliburton baker hughes news",
            "oil and gas supply chain news",
            "upstream energy industry trends"
        ]
    elif lane == "ai_automation":
        return [
            "AI in oil and gas upstream",
            "machine learning in drilling operations",
            "oilfield digital transformation AI",
            "generative AI for oil and gas",
            "predictive maintenance oil and gas AI"
        ]
    elif lane == "regulation":
        return [
            "EPA regulations oil and gas upstream",
            "PHMSA pipeline safety rule changes",
            "BLM oil and gas leasing news",
            "EU methane regulation oil and gas"
        ]
    return base

# --- LLM Helper ---

def query_llm(prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.0) -> str:
    """Simple wrapper for OpenAI LLM calls. Returns content string."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found.")
        return ""
        
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""
