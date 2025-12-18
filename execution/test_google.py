import os
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def main():
    token_path = os.getenv("GOOGLE_TOKEN_PATH")
    if not token_path or not os.path.exists(token_path):
        print("Error: Token file not found. Run authorize_google.py first.")
        return

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    try:
        # 1. Drive List
        print("--- Testing Drive API ---")
        drive_service = build('drive', 'v3', credentials=creds)
        results = drive_service.files().list(
            pageSize=5, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print('No files found in Drive (or permissions issue).')
        else:
            print('Files found:')
            for item in items:
                print(f"  {item['name']} ({item['id']})")

        # 2. Sheets Create & Write
        print("\n--- Testing Sheets API ---")
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        # Create
        spreadsheet = {
            'properties': {
                'title': f'Workflow_Test_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}'
            }
        }
        spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        spreadsheet_id = spreadsheet.get('spreadsheetId')
        print(f"Created Spreadsheet ID: {spreadsheet_id}")
        
        # Write
        values = [
            ["Test from Python"],
            ["Timestamp", str(datetime.datetime.now())],
            ["Status", "Success"]
        ]
        body = {
            'values': values
        }
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range="Sheet1!A1",
            valueInputOption="RAW", body=body).execute()
        print(f"{result.get('updatedCells')} cells updated.")
        
    except HttpError as error:
        print(f"An error occurred: {error}")

if __name__ == '__main__':
    main()
