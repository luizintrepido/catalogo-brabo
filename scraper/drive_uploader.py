"""
Módulo responsável por criar pastas e fazer upload de arquivos no Google Drive.
"""
import io
import logging
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import config

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveUploader:
    def __init__(self):
        self.service = self._authenticate()
        self._folder_cache: dict[tuple, str] = {}

    def _authenticate(self):
        creds = None
        if os.path.exists(config.GOOGLE_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_FILE, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
                    raise FileNotFoundError(f"'{config.GOOGLE_CREDENTIALS_FILE}' não encontrado!")
                flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, SCOPES)
                flow.redirect_uri = "http://localhost"
                auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
                print("\n" + "="*60)
                print("  AUTORIZAÇÃO DO GOOGLE DRIVE")
                print("="*60)
                print("\nPASSO 1 — Abra este link no navegador:\n")
                print(auth_url)
                print("\nPASSO 2 — Faça login e clique em 'Permitir'")
                print("\nPASSO 3 — Copie o link completo da barra de endereço")
                print("         (começa com: http://localhost/?code=...)\n")
                redirect_url = input("PASSO 4 — Cole o link aqui e aperte Enter:\n> ").strip()
                from urllib.parse import urlparse, parse_qs
                params = parse_qs(urlparse(redirect_url).query)
                code = params.get("code", [None])[0]
                if not code:
                    raise ValueError("Código de autorização não encontrado!")
                flow.fetch_token(code=code)
                creds = flow.credentials
            with open(config.GOOGLE_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        return build("drive", "v3", credentials=creds)

    def make_public(self, file_id: str):
        """Torna um arquivo público (qualquer pessoa pode visualizar)."""
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
            ).execute()
        except Exception as e:
            logger.warning(f"Não foi possível tornar arquivo público {file_id}: {e}")

    def create_folder_if_not_exists(self, name: str, parent_id: str = None) -> str:
        cache_key = (name, parent_id)
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        results = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                meta["parents"] = [parent_id]
            folder = self.service.files().create(body=meta, fields="id").execute()
            folder_id = folder["id"]
            logger.info(f"Pasta criada: '{name}'")
        self._folder_cache[cache_key] = folder_id
        return folder_id

    def folder_has_files(self, folder_id: str) -> bool:
        r = self.service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive", fields="files(id)", pageSize=1
        ).execute()
        return len(r.get("files", [])) > 0

    def file_exists_in_folder(self, filename: str, folder_id: str) -> bool:
        r = self.service.files().list(
            q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
            spaces="drive", fields="files(id)", pageSize=1
        ).execute()
        return len(r.get("files", [])) > 0

    def get_file_id_in_folder(self, filename: str, folder_id: str) -> str | None:
        r = self.service.files().list(
            q=f"name='{filename}' and '{folder_id}' in parents and trashed=false",
            spaces="drive", fields="files(id)", pageSize=1
        ).execute()
        files = r.get("files", [])
        return files[0]["id"] if files else None

    def list_files_in_folder(self, folder_id: str) -> list[dict]:
        """Lista todos os arquivos de uma pasta. Retorna lista de {id, name, size}."""
        results = []
        page_token = None
        while True:
            params = dict(
                q=f"'{folder_id}' in parents and trashed=false",
                spaces="drive",
                fields="nextPageToken, files(id, name, size)",
                pageSize=100,
            )
            if page_token:
                params["pageToken"] = page_token
            r = self.service.files().list(**params).execute()
            results.extend(r.get("files", []))
            page_token = r.get("nextPageToken")
            if not page_token:
                break
        return results

    def list_subfolders(self, parent_id: str) -> list[dict]:
        """Lista subpastas de uma pasta. Retorna lista de {id, name}."""
        results = []
        page_token = None
        while True:
            params = dict(
                q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="nextPageToken, files(id, name)",
                pageSize=100,
            )
            if page_token:
                params["pageToken"] = page_token
            r = self.service.files().list(**params).execute()
            results.extend(r.get("files", []))
            page_token = r.get("nextPageToken")
            if not page_token:
                break
        return results

    def delete_file(self, file_id: str):
        """Apaga permanentemente um arquivo do Drive."""
        try:
            self.service.files().delete(fileId=file_id).execute()
        except Exception as e:
            logger.warning(f"Erro ao apagar arquivo {file_id}: {e}")

    def download_file_bytes(self, file_id: str) -> bytes | None:
        """Baixa o conteúdo de um arquivo do Drive."""
        try:
            return self.service.files().get_media(fileId=file_id).execute()
        except Exception:
            return None

    def upload_text(self, content: str, filename: str, folder_id: str,
                    mime_type: str = "text/plain", make_public: bool = False) -> str | None:
        if self.file_exists_in_folder(filename, folder_id):
            fid = self.get_file_id_in_folder(filename, folder_id)
            # Atualiza conteúdo
            if fid:
                fh = io.BytesIO(content.encode("utf-8"))
                media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=False)
                self.service.files().update(fileId=fid, media_body=media).execute()
                return fid
            return None
        fh = io.BytesIO(content.encode("utf-8"))
        meta = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=False)
        f = self.service.files().create(body=meta, media_body=media, fields="id").execute()
        fid = f["id"]
        if make_public:
            self.make_public(fid)
        return fid

    def upload_bytes(self, data: bytes, filename: str, folder_id: str,
                     mime_type: str = "image/jpeg", make_public: bool = True) -> str | None:
        existing_id = self.get_file_id_in_folder(filename, folder_id)
        if existing_id:
            logger.debug(f"'{filename}' já existe, pulando.")
            return existing_id
        fh = io.BytesIO(data)
        meta = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=True, chunksize=1024 * 256)
        f = self.service.files().create(body=meta, media_body=media, fields="id").execute()
        fid = f["id"]
        if make_public:
            self.make_public(fid)
        return fid

    def drive_thumb_url(self, file_id: str, size: int = 520) -> str:
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{size}"

    def drive_photo_url(self, file_id: str) -> str:
        return f"https://drive.google.com/uc?id={file_id}&export=view"
