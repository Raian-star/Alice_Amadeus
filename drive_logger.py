import os
import json
import logging
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def _obter_servico_drive():
    creds_json_str = os.environ.get("GOOGLE_DRIVE_CREDENTIALS")
    if not creds_json_str:
        return None
    
    try:
        creds_info = json.loads(creds_json_str)
        credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logging.error(f"Erro ao autenticar no Google Drive: {e}")
        return None

def salvar_log_no_drive(conteudo_log: str, nome_arquivo: str = None) -> bool:
    try:
        service = _obter_servico_drive()
        if not service:
            return False

        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "1ML5-hM8pC7gRg9r05RxTZMx5rVRLByV9")
        
        if not nome_arquivo:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = f"alice_erro_{timestamp}.txt"

        file_metadata = {
            'name': nome_arquivo,
            'parents': [folder_id]
        }

        media = MediaInMemoryUpload(
            conteudo_log.encode('utf-8'),
            mimetype='text/plain',
            resumable=True
        )

        service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        return True
    except Exception as e:
        logging.error(f"Falha ao enviar log para o Google Drive: {e}")
        return False