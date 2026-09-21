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


def _log(msg: str) -> None:
    """Log seguro: nunca expor tokens/secrets. Apenas print para logs do servidor."""
    try:
        # No Streamlit Cloud os prints vão para logs
        print(f"[gdocs] {msg}")
    except Exception:
        pass


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
        # Não adicionar "/" automaticamente; deve ser EXATAMENTE igual ao cadastrado no Google Cloud
        val = st.secrets.get("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT)
        return str(val).strip() if val else _DEFAULT_REDIRECT
    except Exception:
        val = _load_secrets().get("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT)
        return str(val).strip() if val else _DEFAULT_REDIRECT


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
    # access_type offline + prompt consent garante refresh_token no primeiro consentimento
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    try:
        import streamlit as st
        st.session_state["google_oauth_state"] = state
    except Exception:
        pass
    return url


def exchange_code(code: str, expected_state: str = "") -> Credentials:
    if not code or not str(code).strip():
        raise ValueError("Código de autorização vazio.")
    flow = _build_flow()
    state = None
    try:
        import streamlit as st
        state = st.session_state.get("google_oauth_state")
    except Exception:
        pass
    # Validação CSRF: só falha se ambos existirem e forem diferentes
    if expected_state and state and expected_state != state:
        _log("state mismatch")
        raise ValueError("Estado de autenticação inválido (proteção CSRF). Tente novamente.")
    try:
        flow.fetch_token(code=str(code).strip())
    except Exception as e:
        # Não expor code/client_secret nos logs
        _log(f"fetch_token falhou: {type(e).__name__}")
        # Mensagens específicas para diagnóstico seguro
        msg = str(e)
        if "redirect_uri_mismatch" in msg:
            raise RuntimeError(
                "redirect_uri_mismatch: o GOOGLE_REDIRECT_URI configurado não confere com o cadastrado no Google Cloud. "
                f"Verifique se o valor é exatamente '{redirect_uri()}' (sem '/' extra) e se está autorizado em console.cloud.google.com → Credentials → OAuth 2.0 Client ID."
            ) from e
        if "invalid_grant" in msg:
            raise RuntimeError("Código expirado ou já utilizado (invalid_grant). Tente conectar novamente.") from e
        raise RuntimeError(f"Falha ao trocar código por token: {type(e).__name__}") from e
    creds = flow.credentials
    if not creds:
        raise RuntimeError("Não foi possível obter credenciais do Google (creds vazias).")
    if not creds.token:
        raise RuntimeError("Google não retornou access_token.")

    # ── Preservar refresh_token se Google não enviar um novo ──
    # Google só envia refresh_token no primeiro consentimento ou com prompt=consent.
    # Se vier vazio, reaproveitar o já salvo no banco.
    if not creds.refresh_token:
        raw_old = db.obter_google_tokens()
        if raw_old:
            try:
                old_data = json.loads(raw_old)
                old_rt = old_data.get("refresh_token")
                if old_rt:
                    creds.refresh_token = old_rt
                    _log("refresh_token preservado do DB")
                else:
                    _log("aviso: novo creds sem refresh_token e DB também sem refresh_token")
            except Exception:
                _log("aviso: falha ao ler old token para preservar refresh_token")
        else:
            _log("aviso: novo creds sem refresh_token e nenhum token antigo no DB")

    # Mesmo sem refresh_token ainda salvamos o token (access_token pode ser usado até expirar),
    # mas se tivermos refresh_token, garantimos persistência de longa duração.
    try:
        token_json = creds.to_json()
    except Exception as e:
        _log(f"to_json falhou: {type(e).__name__}")
        raise RuntimeError("Falha ao serializar credenciais.") from e

    # Validar que o JSON contém ao menos token
    try:
        data_check = json.loads(token_json)
        if not data_check.get("token"):
            raise ValueError("JSON sem access_token")
    except Exception as e:
        _log(f"token_json inválido: {type(e).__name__}")
        raise RuntimeError("Token JSON inválido.") from e

    # Persistir no PostgreSQL e CONFIRMAR salvamento
    try:
        saved = db.salvar_google_tokens(token_json)
    except Exception as e:
        _log(f"salvar_google_tokens exception: {type(e).__name__}")
        raise RuntimeError("Não foi possível salvar a autorização do Google no banco de dados.") from e
    if not saved:
        _log("salvar_google_tokens retornou False")
        raise RuntimeError("Não foi possível salvar a autorização do Google no banco de dados (persistência falhou).")

    # Cache em sessão para uso imediato (evita leitura do DB no mesmo rerun)
    try:
        import streamlit as st
        st.session_state["google_creds"] = creds
        # Limpar state após uso bem-sucedido (single-use)
        st.session_state.pop("google_oauth_state", None)
    except Exception:
        pass
    _log("exchange_code sucesso")
    return creds


def _save(creds: Credentials) -> bool:
    """Persiste credenciais após refresh. Preserva refresh_token se necessário. Retorna bool sucesso."""
    try:
        if not creds:
            return False
        # Se creds.token vazio, não salvar
        if not getattr(creds, "token", None):
            _log("_save: token vazio, ignorando")
            return False
        # Preservar refresh_token se creds.refresh_token estiver vazio mas DB tem um
        if not creds.refresh_token:
            raw_old = db.obter_google_tokens()
            if raw_old:
                try:
                    old_data = json.loads(raw_old)
                    old_rt = old_data.get("refresh_token")
                    if old_rt:
                        creds.refresh_token = old_rt
                        _log("_save: refresh_token preservado")
                except Exception:
                    pass
        token_json = creds.to_json()
        ok = db.salvar_google_tokens(token_json)
        if not ok:
            _log("_save: salvar_google_tokens retornou False")
            return False
        return True
    except Exception as e:
        _log(f"_save falhou: {type(e).__name__}")
        return False


def get_credentials() -> Optional[Credentials]:
    """Devolve credenciais válidas (da sessão ou do banco), com refresh automático."""
    # 1) Tentar cache em sessão
    try:
        import streamlit as st
        cached = st.session_state.get("google_creds")
        if isinstance(cached, Credentials):
            # Se não expirado, retorna direto
            if not getattr(cached, "expired", False):
                return cached
            # Se expirado e tem refresh_token, tenta refresh
            if cached.expired and cached.refresh_token:
                try:
                    cached.refresh(Request())
                    _save(cached)
                    return cached
                except Exception as e:
                    _log(f"refresh cache falhou: {type(e).__name__}")
                    # Fallback: tentar carregar do DB (pode ter token mais recente)
                    pass
            # Se expirado sem refresh_token, não é utilizável -> cair para DB
            elif cached.expired and not cached.refresh_token:
                _log("cached expirado sem refresh_token, buscando DB")
                pass
            else:
                return cached
    except Exception:
        pass

    raw = db.obter_google_tokens()
    if not raw:
        return None
    try:
        creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    except Exception as e:
        _log(f"from_authorized_user_info falhou: {type(e).__name__}")
        return None
    # Se credencial já é válida (não expirada), retorna
    if not getattr(creds, "expired", False) and creds.token:
        try:
            import streamlit as st
            st.session_state["google_creds"] = creds
        except Exception:
            pass
        return creds
    # Se expirada e tem refresh_token, tenta refresh
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
        except Exception as e:
            _log(f"refresh DB token falhou: {type(e).__name__}")
            return None
        try:
            import streamlit as st
            st.session_state["google_creds"] = creds
        except Exception:
            pass
        return creds
    # Se expirada sem refresh_token, não há como renovar -> creds inválida
    if creds.expired and not creds.refresh_token:
        _log("DB token expirado sem refresh_token - reautorização necessária")
        return None
    # Caso token ainda válido mesmo sem refresh (access_token recente), retorna
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
        st.session_state.pop("google_oauth_state", None)
        st.session_state.pop("google_last_code_hash", None)
    except Exception:
        pass
    try:
        ok = db.limpar_google_tokens()
        if not ok:
            _log("disconnect: limpar_google_tokens retornou False (talvez já vazio)")
    except Exception as e:
        _log(f"disconnect falhou: {type(e).__name__}")


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
    except Exception as e:
        _log(f"account_info falhou: {type(e).__name__}")
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
