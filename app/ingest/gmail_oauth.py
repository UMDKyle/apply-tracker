from __future__ import annotations
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


def load_credentials(client_secret_file: str, token_file: str, scopes: list[str]) -> Credentials:
    """
    Returns Google OAuth credentials.
    - If token_file exists: load it (contains refresh token usually)
    - If expired: refresh automatically
    - Else: run local server flow to get a new token
    """
    token_path = Path(token_file)
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes=scopes)

    if creds and creds.expired and creds.refresh_token:
        # Refresh without user interaction
        creds.refresh(Request())
    elif not creds or not creds.valid:
        # First-time interactive login
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes=scopes)
        creds = flow.run_local_server(port=0)
        # run_local_server is the documented recommended approach for installed apps :contentReference[oaicite:5]{index=5}

    # Persist token for future runs
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds
