# Google Drive Upload Setup (Desktop App OAuth)

To enable "Upload to Google Drive" from the app:

1) Go to https://console.cloud.google.com/apis/credentials (sign in)
2) Create **OAuth client ID**:
   - App type: **Desktop**
   - Name: DailyCompanion (Desktop)
3) Download the JSON → rename to **client_secrets.json**
4) Place `client_secrets.json` in ONE of these:
   - Same folder as `DailyCompanion.exe`, or
   - `%USERPROFILE%\Documents\DailyCompanion\client_secrets.json`
5) First upload will open a browser to grant permission.
   - Scope used: `https://www.googleapis.com/auth/drive.file`
6) A token file (`token.json`) will be saved next to the exe so future uploads are one-click.

Troubleshooting:
- If browser doesn’t open, a local URL will be printed—open it manually and paste the code if asked.
- To reset auth, delete `token.json` and try again.
