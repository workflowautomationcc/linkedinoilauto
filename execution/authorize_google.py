import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

# Scopes: Drive Read/Write + Sheets Read/Write
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

def main():
    client_secrets_path = os.getenv("GOOGLE_OAUTH_CLIENT_JSON_PATH")
    token_path = os.getenv("GOOGLE_TOKEN_PATH")

    if not client_secrets_path:
        print("Error: GOOGLE_OAUTH_CLIENT_JSON_PATH not set in .env")
        return

    if not os.path.exists(client_secrets_path):
        print(f"Error: Client secrets file not found at {client_secrets_path}")
        return

    creds = None
    if token_path and os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            print(f"Token saved to {token_path}")

if __name__ == '__main__':
    main()
