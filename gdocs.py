"""Integração com Google Docs (Docs API + Drive API) via OAuth 2.0.

Fluxo:
  1. O usuário clica em "Conectar com Google" -> authorization_url() gera a URL.
  2. Após autorizar, o Google redireciona de volta para o app com ?code=...
  3. exchange_code() troca o code por tokens e persiste o refresh_token no banco.
  4. get_credentials() devolve credenciais válidas (com refresh automático).
  5. fill_template() copia um documento modelo e preenche os campos.
"""
import json
import pathlib
import re
import tomllib
from typing import Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

import db

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]

BASE_DIR = pathlib.Path(__file__).resolve().parent
SECRETS_FILE = BASE_DIR / ".streamlit" / "secrets.toml"

_DEFAULT_REDIRECT = "http://localhost:8501"


def _load_secrets() -> dict:
    try:
        with open(SECRETS_FILE, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def client_id() -> Optional[str]:
    try:
        import streamlit as st
        return st.secrets.get("GOOGLE_CLIENT_ID")
    except Exception:
        return _load_secrets().get("GOOGLE_CLIENT_ID")


def client_secret() -> Optional[str]:
    try:
        import streamlit as st
        return st.secrets.get("GOOGLE_CLIENT_SECRET")
    except Exception:
        return _load_secrets().get("GOOGLE_CLIENT_SECRET")


def redirect_uri() -> str:
    try:
        import streamlit as st
        return st.secrets.get("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT)
    except Exception:
        return _load_secrets().get("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT)


def configurado() -> bool:
    return bool(client_id() and client_secret())


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": client_id(),
            "client_secret": client_secret(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": [redirect_uri()],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri())


def authorization_url() -> str:
    flow = _build_flow()
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    try:
        import streamlit as st
        st.session_state["google_oauth_state"] = state
    except Exception:
        pass
    return url


def exchange_code(code: str, expected_state: str = "") -> Credentials:
    flow = _build_flow()
    state = None
    try:
        import streamlit as st
        state = st.session_state.get("google_oauth_state")
    except Exception:
        pass
    if expected_state and state and expected_state != state:
        raise ValueError("Estado de autenticação inválido (proteção CSRF).")
    flow.fetch_token(code=code)
    creds = flow.credentials
    if creds and creds.refresh_token:
        db.salvar_google_tokens(creds.to_json())
    return creds


def _save(creds: Credentials) -> None:
    try:
        if creds.refresh_token:
            db.salvar_google_tokens(creds.to_json())
    except Exception:
        pass


def get_credentials() -> Optional[Credentials]:
    """Devolve credenciais válidas (da sessão ou do banco), com refresh automático."""
    try:
        import streamlit as st
        cached = st.session_state.get("google_creds")
        if isinstance(cached, Credentials):
            if cached.expired and cached.refresh_token:
                cached.refresh(Request())
                _save(cached)
            return cached
    except Exception:
        pass

    raw = db.obter_google_tokens()
    if not raw:
        return None
    try:
        creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    except Exception:
        return None
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
        except Exception:
            return None
    try:
        import streamlit as st
        st.session_state["google_creds"] = creds
    except Exception:
        pass
    return creds


def disconnect() -> None:
    try:
        import streamlit as st
        st.session_state.pop("google_creds", None)
    except Exception:
        pass
    db.limpar_google_tokens()


def account_info() -> str:
    """Retorna o e-mail/nome da conta conectada (via Drive metadata)."""
    creds = get_credentials()
    if not creds:
        return ""
    try:
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        about = drive.about().get(fields="user").execute()
        user = about.get("user", {})
        return user.get("emailAddress") or user.get("displayName") or ""
    except Exception:
        return ""


def _extract_doc_id(template_url: str) -> str:
    text = template_url.strip()
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", text):
        return text
    raise ValueError("Não foi possível identificar o documento na URL informada.")


def fill_template(template_url: str, placeholders: Dict[str, str], doc_name: str) -> str:
    """Copia um documento modelo e substitui os placeholders no conteúdo.

    Retorna a URL da nova cópia preenchida.
    """
    doc_id = _extract_doc_id(template_url)
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Não conectado ao Google.")

    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    # 1. Ler o texto do modelo para saber quais placeholders existem
    try:
        exported = (
            drive.files()
            .export(fileId=doc_id, mimeType="text/plain")
            .execute()
        )
        template_text = exported.decode("utf-8", errors="replace")
    except Exception:
        template_text = ""

    # 2. Copiar o documento
    copied = (
        drive.files()
        .copy(fileId=doc_id, body={"name": doc_name})
        .execute()
    )
    new_id = copied["id"]

    # 3. Substituir apenas os placeholders presentes no texto do modelo
    requests = []
    keys_found = re.findall(r"\{[^}\n]+\}", template_text or "")
    for key in set(keys_found):
        value = placeholders.get(key, "")
        if value is None:
            value = ""
        requests.append({
            "replaceAllText": {
                "containsText": {"text": key, "matchCase": True},
                "replaceText": str(value),
            }
        })
    if requests:
        docs = build("docs", "v1", credentials=creds, cache_discovery=False)
        docs.documents().batchUpdate(documentId=new_id, body={"requests": requests}).execute()

    return f"https://docs.google.com/document/d/{new_id}/edit"
