"""YouTube (Shorts) yükleyici — YouTube Data API v3 + OAuth.

Kurulum:
  1. Google Cloud Console'da bir proje aç, "YouTube Data API v3"ü etkinleştir.
  2. OAuth istemci kimliği (Masaüstü uygulaması) oluştur, JSON'u indir ve
     secrets/youtube_client_secret.json olarak kaydet.
  3. İlk çalıştırmada tarayıcı açılır ve KENDİ hesabınla yetki verirsin;
     token secrets/youtube_token.json'a kaydedilir (bir daha sorulmaz).
"""

from __future__ import annotations

from pathlib import Path

from .base import Uploader, UploadResult

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader(Uploader):
    name = "youtube"

    @property
    def client_secret_path(self) -> Path:
        return self.secrets_dir / "youtube_client_secret.json"

    @property
    def token_path(self) -> Path:
        return self.secrets_dir / "youtube_token.json"

    def is_configured(self) -> bool:
        return self.token_path.exists() or self.client_secret_path.exists()

    def _load_credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds
        if not self.client_secret_path.exists():
            raise FileNotFoundError(
                f"YouTube istemci gizli anahtarı yok: {self.client_secret_path}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), SCOPES)
        creds = flow.run_local_server(port=0)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def authorize(self) -> str:
        self._load_credentials()
        return "YouTube yetkilendirmesi tamam. Token kaydedildi."

    def upload(self, clip_path: Path, meta: dict) -> UploadResult:
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except Exception as e:  # noqa: BLE001
            return UploadResult("youtube", "error", error=f"google-api-python-client gerekli: {e}")

        try:
            creds = self._load_credentials()
            youtube = build("youtube", "v3", credentials=creds)

            title = self._title(meta)[:100]
            body = {
                "snippet": {
                    "title": title,
                    "description": self._description(meta),
                    "tags": self._hashtags(meta)[:15],
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": meta.get("privacy", "private"),
                    "selfDeclaredMadeForKids": False,
                },
            }
            media = MediaFileUpload(str(clip_path), chunksize=-1, resumable=True)
            request = youtube.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = request.execute()
            vid = response.get("id")
            return UploadResult(
                "youtube", "ok", id=vid, url=f"https://youtube.com/shorts/{vid}"
            )
        except Exception as e:  # noqa: BLE001
            return UploadResult("youtube", "error", error=str(e))
