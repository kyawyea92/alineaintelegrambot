import os
import requests
import json
from google.oauth2.service_account import Credentials
import google.auth.transport.requests
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive"]

def upload_to_drive(local_path, filename, folder_id):
    email = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    raw_key = os.getenv("GOOGLE_PRIVATE_KEY", "")
    if not (email and raw_key):
        print("Missing credentials")
        return
        
    private_key = raw_key.replace("\\n", "\n")
    creds = Credentials.from_service_account_info(
        {
            "type": "service_account",
            "project_id": "alineain-menu-telegram-bot",
            "private_key_id": "key",
            "private_key": private_key,
            "client_email": email,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES,
    )
    
    # Refresh/get access token
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    access_token = creds.token
    
    metadata = {
        "name": filename,
        "parents": [folder_id]
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    files = {
        "data": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
        "file": (filename, open(local_path, "rb"), "application/octet-stream")
    }
    
    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    response = requests.post(url, headers=headers, files=files)
    print("Response Status Code:", response.status_code)
    print("Response Body:", response.text)
    if response.status_code == 200:
        return response.json().get("id")
    return None

if __name__ == "__main__":
    # Create a dummy file
    with open("dummy.txt", "w") as f:
        f.write("Hello Drive!")
    
    folder_id = "1ztev83FQZfqgNbUKNTKAmri0RQ5mCASY"
    file_id = upload_to_drive("dummy.txt", "dummy.txt", folder_id)
    print("Uploaded File ID:", file_id)
    
    # Clean up
    if os.path.exists("dummy.txt"):
        os.remove("dummy.txt")
