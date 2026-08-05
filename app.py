import streamlit as st
import streamlit.components.v1 as components
import db
import os
import base64
import pathlib
import urllib.parse
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from enum import Enum
import pandas as pd
import plotly.express as px
import plotly.io as pio
from fpdf import FPDF

# Configurar página do Streamlit
st.set_page_config(
    page_title="Sistema de Gestão Clínica",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar esquema do banco (cria tabelas caso ainda não existam)
try:
    db.create_tables_if_needed()
except Exception:
    # Não interromper a interface: DatabaseManager.initialize_database mantém a mesma responsabilidade    
    pass


BASE_DIR = pathlib.Path(__file__).resolve().parent
DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M"
PRIMARY_ACCENT = "#4DA768"

# ── TEMAS PREMIUM (1 clique) ──
# Cada tema define: acento (sidebar/botões), fundo principal, fundo dos cards, texto dos cards
PREMIUM_THEMES = {
    "Verde Clínica": {"accent": "#1E7A46", "bg": "#73C883", "card_bg": "#ffffff", "card_text": "#ffffff"},
    "Azul Saúde":   {"accent": "#1D5FA8", "bg": "#5FA8D3", "card_bg": "#ffffff", "card_text": "#ffffff"},
    "Roxo Psicologia": {"accent": "#6C3FA8", "bg": "#9B7BD6", "card_bg": "#ffffff", "card_text": "#ffffff"},
    "Vinho":        {"accent": "#8A1F3D", "bg": "#C24A6B", "card_bg": "#ffffff", "card_text": "#ffffff"},
    "Petróleo":     {"accent": "#124A5B", "bg": "#2E7A8A", "card_bg": "#ffffff", "card_text": "#ffffff"},
    "Cinza Executive": {"accent": "#37474F", "bg": "#607D8B", "card_bg": "#ffffff", "card_text": "#ffffff"},
}

# ── BADGES DE STATUS (pills coloridas) ──
BADGE_STYLES = {
    "Agendado":   {"bg": "#E8F4FD", "fg": "#1D5FA8"},
    "Atendido":   {"bg": "#E7F9EE", "fg": "#1E7A46"},
    "Concluído":  {"bg": "#E7F9EE", "fg": "#1E7A46"},
    "Cancelado":  {"bg": "#FDE8EB", "fg": "#B03045"},
    "Pendente":   {"bg": "#FFF4E0", "fg": "#B4791F"},
    "Pago":       {"bg": "#E7F9EE", "fg": "#1E7A46"},
    "Atrasado":   {"bg": "#FDE8EB", "fg": "#B03045"},
    "Check-in":   {"bg": "#FFF4E0", "fg": "#B4791F"},
    "Em Atendimento": {"bg": "#E3F0FF", "fg": "#1D5FA8"},
    "Reagendado": {"bg": "#FFF9E0", "fg": "#8A6D1F"},
    "Presente":   {"bg": "#E7F9EE", "fg": "#1E7A46"},
    "Ausente":    {"bg": "#FDE8EB", "fg": "#B03045"},
    "Ativo":      {"bg": "#E7F9EE", "fg": "#1E7A46"},
    "Inativo":    {"bg": "#ECECF0", "fg": "#5A5A66"},
    "Online":     {"bg": "#E7F9EE", "fg": "#1E7A46"},
    "Offline":    {"bg": "#ECECF0", "fg": "#5A5A66"},
}

def status_badge(status):
    """Gera uma pill colorida para exibir status em tabelas e cards."""
    style = BADGE_STYLES.get(str(status), {"bg": "#ECECF0", "fg": "#5A5A66"})
    return (
        f"<span style='display:inline-block;padding:3px 12px;border-radius:999px;"
        f"font-size:0.72rem;font-weight:700;letter-spacing:0.4px;"
        f"background:{style['bg']};color:{style['fg']};"
        f"border:1px solid {style['bg']};'>{status}</span>"
    )

def empty_state(icon, title, message):
    """Empty state premium: ícone grande + texto acolhedor."""
    st.markdown(
        f"""
        <div style="text-align:center;padding:3.5rem 1.5rem;margin:0.5rem 0;
                    background:rgba(255,255,255,0.05);
                    border:1.5px dashed rgba(255,255,255,0.25);
                    border-radius:24px;">
            <div style="font-size:3.2rem;margin-bottom:0.8rem;filter:grayscale(0.2);">{icon}</div>
            <div style="font-size:1.15rem;font-weight:700;color:rgba(255,255,255,0.92);">{title}</div>
            <div style="font-size:0.85rem;color:rgba(255,255,255,0.6);margin-top:4px;max-width:460px;margin-left:auto;margin-right:auto;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

AGENDA_MEDICOS = ["Dr(a). Cláudia", "Dr(a). Ana", "Dr(a). Carlos", "Dr(a). Beatriz"]

def _parse_data(valor):
    """Converte valor de data (str 'DD/MM/YYYY', 'YYYY-MM-DD', date, datetime) para date."""
    try:
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date):
            return valor
        texto = str(valor).strip()
        if "-" in texto:
            return pd.to_datetime(texto, errors="coerce").date()
        return pd.to_datetime(texto, dayfirst=True, errors="coerce").date()
    except Exception:
        return date(1900, 1, 1)

class ModalidadeAtendimento(Enum):
    ADMISSIONAL = "Admissional"
    DEMISSIONAL = "Demissional"
    PERIODICO = "Periódico"
    MUDANCA_FUNCAO = "Mudança de função"

class Security:
    @staticmethod
    def sanitize_input(text):
        if not text:
            return ""
        return str(text).strip()
    @staticmethod
    def generate_safe_filename(filename):
        import re
        safe = re.sub(r'[^\w\-_\.]', '_', str(filename))
        return safe[:100]
    @staticmethod
    def validate_file_upload(filename, size_bytes, max_size_mb=50):
        if not filename:
            return False, "Nome do arquivo inválido"
        if not filename.lower().endswith('.pdf'):
            return False, "Apenas arquivos PDF são permitidos"
        if size_bytes > max_size_mb * 1024 * 1024:
            return False, f"Arquivo muito grande. Máximo: {max_size_mb}MB"
        return True, "OK"
    @staticmethod
    def is_valid_pdf(file_bytes):
        """Verifica se o conteúdo do arquivo começa com o cabeçalho PDF (Magic Bytes)."""
        if not file_bytes or len(file_bytes) < 4:
            return False
        return file_bytes[:4] == b'%PDF'
    @staticmethod
    def log_error(action, error):
        """Log técnico detalhado apenas para o servidor."""
        try:
            log_dir = BASE_DIR / "logs"
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "error.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} - {action}: {str(error)}\n")
        except Exception:
            pass
    @staticmethod
    def log_access(action, details):
        try:
            log_dir = BASE_DIR / "logs"
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "access.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} - {action}: {details}\n")
        except Exception:
            pass

security = Security()

class DatabaseManager:
    @staticmethod
    def initialize_database(force=False):
        try:
            # Cria tabelas no Postgres conforme metadata do db.py
            db.ensure_schema(force=force)
            return True
        except Exception as e:
            Security.log_error("DB_INIT", e)
            st.error("Erro interno ao inicializar o sistema. Verifique os logs.")
            return False

    @staticmethod
    @st.cache_data(show_spinner="Carregando atendimentos...", ttl=600)
    def get_all_appointments():
        try:
            return db.listar_atendimentos()
        except Exception as e:
            Security.log_error("DB_LIST", e)
            st.error("Erro interno ao carregar dados.")
            return []

    @staticmethod
    def add_appointment(appointment_data):
        try:
            res = db.inserir_atendimento(
                appointment_data.empresa,
                appointment_data.nome,
                appointment_data.modalidade,
                appointment_data.data,
                appointment_data.hora,
                appointment_data.laudo_pdf,
                appointment_data.avaliacao_pdf,
                getattr(appointment_data, 'observacoes', '')
            )
            if res:
                st.cache_data.clear() # Limpa cache para refletir novo registro
            return res
        except Exception as e:
            Security.log_error("DB_ADD", e)
            st.error("Erro ao salvar o atendimento. Verifique os dados e tente novamente.")
            return False

    @staticmethod
    def delete_appointment(appointment_id):
        try:
            res = db.excluir_atendimento(appointment_id)
            if res:
                st.cache_data.clear() # Limpa cache após exclusão
            return res
        except Exception as e:
            Security.log_error("DB_DELETE", e)
            st.error("Não foi possível excluir o registro.")
            return False

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=300)
    def get_statistics():
        try:
            rows = db.listar_atendimentos()
            total = len(rows)
            modalidades = {}
            for r in rows:
                mod = r[3] if len(r) > 3 else None
                if mod:
                    modalidades[mod] = modalidades.get(mod, 0) + 1
            return {"total_atendimentos": total, "modalidades": modalidades}
        except Exception:
            return {"total_atendimentos": 0, "modalidades": {}}

def display_cards(cards):
    cols = st.columns(len(cards))
    accent = st.session_state.get('accent_color', '#4DA768')
    txt = st.session_state.get('card_text_color', '#ffffff')
    card_bg = st.session_state.get('card_bg_hex', '#ffffff')
    bg_css = "rgba(255,255,255,0.14)" if card_bg.lower() == "#ffffff" else card_bg

    for i, card in enumerate(cards):
        with cols[i]:
            icon  = card.get('icon', '📋')
            title = card.get('title', '')
            value = card.get('value', 0)
            delta = card.get('delta', None)

            delta_html = ""
            if delta is not None:
                sign  = "▲" if str(delta).startswith('+') or (isinstance(delta, (int,float)) and delta > 0) else "▼"
                color = "#4ade80" if sign == "▲" else "#f87171"
                delta_html = f"<div style='font-size:0.72rem;font-weight:600;color:{color};margin-top:2px;'>{sign} {delta}</div>"

            st.markdown(
                f"""
                <div style="
                    background: {bg_css};
                    backdrop-filter: blur(20px);
                    -webkit-backdrop-filter: blur(20px);
                    border: 1px solid rgba(255,255,255,0.18);
                    border-radius: 20px;
                    padding: 22px 20px 18px 20px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.07),
                                inset 0 1px 0 rgba(255,255,255,0.18);
                    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
                    cursor: default;
                    margin-bottom: 4px;
                ">
                    <div style="font-size:1.6rem;margin-bottom:8px;line-height:1;">{icon}</div>
                    <div style="
                        font-size:0.7rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:1.2px;
                        color:{txt};opacity:0.75;margin-bottom:6px;
                    ">{title}</div>
                    <div style="
                        font-size:2rem;font-weight:800;
                        color:{txt};letter-spacing:-1px;line-height:1;
                    ">{value}</div>
                    {delta_html}
                </div>
                """,
                unsafe_allow_html=True
            )


def render_page_header(title, subtitle, inverse=False):
    st.markdown(
        f"""
        <div style='margin-bottom:0.5rem;'>
            <p style='font-size:0.75rem;font-weight:700;letter-spacing:2px;
                      text-transform:uppercase;color:rgba(255,255,255,0.6);
                      margin:0 0 4px 0;'></p>
            <h1 style='margin:0;padding:0;'>{title}</h1>
            <p style='font-size:0.88rem;color:rgba(255,255,255,0.7);
                      margin:4px 0 0 0;font-weight:400;'>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.divider()

def apply_custom_css(dark_mode=False, primary_accent="#4DA768", card_text_color="#ffffff", main_bg_color="#73C883", card_bg_color="rgba(255, 255, 255, 0.15)"):
    # Paleta Dinâmica
    bg_main = "#121212" if dark_mode else main_bg_color
    bg_sidebar = "#1a1a1a" if dark_mode else primary_accent
    card_bg = "rgba(255, 255, 255, 0.05)" if dark_mode else card_bg_color
    text_main = "#ffffff"
    
    st.markdown(
        f'''<style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        
        /* ── BASE & TYPOGRAPHY PREMIUM ── */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
        [data-testid="stMainViewContainer"] {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: {bg_main} !important;
            -webkit-font-smoothing: antialiased !important;
            -moz-osx-font-smoothing: grayscale !important;
            text-rendering: optimizeLegibility !important;
        }}
        * {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}

        /* ── CUSTOM SCROLLBAR PREMIUM ── */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: rgba(0,0,0,0.02); 
            border-radius: 12px;
        }}
        ::-webkit-scrollbar-thumb {{
            background: rgba(255,255,255,0.15); 
            border-radius: 12px;
            border: 2px solid transparent;
            background-clip: padding-box;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255,255,255,0.25);
            border: 2px solid transparent;
            background-clip: padding-box;
        }}

        /* ── CONTAINER ── */
        .main .block-container {{
            padding-top: 2rem;
            max-width: 1280px;
        }}

        /* ── SIDEBAR PREMIUM ── */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {bg_sidebar} 0%, {bg_sidebar}E6 100%) !important;
            box-shadow: 8px 0 32px rgba(0,0,0,0.18);
            border-right: 1px solid rgba(255,255,255,0.08);
            backdrop-filter: blur(20px);
        }}
        [data-testid="stSidebar"] * {{ color: #ffffff !important; }}
        [data-testid="stSidebar"] .stRadio label {{
            font-weight: 500 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.3px !important;
            padding: 4px 0 !important;
            transition: opacity 0.2s ease;
        }}
        [data-testid="stSidebar"] .stRadio label:hover {{
            opacity: 0.8;
        }}
        [data-testid="stSidebar"] [data-testid="stTextInput"] input {{
            background: rgba(255,255,255,0.1) !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-radius: 12px !important;
            color: #ffffff !important;
            font-size: 0.9rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }}
        [data-testid="stSidebar"] [data-testid="stTextInput"] input:focus {{
            border-color: rgba(255,255,255,0.4) !important;
            box-shadow: 0 0 0 3px rgba(255,255,255,0.1) !important;
            background: rgba(255,255,255,0.15) !important;
        }}

        /* ── TITULOS PREMIUM ── */
        h1 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 800 !important;
            font-size: 2.2rem !important;
            letter-spacing: -1px !important;
            line-height: 1.2 !important;
            background: linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.6) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem !important;
        }}
        h2, h3 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 700 !important;
            color: #ffffff !important;
            letter-spacing: -0.5px;
        }}
        h4, h5, h6 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 600 !important;
            color: rgba(255,255,255,0.85) !important;
        }}
        p, span, div, label {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            line-height: 1.6;
        }}

        /* ── CARDS DE MÉTRICAS (GLASSMORPHISM PRO) ── */
        [data-testid="stMetric"] {{
            background: {card_bg} !important;
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 24px !important;
            padding: 24px !important;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.2) !important;
            transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-6px) scale(1.02);
            border-color: rgba(255,255,255,0.3);
            box-shadow: 0 20px 48px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.3) !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: {card_text_color} !important;
            font-weight: 600 !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            opacity: 0.85;
            margin-bottom: 8px;
        }}
        [data-testid="stMetricValue"] {{
            color: {card_text_color} !important;
            font-weight: 800 !important;
            font-size: 2.2rem !important;
            letter-spacing: -1.2px;
            text-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        [data-testid="stMetricDelta"] {{ color: {card_text_color} !important; }}

        /* ── TABELAS ELEGANTES ── */
        .stDataFrame, [data-testid="stTable"] {{
            background: {"#1e1e1e" if dark_mode else "white"};
            border-radius: 20px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.05);
            box-shadow: 0 10px 40px rgba(0,0,0,0.08);
            transition: box-shadow 0.3s ease;
        }}
        .stDataFrame:hover, [data-testid="stTable"]:hover {{
            box-shadow: 0 15px 50px rgba(0,0,0,0.12);
        }}
        [data-testid="stSidebar"] {{
            z-index: 100 !important;
        }}

        /* ── INPUTS E FORMULÁRIOS ── */
        .stTextInput input, .stSelectbox select, .stTextArea textarea, .stDateInput input, .stTimeInput input {{
            border-radius: 14px !important;
            border: 1.5px solid rgba(255,255,255,0.15) !important;
            padding: 12px 18px !important;
            background: rgba(255,255,255,{0.05 if dark_mode else 0.95}) !important;
            color: {"white" if dark_mode else "#1a1a1a"} !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
        }}
        .stTextInput input:hover, .stSelectbox select:hover, .stTextArea textarea:hover {{
            border-color: rgba(255,255,255,0.3) !important;
            background: rgba(255,255,255,{0.08 if dark_mode else 1}) !important;
        }}
        .stTextInput input:focus, .stSelectbox select:focus, .stTextArea textarea:focus, .stDateInput input:focus, .stTimeInput input:focus {{
            border-color: {primary_accent} !important;
            box-shadow: 0 0 0 4px {primary_accent}25, inset 0 2px 4px rgba(0,0,0,0.02) !important;
            background: rgba(255,255,255,{0.1 if dark_mode else 1}) !important;
            outline: none !important;
        }}

        /* ── STATUS BADGES ── */
        .status-badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 14px;
            border-radius: 50px;
            font-size: 0.72rem;
            font-weight: 700;
            color: white !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }}
        .status-agendado {{ background: linear-gradient(135deg,#3498db,#2980b9); }}
        .status-atendido {{ background: linear-gradient(135deg,#2ecc71,#27ae60); }}
        .status-concluido {{ background: linear-gradient(135deg,#1e8449,#145a32); }}
        .status-cancelado {{ background: linear-gradient(135deg,#e74c3c,#c0392b); }}

        /* ── BOTÕES MAGNÉTICOS ── */
        .stButton > button {{
            width: 100%;
            border-radius: 14px !important;
            background: linear-gradient(135deg, {primary_accent} 0%, {primary_accent}D9 100%) !important;
            color: white !important;
            font-weight: 700 !important;
            font-size: 0.92rem !important;
            letter-spacing: 0.4px !important;
            padding: 12px 24px !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            border-bottom: 1px solid rgba(0,0,0,0.1) !important;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.2) !important;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }}
        .stButton > button:hover {{
            transform: translateY(-3px) !important;
            box-shadow: 0 12px 28px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.3) !important;
            border-color: rgba(255,255,255,0.4) !important;
            filter: brightness(1.05);
        }}
        .stButton > button:active {{ 
            transform: translateY(1px) !important; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1), inset 0 2px 4px rgba(0,0,0,0.1) !important;
        }}

        /* ── EXPANDER (ACORDEÃO) ── */
        .stExpander {{
            border: 1px solid rgba(255,255,255,0.1) !important;
            background: linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%) !important;
            border-radius: 20px !important;
            backdrop-filter: blur(12px);
            margin-bottom: 1.2rem !important;
            box-shadow: 0 8px 32px rgba(0,0,0,0.05);
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }}
        .stExpander:hover {{
            border-color: rgba(255,255,255,0.2) !important;
            box-shadow: 0 12px 40px rgba(0,0,0,0.08);
        }}
        .stExpander > div > div > div > div > p {{
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.2px;
        }}
        .stExpander * {{ color: white !important; }}

        /* ── DIVIDER ── */
        hr {{
            border-color: rgba(255,255,255,0.1) !important;
            margin: 1.5rem 0 !important;
            background-image: linear-gradient(to right, transparent, rgba(255,255,255,0.2), transparent) !important;
            border: none;
            height: 1px;
        }}

        /* ── ALERTS / INFO ── */
        [data-testid="stAlert"] {{
            border-radius: 16px !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.06);
        }}

        /* ── LOGIN FORM ── */
        [data-testid="stForm"] {{
            background: linear-gradient(145deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%) !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-top: 1px solid rgba(255,255,255,0.25) !important;
            border-radius: 28px !important;
            padding: 3rem !important;
            backdrop-filter: blur(32px) !important;
            -webkit-backdrop-filter: blur(32px) !important;
            box-shadow: 0 24px 64px rgba(0,0,0,0.2) !important;
        }}
        [data-testid="stFormSubmitButton"] button {{
            background: linear-gradient(135deg, {primary_accent} 0%, {primary_accent}CC 100%) !important;
            color: white !important;
            border-radius: 16px !important;
            font-size: 1.05rem !important;
            font-weight: 800 !important;
            padding: 0.8rem 2.5rem !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            box-shadow: 0 8px 28px rgba(77,167,104,0.4), inset 0 1px 0 rgba(255,255,255,0.3) !important;
            letter-spacing: 0.5px !important;
            transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        }}
        [data-testid="stFormSubmitButton"] button:hover {{
            transform: translateY(-4px) !important;
            box-shadow: 0 14px 36px rgba(77,167,104,0.5), inset 0 1px 0 rgba(255,255,255,0.4) !important;
            filter: brightness(1.1);
        }}

        /* ── CAPTION / SMALL TEXT ── */
        .stCaption, [data-testid="stCaptionContainer"] {{
            font-size: 0.8rem !important;
            opacity: 0.7;
            letter-spacing: 0.2px;
            font-weight: 500;
        }}

        /* ── SIDEBAR FILE UPLOADER → BOTÃO COMPACTO ── */
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {{
            display: none !important;
        }}
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
            min-height: unset !important;
            box-shadow: none !important;
        }}
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] > button {{
            width: 100% !important;
            background: rgba(255,255,255,0.08) !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-radius: 12px !important;
            color: rgba(255,255,255,0.9) !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            padding: 8px 14px !important;
            letter-spacing: 0.4px !important;
            cursor: pointer !important;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
            margin: 0 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] > button:hover {{
            background: rgba(255,255,255,0.15) !important;
            border-color: rgba(255,255,255,0.3) !important;
            color: #fff !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        [data-testid="stSidebar"] [data-testid="stFileUploader"] small {{
            display: none !important;
        }}

        </style>''', unsafe_allow_html=True)

def apply_plotly_theme(dark_mode=False):
    pio.templates.default = "plotly_dark" if dark_mode else "plotly_white"

def save_uploaded_pdf(uploaded_file):
    """Salva PDF no banco (BYTEA) e retorna um marcador 'db:<id>' ou None se falhar.
    Valida se o conteúdo é realmente um PDF antes de salvar.
    """
    if uploaded_file is None:
        return None
    try:
        file_bytes = uploaded_file.getvalue()
        # Validação Sênior: Verifica se o arquivo é REALMENTE um PDF pelo conteúdo
        if not Security.is_valid_pdf(file_bytes):
            st.error(f"O arquivo '{uploaded_file.name}' não é um PDF válido.")
            return None
            
        safe_name = security.generate_safe_filename(uploaded_file.name)
        file_id = db.salvar_arquivo(safe_name, file_bytes, content_type="application/pdf")
        if file_id:
            return f"db:{file_id}"
        # fallback improvável; manter compat com disco se algo falhar
        uploads_dir = BASE_DIR / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        file_path = uploads_dir / safe_name
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return str(file_path)
    except Exception as e:
        Security.log_error("PDF_SAVE", e)
        st.error("Erro interno ao salvar o arquivo.")
        return None

def verificar_conexao():
    return db.verificar_conexao()

def generate_pdf_report(df):
    from fpdf.enums import XPos, YPos

    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 16)
            self.cell(0, 10, 'Relatório de Atendimentos', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(5)
            self.set_font('Helvetica', 'I', 10)
            self.cell(0, 10, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', align='C')

    pdf = PDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)

    # Columns to export
    cols = ["Nº", "Empresa", "Nome", "Modalidade", "Data", "Hora", "Status"]

    # Column widths adjusted for A4 Landscape (~277mm usable width)
    # Total width: 12 + 68 + 68 + 42 + 25 + 22 + 40 = 277
    widths = [12, 68, 68, 42, 25, 22, 40]

    # Header
    pdf.set_font("Helvetica", 'B', 10)
    for i, col in enumerate(cols):
        pdf.cell(widths[i], 10, col, 1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    # Rows — font size 8 for data to ensure text fits inside fixed-width columns
    pdf.set_font("Helvetica", size=8)

    def safe_cell_text(text):
        try:
            return str(text).encode('latin-1', 'replace').decode('latin-1')
        except Exception:
            return str(text)

    for index, row in df.iterrows():
        try:
            num_txt = safe_cell_text(str(index + 1))
            empresa_txt = safe_cell_text(str(row['Empresa']).strip()[:28])
            nome_txt = safe_cell_text(str(row['Nome']).strip()[:28])
            modal_txt = safe_cell_text(str(row['Modalidade']).strip()[:20])
            data_txt = safe_cell_text(str(row['Data']).strip())
            hora_txt = safe_cell_text(str(row['Hora']).strip())
            status_txt = safe_cell_text(str(row['Status']).strip())

            pdf.cell(widths[0], 8, num_txt, 1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(widths[1], 8, empresa_txt, 1, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(widths[2], 8, nome_txt, 1, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(widths[3], 8, modal_txt, 1, align='L', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(widths[4], 8, data_txt, 1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(widths[5], 8, hora_txt, 1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(widths[6], 8, status_txt, 1, align='C', new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln()

        except Exception:
            pass

    return bytes(pdf.output())

class AtendimentoData:
    def __init__(self, empresa, nome, modalidade, data, hora, laudo_pdf="", avaliacao_pdf="", observacoes=""):
        self.empresa = empresa
        self.nome = nome
        self.modalidade = modalidade
        self.data = data
        self.hora = hora
        self.laudo_pdf = laudo_pdf
        self.avaliacao_pdf = avaliacao_pdf
        self.observacoes = observacoes

class DashboardPage:
    @staticmethod
    def render() -> None:
        conn_ok = verificar_conexao()
        accent = st.session_state.get('accent_color', PRIMARY_ACCENT)
        is_dark = st.session_state.get('premium_dark_mode', False)
        hora = datetime.now(ZoneInfo("America/Manaus")).hour
        saudacao = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
        usuario = st.session_state.get('user_name', 'Admin')
        nome_exibido = str(usuario).split('@')[0].replace('.', ' ').title() if usuario not in ('Admin', 'admin', 'guest') else "Profissional"
        agora_manaus = datetime.now(ZoneInfo("America/Manaus"))
        dia_semana = {"Monday": "Segunda-feira", "Tuesday": "Terça-feira", "Wednesday": "Quarta-feira",
                      "Thursday": "Quinta-feira", "Friday": "Sexta-feira", "Saturday": "Sábado", "Sunday": "Domingo"}.get(agora_manaus.strftime("%A"), "")
        mes_pt = {"January": "janeiro", "February": "fevereiro", "March": "março", "April": "abril",
                  "May": "maio", "June": "junho", "July": "julho", "August": "agosto",
                  "September": "setembro", "October": "outubro", "November": "novembro", "December": "dezembro"}.get(agora_manaus.strftime("%B"), "")
        data_pt = f"{dia_semana}, {agora_manaus.day} de {mes_pt} de {agora_manaus.year}"
        hora_pt = agora_manaus.strftime("%H:%M")
        status_html = status_badge("Online" if conn_ok else "Offline")
        status_label = "Postgres conectado" if conn_ok else "Banco indisponível"
        overlay = "rgba(0,0,0,0.28)" if is_dark else "rgba(255,255,255,0.10)"
        components.html(
            f"""
            <html>
            <head>
            <style>
              html, body {{ margin:0; padding:0; height:100%; overflow:hidden; background:transparent; }}
              .box {{
                  height:100%; box-sizing:border-box;
                  background: linear-gradient(120deg, {accent} 0%, {accent}CC 55%, {accent}88 100%);
                  border: 1px solid rgba(255,255,255,0.18);
                  border-radius: 24px;
                  padding: 1.3rem 2.2rem;
                  box-shadow: 0 12px 40px rgba(0,0,0,0.16), inset 0 1px 0 rgba(255,255,255,0.25);
                  position: relative; overflow: hidden;
                  display:flex; align-items:center;
              }}
              .steth {{ position:absolute; top:-40px; right:-30px; font-size:8rem; opacity:0.10; transform:rotate(-12deg); }}
              .content {{ position:relative; width:100%; display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px; }}
              .kicker {{ font-size:0.72rem; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:rgba(255,255,255,0.75); margin:0 0 6px 0; }}
              h1 {{ margin:0; font-size:2.1rem; font-weight:800; color:#fff; letter-spacing:-1px; }}
              .data {{ font-size:0.9rem; color:rgba(255,255,255,0.85); margin:6px 0 0 0; font-weight:500; }}
              .direita {{ text-align:right; }}
              .status-txt {{ font-size:0.75rem; color:rgba(255,255,255,0.75); margin:6px 0 0 0; }}
            </style>
            </head>
            <body>
              <div class="box">
                <div class="steth">🩺</div>
                <div class="content">
                  <div>
                    <p class="kicker">Dashboard Executivo</p>
                    <h1>{saudacao}, {nome_exibido} 👋</h1>
                    <p class="data">📅 {data_pt} &nbsp;•&nbsp; 🕐 <span id="relogio-manaus" style="font-variant-numeric:tabular-nums;">{hora_pt}</span></p>
                  </div>
                  <div class="direita">
                    <div>{status_html}</div>
                    <p class="status-txt">{status_label}</p>
                  </div>
                </div>
              </div>
              <script>
              (function() {{
                function formatar(tz) {{
                  try {{
                    return new Intl.DateTimeFormat('pt-BR', {{ timeZone: tz, hour: '2-digit', minute: '2-digit' }}).format(new Date());
                  }} catch (e) {{ return ''; }}
                }}
                function atualizar() {{
                  var el = document.getElementById('relogio-manaus');
                  if (el) el.textContent = formatar('America/Manaus');
                }}
                atualizar();
                setInterval(atualizar, 1000);
              }})();
              </script>
            </body>
            </html>
            """,
            height=190,
        )
        st.caption("PostgreSQL | IA Assistente | Gestão Clínica")
        try:
            stats = DatabaseManager.get_statistics()
            appointments = DatabaseManager.get_all_appointments()
            total_appointments = len(appointments)
            empresas_unicas = set()
            laudos_enviados = 0
            avaliacoes_enviadas = 0
            for apt in appointments:
                if len(apt) > 1:
                    empresas_unicas.add(str(apt[1]))
                if len(apt) > 6 and apt[6]:
                    laudos_enviados += 1
                if len(apt) > 7 and apt[7]:
                    avaliacoes_enviadas += 1
            total_empresas = len(empresas_unicas)
        except Exception as e:
            Security.log_error("DASHBOARD_STATS", e)
            st.error("Erro interno ao carregar estatísticas do painel.")
            total_appointments = total_empresas = laudos_enviados = avaliacoes_enviadas = 0
        accent = st.session_state.get('accent_color', PRIMARY_ACCENT)
        cards = [
            {"icon": "📋", "title": "Atendimentos", "value": total_appointments, "acc": accent},
            {"icon": "🏢", "title": "Empresas", "value": total_empresas, "acc": accent},
            {"icon": "📄", "title": "Relatórios", "value": laudos_enviados, "acc": accent},
            {"icon": "📝", "title": "Avaliações", "value": avaliacoes_enviadas, "acc": accent},
        ]
        display_cards(cards)
        
        if total_appointments > 0:
            st.markdown("---")
            st.markdown("### 🧠 Dicas da IA Assistente")
            with st.spinner("Gerando insights de negócio..."):
                import json
                stats_resumo = {
                    "total_atendimentos": total_appointments,
                    "total_empresas": total_empresas,
                    "laudos_gerados": laudos_enviados,
                    "modalidades": stats.get("modalidades", {})
                }
                from ai_manager import AIManager
                dicas = AIManager.generate_dashboard_insights(json.dumps(stats_resumo))
                st.info(dicas)
        else:
            empty_state("✨", "Painel vazio", "Cadastre seu primeiro atendimento para ver a mágica acontecer.")
        
        if total_appointments > 0:
            st.markdown("### 📊 Distribuição por Modalidade & Empresa")
            st.caption("Use o calendário para escolher o período e ver quantos atendimentos cada empresa teve.")

            # ── Mini calendário (período) ──
            datas_validas = []
            for a in appointments:
                dt = _parse_data(a[4]) if len(a) > 4 and a[4] else None
                if dt and dt.year > 1900:
                    datas_validas.append(dt)
            data_min = min(datas_validas) if datas_validas else date.today()
            data_max = max(datas_validas) if datas_validas else date.today()
            if 'dash_periodo' not in st.session_state:
                st.session_state['dash_periodo'] = (data_min, data_max)
            calendario = st.date_input(
                "Período",
                value=st.session_state['dash_periodo'],
                min_value=data_min,
                max_value=data_max,
                key="dash_calendario",
            )
            if isinstance(calendario, tuple) and len(calendario) == 2:
                inicio, fim = calendario
            else:
                inicio = fim = calendario

            contagem_empresas = {}
            for a in appointments:
                if len(a) <= 1 or not a[1]:
                    continue
                dt = _parse_data(a[4]) if len(a) > 4 and a[4] else None
                if dt and dt.year > 1900 and inicio <= dt <= fim:
                    contagem_empresas[str(a[1])] = contagem_empresas.get(str(a[1]), 0) + 1

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                if stats.get("modalidades"):
                    st.markdown("#### 🏥 Distribuição por Modalidade")
                    vals = list(stats["modalidades"].values())
                    labels = list(stats["modalidades"].keys())
                    fig = px.pie(values=vals, names=labels, title="Distribuição por Modalidade",
                                 color_discrete_sequence=['#1E5631', '#2D7D32', '#388E3C', '#43A047', '#4CAF50'])
                    fig.update_traces(textposition="inside", textinfo="percent+label", marker=dict(line=dict(color='rgba(255,255,255,0.2)', width=2)))
                    fig.update_layout(legend_title_text="Modalidade", height=400, margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#FFFFFF" if is_dark else "#1E293B"))
                    st.plotly_chart(fig, use_container_width=True)
            with col_p2:
                if contagem_empresas:
                    st.markdown("#### 🏢 Atendimentos por Empresa")
                    labels = list(contagem_empresas.keys())
                    vals = list(contagem_empresas.values())
                    fig = px.pie(values=vals, names=labels, title="Atendimentos por Empresa",
                                 color_discrete_sequence=['#1E5631', '#2D7D32', '#388E3C', '#43A047', '#4CAF50', '#66BB6A', '#81C784', '#A5D6A7'])
                    fig.update_traces(textposition="inside", textinfo="percent+label", marker=dict(line=dict(color='rgba(255,255,255,0.2)', width=2)))
                    fig.update_layout(legend_title_text="Empresa", height=400, margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#FFFFFF" if is_dark else "#1E293B"))
                    st.plotly_chart(fig, use_container_width=True)

            if contagem_empresas:
                st.markdown("#### 📊 Resumo por Empresa")
                resumo = pd.DataFrame({
                    "Empresa": list(contagem_empresas.keys()),
                    "Atendimentos": list(contagem_empresas.values()),
                }).sort_values("Atendimentos", ascending=False).reset_index(drop=True)
                st.dataframe(resumo, use_container_width=True, hide_index=True)
            else:
                empty_state("📅", "Nada por aqui", "Não há atendimentos no período selecionado. Ajuste o calendário acima.")

class AppointmentsPage:
    @staticmethod
    def render(filters):
        render_page_header("📅 Atendimentos", "Gerenciamento de Consultas e Procedimentos")

        # Filtros rápidos (busca, modalidade, status, período)
        with st.expander("🔎 Filtros", expanded=True):
            colf1, colf2, colf3, colf4 = st.columns([2,2,2,2])
            with colf1:
                q = st.text_input("Pesquisar (Nome/Empresa)", key="flt_q").strip()
            with colf2:
                mod_opts = ["(Todas)"] + [m.value for m in ModalidadeAtendimento]
                mod_sel = st.selectbox("Modalidade", mod_opts, key="flt_mod")
            with colf3:
                status_sel = st.selectbox("Status", ["(Todos)", "Agendado", "Atendido", "Concluído", "Cancelado"], key="flt_status")
            with colf4:
                d1 = st.date_input("Data inicial", value=None, key="flt_dini", min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
                d2 = st.date_input("Data final", value=None, key="flt_dfim", min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))

            filters["q"] = q
            filters["modalidade_filter"] = None if mod_sel == "(Todas)" else mod_sel
            filters["status_filter"] = None if status_sel == "(Todos)" else status_sel
            filters["date_start"] = d1
            filters["date_end"] = d2
        with st.expander("➕ Cadastrar Novo Atendimento", expanded=False):
            # ─── Campos do formulário (widgets simples, sem st.form) ───
            col1, col2 = st.columns(2)
            with col1:
                empresa = st.text_input("🏢 Empresa/Organização", max_chars=100, key="new_apt_empresa").strip()
                modalidade = st.selectbox("🧾 Modalidade", [m.value for m in ModalidadeAtendimento], key="new_apt_modal")
                data_sel = st.date_input("📅 Data", value=date.today(), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key="new_apt_data")
            with col2:
                nome = st.text_input("👤 Nome do Paciente", max_chars=100, key="new_apt_nome").strip()
                hora_sel = st.time_input("⏰ Horário", key="new_apt_hora")

            # ─── Anexos PDF (fora de qualquer form para preservar o estado do arquivo) ───
            st.markdown("#### 📎 Anexos (opcional)")
            c1a, c2a = st.columns(2)
            with c1a:
                up_laudo = st.file_uploader("📄 Laudo PDF", type=["pdf"], key="up_laudo_new")
                if up_laudo:
                    size_mb = len(up_laudo.getvalue()) / (1024 * 1024)
                    st.caption(f"Selecionado: {up_laudo.name} — {size_mb:.2f} MB")
                    if st.button("🪄 Analisar Laudo com IA", key="ai_btn_laudo"):
                        with st.spinner("IA analisando laudo..."):
                            from ai_manager import AIManager
                            ai_res = AIManager.analyze_pdf_content(up_laudo.getvalue(), up_laudo.name)
                            st.session_state['temp_ai_obs'] = ai_res
            with c2a:
                up_avaliacao = st.file_uploader("📝 Avaliação PDF", type=["pdf"], key="up_aval_new")
                if up_avaliacao:
                    size_mb = len(up_avaliacao.getvalue()) / (1024 * 1024)
                    st.caption(f"Selecionado: {up_avaliacao.name} — {size_mb:.2f} MB")
                    if st.button("🪄 Analisar Avaliação com IA", key="ai_btn_aval"):
                        with st.spinner("IA analisando avaliação..."):
                            from ai_manager import AIManager
                            ai_res = AIManager.analyze_pdf_content(up_avaliacao.getvalue(), up_avaliacao.name)
                            st.session_state['temp_ai_obs'] = ai_res

            initial_obs = st.session_state.get('temp_ai_obs', '')
            observacoes = st.text_area("🗒️ Observações", value=initial_obs, placeholder="Observações adicionais ou notas da IA...", key="new_apt_obs")

            c_act1, c_act2 = st.columns([1, 1])
            with c_act1:
                submitted = st.button("💾 Salvar", type="primary", key="new_apt_salvar", use_container_width=True)
            with c_act2:
                if st.button("🧹 Limpar Notas IA", key="new_apt_limpar", use_container_width=True):
                    st.session_state['temp_ai_obs'] = ''
                    st.rerun()

            if submitted:
                if not empresa or not nome:
                    st.error("Preencha os campos obrigatórios (Empresa e Nome).")
                else:
                    from ai_manager import AIManager

                    is_valid = True
                    if up_laudo:
                        valid_laudo, msg_laudo = AIManager.validate_clinical_pdf(up_laudo.getvalue())
                        if not valid_laudo:
                            st.error(f"❌ Documento bloqueado (Laudo): {msg_laudo}")
                            is_valid = False

                    if up_avaliacao:
                        valid_aval, msg_aval = AIManager.validate_clinical_pdf(up_avaliacao.getvalue())
                        if not valid_aval:
                            st.error(f"❌ Documento bloqueado (Avaliação): {msg_aval}")
                            is_valid = False

                    if is_valid:
                        laudo_path = save_uploaded_pdf(up_laudo) if up_laudo else None
                        avaliacao_path = save_uploaded_pdf(up_avaliacao) if up_avaliacao else None
                        novo_atendimento = AtendimentoData(
                            empresa=security.sanitize_input(empresa),
                            nome=security.sanitize_input(nome),
                            modalidade=modalidade,
                            data=data_sel,
                            hora=hora_sel,
                            laudo_pdf=laudo_path,
                            avaliacao_pdf=avaliacao_path,
                            observacoes=security.sanitize_input(observacoes)
                        )
                        if DatabaseManager.add_appointment(novo_atendimento):
                            security.log_access("ADD_APPOINTMENT", f"{nome} - {empresa}")
                            st.toast("Atendimento cadastrado com sucesso!", icon="✅")
                            if 'temp_ai_obs' in st.session_state:
                                del st.session_state['temp_ai_obs']
                            st.rerun()
                        else:
                            st.error("Erro ao cadastrar atendimento.")

        with st.expander("✏️ Editar Atendimento", expanded=False):
            st.caption("Busque um atendimento pelo ID ou nome/empresa para editar seus dados.")
            col_search1, col_search2 = st.columns([2, 1])
            with col_search1:
                busca_editor = st.text_input(
                    "🔎 Buscar por Nome, Empresa ou ID",
                    placeholder="Ex: João Silva  ou  32",
                    key="editor_busca"
                ).strip()
            with col_search2:
                st.markdown("&nbsp;")  # espaço vertical
                buscar_btn = st.button("Buscar", key="editor_buscar_btn", type="primary", use_container_width=True)

            if busca_editor:
                all_apts = DatabaseManager.get_all_appointments()
                # Filtrar por ID exato ou por nome/empresa
                resultados = []
                for r in all_apts:
                    if busca_editor.isdigit() and str(r[0]) == busca_editor:
                        resultados.append(r)
                    elif not busca_editor.isdigit() and (
                        busca_editor.lower() in str(r[1]).lower() or
                        busca_editor.lower() in str(r[2]).lower()
                    ):
                        resultados.append(r)

                if not resultados:
                    empty_state("🔎", "Nenhum resultado", "Não encontramos atendimentos para essa busca. Tente ajustar os filtros.")
                else:
                    st.success(f"{len(resultados)} atendimento(s) encontrado(s).")
                    for r_edit in resultados:
                        aid_e = r_edit[0]
                        lbl = f"#{aid_e} — {r_edit[2]} | {r_edit[1]} | {r_edit[3]}"
                        with st.container(border=True):
                            st.markdown(f"**{lbl}** &nbsp; {status_badge(str(r_edit[8]) if len(r_edit) > 8 else '')}", unsafe_allow_html=True)
                            if st.button("✏️ Editar este atendimento", key=f"ed_btn_{aid_e}", use_container_width=True):
                                st.session_state[f"edit_open_{aid_e}"] = True
                            if st.session_state.get(f"edit_open_{aid_e}"):
                                with st.form(f"form_edit_top_{aid_e}"):
                                    row_e = r_edit
                                    ed1, ed2, ed3 = st.columns(3)
                                    with ed1:
                                        ev_empresa = st.text_input("Empresa", value=str(row_e[1]), max_chars=100).strip()
                                        ev_modal = st.selectbox("Modalidade", [m.value for m in ModalidadeAtendimento],
                                            index=[m.value for m in ModalidadeAtendimento].index(str(row_e[3])) if row_e[3] in [m.value for m in ModalidadeAtendimento] else 0)
                                        ev_status = st.selectbox("Status", ["Agendado","Atendido","Concluído","Cancelado"],
                                            index=["Agendado","Atendido","Concluído","Cancelado"].index(str(row_e[8])) if row_e[8] in ["Agendado","Atendido","Concluído","Cancelado"] else 0)
                                    with ed2:
                                        ev_nome = st.text_input("Nome", value=str(row_e[2]), max_chars=100).strip()
                                        try:
                                            ev_dt = pd.to_datetime(str(row_e[4]), dayfirst=True, errors="coerce").date()
                                        except Exception:
                                            ev_dt = date.today()
                                        ev_data = st.date_input("Data", value=ev_dt, min_value=date(1900,1,1), max_value=date(2100,12,31))
                                    with ed3:
                                        try:
                                            hh_e, mm_e = str(row_e[5]).split(":")[:2]
                                            ev_tm = time(int(hh_e), int(mm_e))
                                        except Exception:
                                            ev_tm = time(8, 0)
                                        ev_hora = st.time_input("Hora", value=ev_tm)
                                        ev_obs = st.text_area("Observações", value=str(row_e[9] or ""), max_chars=1000).strip()
                                    s_save, s_cancel = st.columns(2)
                                    with s_save:
                                        saved = st.form_submit_button("💾 Salvar Alterações", type="primary")
                                    with s_cancel:
                                        cancelled = st.form_submit_button("Cancelar")
                                    if saved:
                                        try:
                                            db.atualizar_campos_atendimento(aid_e, {
                                                "empresa": ev_empresa, "nome": ev_nome,
                                                "modalidade": ev_modal,
                                                "data": ev_data,  # Passar objeto date, não string
                                                "hora": ev_hora,  # Passar objeto time, não string
                                                "status": ev_status, "observacoes": ev_obs,
                                            })
                                            st.toast("Alterações salvas!", icon="✅")
                                            st.session_state[f"edit_open_{aid_e}"] = False
                                            st.rerun()
                                        except Exception as ex:
                                            Security.log_error("EDIT_SAVE_TOP", ex)
                                            st.error("Erro ao salvar as alterações. Verifique os dados e tente novamente.")
                                    if cancelled:
                                        st.session_state[f"edit_open_{aid_e}"] = False
                                        st.rerun()

        AppointmentsPage._render_table(filters)

    @staticmethod
    def _render_table(filters):
        appointments = DatabaseManager.get_all_appointments()
        if not appointments:
            empty_state("📋", "Nenhum atendimento", "Cadastre um novo atendimento para começar a listagem.")
            return

        df = pd.DataFrame(
            appointments,
            columns=[
                "ID",
                "Empresa",
                "Nome",
                "Modalidade",
                "Data",
                "Hora",
                "Laudo PDF",
                "Avaliação PDF",
                "Status",
                "Observações",
            ],
        )

        if filters.get("modalidade_filter"):
            df = df[df["Modalidade"] == filters["modalidade_filter"]]
        if filters.get("status_filter"):
            df = df[df["Status"] == filters["status_filter"]]
        if filters.get("q"):
            q = filters["q"].lower()
            df = df[df["Nome"].str.lower().str.contains(q) | df["Empresa"].str.lower().str.contains(q)]
        # Filtrar por período (datas armazenadas como dd/mm/yyyy)
        try:
            df["_data_dt"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
            d1 = filters.get("date_start")
            d2 = filters.get("date_end")
            if d1:
                df = df[df["_data_dt"] >= pd.to_datetime(d1)]
            if d2:
                df = df[df["_data_dt"] <= pd.to_datetime(d2)]
        except Exception:
            pass

        df["Laudo"] = df["Laudo PDF"].apply(lambda x: "SIM" if x else "NÃO")
        df["Avaliação"] = df["Avaliação PDF"].apply(lambda x: "SIM" if x else "NÃO")

        st.subheader("📋 Lista de Atendimentos")

        # Paginação simples
        total_rows = len(df)
        page_size = st.selectbox("Tamanho da página", [10, 20, 50, 100], index=1, key="pg_size")
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, key="pg_num")
        start, end = (page - 1) * page_size, min(page * page_size, total_rows)
        page_df = df.iloc[start:end]

        # Aplicar cores ao DataFrame para UX
        def color_status(val):
            color = '#637381'
            if val == 'Agendado': color = '#2196F3'
            elif val == 'Atendido': color = '#4DA768'
            elif val == 'Concluído': color = '#1E5631'
            elif val == 'Cancelado': color = '#d32f2f'
            return f'color: {color}; font-weight: bold;'

        df_display = page_df[["Empresa", "Nome", "Modalidade", "Data", "Hora", "Laudo", "Avaliação", "Status"]].copy()
        try:
            st.dataframe(df_display.style.map(color_status, subset=['Status']), use_container_width=True, height=420)
        except:
            st.dataframe(df_display, use_container_width=True, height=420)

        csv_data = df.to_csv(index=False, sep=';').encode("utf-8-sig")
        
        c_dl1, c_dl2 = st.columns([1, 1])
        with c_dl1:
            st.download_button("⬇️ Exportar CSV", data=csv_data, file_name="atendimentos_filtrados.csv", mime="text/csv")
        with c_dl2:
            try:
                pdf_bytes = generate_pdf_report(df)
                st.download_button("⬇️ Exportar PDF", data=pdf_bytes, file_name="atendimentos_filtrados.pdf", mime="application/pdf")
            except Exception as e:
                Security.log_error("PDF_LIST_EXPORT", e)
                st.error("Erro interno ao gerar o relatório PDF.")

        # Downloads de anexos diretamente na lista
        def _download_button_from_ref(ref: str, label: str, key: str):
            if not ref:
                return
            try:
                if isinstance(ref, str) and ref.startswith("db:"):
                    fid = int(str(ref).split(":", 1)[1])
                    reg = db.obter_arquivo_por_id(fid)
                    if reg:
                        st.download_button(
                            label=label,
                            data=reg["content"],
                            file_name=reg.get("filename", "arquivo.pdf"),
                            mime=reg.get("content_type", "application/pdf"),
                            key=key
                        )
                else:
                    # caminho em disco (compatibilidade)
                    if os.path.exists(str(ref)):
                        with open(ref, "rb") as f:
                            st.download_button(
                                label=label,
                                data=f.read(),
                                file_name=os.path.basename(str(ref)),
                                mime="application/pdf",
                                key=key
                            )
            except Exception as e:
                st.caption(f"Não foi possível preparar o download ({label}): {e}")

        # Mapear linhas paginadas para tuplas originais
        id_set = set(page_df["ID"].tolist())
        page_rows = [r for r in appointments if r[0] in id_set]

        st.markdown("---")
        with st.expander("🪄 Gerador de Parecer Clínico Automático (IA)", expanded=False):
            st.markdown("A IA transforma suas breves anotações da tabela em um Parecer Técnico formal, pronto para impressão.")
            if not page_df.empty:
                # Baseado na página atual para não sobrecarregar
                opcoes = page_df.apply(lambda r: f"ID {r['ID']} | {r['Nome']} | {r['Modalidade']}", axis=1).tolist()
                sel_appt = st.selectbox("Selecione o Atendimento (Página Atual):", opcoes)
                
                if st.button("🪄 Gerar Rascunho Formal", type="primary", key="ai_draft_btn"):
                    sel_id = int(sel_appt.split("|")[0].replace("ID", "").strip())
                    row_data = page_df[page_df["ID"] == sel_id].iloc[0]
                    nome_pac, emp_pac, mod_pac, obs_pac = str(row_data["Nome"]), str(row_data["Empresa"]), str(row_data["Modalidade"]), str(row_data["Observações"])
                    
                    if not obs_pac or obs_pac.strip().lower() in ["", "nan", "none"]:
                        st.warning("Eita! Este atendimento não possui 'Observações' salvas. A IA precisa de algumas notas para expandi-las em um laudo.")
                    else:
                        with st.spinner("IA redigindo parecer formal..."):
                            from ai_manager import AIManager
                            draft = AIManager.generate_clinical_draft(nome_pac, emp_pac, mod_pac, obs_pac)
                            st.success("Parecer gerado com sucesso!")
                            st.text_area("Rascunho Final (Copie para o Word)", value=draft, height=400, key=f"draft_{sel_id}")
            else:
                empty_state("🗂️", "Tabela vazia", "Não há atendimentos cadastrados para exibir.")


        with st.expander("📎 Gerenciar por atendimento (visualizar/download/editar/status/exportar)", expanded=False):
            for row in page_rows:
                aid, empresa, nome, modalidade, data_s, hora_s = row[0], row[1], row[2], row[3], row[4], row[5]
                laudo_ref, aval_ref, status_row = row[6], row[7], row[8]
                status_raw = str(row[8])
                status_class = f"status-{status_raw.lower().replace('í','i')}"
                
                with st.container(border=True):
                    st.markdown(f"**📌 {nome} | {empresa} | {data_s}**")
                    c10, c20 = st.columns([3, 1])
                    with c10:
                        st.info(f"ID: #{aid} | {modalidade}")
                        st.write(f"Status: **{status_raw}**")
                    
                    c1, c2, c3, c4, c5, c6, c7, c8, c9, c10m = st.columns([2.5, 1, 1, 1, 1, 1, 1, 1, 1.2, 1.2])
                    with c1:
                        st.write(f"📄 {nome} — {empresa}")
                    with c2:
                        if laudo_ref:
                            _download_button_from_ref(laudo_ref, "⬇️ Laudo", key=f"dl_laudo_{aid}")
                        else:
                            st.caption("Laudo: —")
                    with c3:
                        if aval_ref:
                            _download_button_from_ref(aval_ref, "⬇️ Avaliação", key=f"dl_aval_{aid}")
                        else:
                            st.caption("Avaliação: —")
                    with c4:
                        if laudo_ref and st.button("👁️ Ver Laudo", key=f"pv_laudo_{aid}"):
                            _preview_pdf_from_ref(laudo_ref, title=f"Laudo - {nome}")
                    with c5:
                        if aval_ref and st.button("👁️ Ver Aval.", key=f"pv_aval_{aid}"):
                            _preview_pdf_from_ref(aval_ref, title=f"Avaliação - {nome}")
                    with c6:
                        if isinstance(laudo_ref, str) and laudo_ref.startswith("db:"):
                            if st.button("🗑️ Laudo", key=f"rm_laudo_{aid}"):
                                try:
                                    fid = int(laudo_ref.split(":",1)[1])
                                    db.limpar_anexo_atendimento(aid, "laudo_pdf")
                                    db.excluir_arquivo(fid)
                                    st.success("Laudo excluído")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir laudo: {e}")
                    with c7:
                        if isinstance(aval_ref, str) and aval_ref.startswith("db:"):
                            if st.button("🗑️ Aval.", key=f"rm_aval_{aid}"):
                                try:
                                    fid = int(aval_ref.split(":",1)[1])
                                    db.limpar_anexo_atendimento(aid, "avaliacao_pdf")
                                    db.excluir_arquivo(fid)
                                    st.success("Avaliação excluída")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir avaliação: {e}")
                    with c8:
                        if st.button("✏️ Editar", key=f"edit_{aid}"):
                            st.session_state[f"edit_open_{aid}"] = True
                    with c9:
                        # Integração WhatsApp (UX #1)
                        msg = f"Olá {nome}, confirmamos seu atendimento clínico na {empresa} para o dia {data_s} às {hora_s}."
                        import urllib.parse
                        wp_url = f"https://wa.me/?text={urllib.parse.quote(msg)}"
                        st.link_button("🟢 WhatsApp", wp_url, use_container_width=True)
                    
                    with c10m:
                        with st.popover(f"⚙️", use_container_width=True):
                            st.caption("Ações")
                            if st.button("🗑️ Excluir Atend.", key=f"del_apt_{aid}"):
                                # Confirmação de Segurança (UX #5)
                                if DatabaseManager.delete_appointment(aid):
                                    st.toast("Atendimento excluído!", icon="🗑️")
                                    st.rerun()
                            
                            st.divider()
                            for stx in ["Agendado", "Atendido", "Concluído", "Cancelado"]:
                                if st.button(stx, key=f"st_{stx}_{aid}"):
                                    try:
                                        db.atualizar_status(aid, stx)
                                        st.toast(f"Status atualizado: {stx}", icon="🔄")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")

                # ─── MANUTENÇÃO DE DADOS ───────────────────────────────────────
                with st.container(border=True):
                    st.markdown("##### 🔧 Manutenção de Dados")
                    tab_edit, tab_del, tab_rec = st.tabs(["✏️ Editar", "🗑️ Excluir", "🔎 Recuperar Dados"])

                    with tab_edit:
                        st.caption("Abra o formulário completo de edição para este atendimento.")
                        if st.button("✏️ Abrir Formulário de Edição", key=f"maint_edit_{aid}", use_container_width=True):
                            st.session_state[f"edit_open_{aid}"] = True
                            st.rerun()

                    with tab_del:
                        st.caption("⚠️ A exclusão é permanente. Ative a confirmação antes de prosseguir.")
                        confirm_key = f"confirm_del_{aid}"
                        confirmar = st.checkbox("Confirmar exclusão permanente", key=confirm_key)
                        if confirmar:
                            if st.button("🗑️ Excluir Definitivamente", key=f"maint_del_{aid}", type="primary", use_container_width=True):
                                if DatabaseManager.delete_appointment(aid):
                                    st.toast("Atendimento excluído!", icon="🗑️")
                                    st.rerun()
                                else:
                                    st.error("Erro ao excluir. Tente novamente.")

                    with tab_rec:
                        st.caption("Dados originais armazenados no banco. Use para verificar ou corrigir manualmente.")
                        st.dataframe({
                            "Campo": ["ID", "Empresa", "Nome", "Modalidade", "Data", "Hora", "Status", "Observações", "Laudo", "Avaliação"],
                            "Valor Salvo": [
                                str(row[0]), str(row[1]), str(row[2]), str(row[3]),
                                str(row[4]), str(row[5]), str(row[8]), str(row[9] or "—"),
                                "✅ Anexado" if row[6] else "—",
                                "✅ Anexada" if row[7] else "—",
                            ]
                        }, use_container_width=True, hide_index=True)
                        # Download dos dados brutos como CSV para auditoria
                        import json
                        raw_json = json.dumps({
                            "id": row[0], "empresa": str(row[1]), "nome": str(row[2]),
                            "modalidade": str(row[3]), "data": str(row[4]), "hora": str(row[5]),
                            "status": str(row[8]), "observacoes": str(row[9] or ""),
                        }, ensure_ascii=False, indent=2)
                        st.download_button(
                            "⬇️ Baixar registro como JSON",
                            data=raw_json,
                            file_name=f"atendimento_{aid}_backup.json",
                            mime="application/json",
                            key=f"dl_raw_{aid}"
                        )
                # ─── FIM MANUTENÇÃO DE DADOS ───────────────────────────────────

                # Parecer Clínico com IA (Bug 2 fix) - USANDO CONTAINER para evitar erro de nesting
                with st.container(border=True):
                    st.markdown(f"##### 🪄 Gerar Parecer Clínico com IA — #{aid}")
                    st.caption("Escreva suas anotações brutas e a IA transforma em um parecer clínico formal.")
                    obs_rascunho = st.text_area(
                        "Suas anotações (rascunho)",
                        placeholder="Ex: Paciente ansioso, leve insônia, MAS APTO ao trabalho. Recomendo acompanhamento.",
                        key=f"parecer_obs_{aid}",
                        height=100
                    )
                    if st.button("✍️ Gerar Parecer Formal", key=f"btn_parecer_{aid}", type="primary"):
                        if not obs_rascunho.strip():
                            st.warning("Escreva suas anotações antes de gerar o parecer.")
                        else:
                            with st.spinner("IA redigindo o parecer clínico..."):
                                from ai_manager import AIManager
                                parecer = AIManager.generate_clinical_draft(
                                    nome=str(nome),
                                    empresa=str(empresa),
                                    modalidade=str(modalidade),
                                    observacoes=obs_rascunho.strip()
                                )
                            st.markdown("---")
                            st.markdown(parecer)
                            st.download_button(
                                label="⬇️ Baixar Parecer (.txt)",
                                data=parecer,
                                file_name=f"parecer_{str(nome).replace(' ','_')}_{aid}.txt",
                                mime="text/plain",
                                key=f"dl_parecer_{aid}"
                            )

                # Editor inline por atendimento
                if st.session_state.get(f"edit_open_{aid}"):
                    with st.container(border=True):
                        st.markdown(f"**✏️ Editar atendimento #{aid}**")
                        with st.form(f"form_edit_{aid}"):
                            colu1, colu2, colu3 = st.columns(3)
                            with colu1:
                                nv_empresa = st.text_input("Empresa", value=str(empresa), max_chars=100).strip()
                                nv_modal = st.selectbox("Modalidade", [m.value for m in ModalidadeAtendimento], index= [m.value for m in ModalidadeAtendimento].index(str(row[3])) if row[3] in [m.value for m in ModalidadeAtendimento] else 0)
                                nv_status = st.selectbox("Status", ["Agendado","Atendido","Concluído","Cancelado"], index=["Agendado","Atendido","Concluído","Cancelado"].index(str(row[8])) if row[8] in ["Agendado","Atendido","Concluído","Cancelado"] else 0)
                            with colu2:
                                nv_nome = st.text_input("Nome", value=str(nome), max_chars=100).strip()
                                try:
                                    cur_dt = pd.to_datetime(str(row[4]), dayfirst=True, errors="coerce").date()
                                except Exception:
                                    cur_dt = date.today()
                                nv_data = st.date_input("Data", value=cur_dt, min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
                            with colu3:
                                try:
                                    (hh,mm) = str(row[5]).split(":")[:2]
                                    cur_tm = time(int(hh), int(mm))
                                except Exception:
                                    cur_tm = time(8,0)
                                nv_hora = st.time_input("Hora", value=cur_tm)
                                nv_obs = st.text_area("Observações", value=str(row[9] or ""), max_chars=1000).strip()
                            st.markdown("#### 📎 Anexos")
                            colaf1, colaf2 = st.columns(2)
                            with colaf1:
                                up_laudo_novo = st.file_uploader("Substituir Laudo (PDF)", type=["pdf"], key=f"up_laudo_edit_{aid}")
                            with colaf2:
                                up_aval_novo = st.file_uploader("Substituir Avaliação (PDF)", type=["pdf"], key=f"up_aval_edit_{aid}")
                            colbtn1, colbtn2, colbtn3, colbtn4 = st.columns([1.2,1,1,1])
                            with colbtn1:
                                s = st.form_submit_button("💾 Salvar alterações", type="primary")
                            with colbtn2:
                                cancel = st.form_submit_button("Cancelar")
                            with colbtn3:
                                exp_csv = st.form_submit_button("⬇️ Exportar CSV")
                            with colbtn4:
                                exp_pdf = st.form_submit_button("⬇️ Exportar PDF")
                            
                            colbtn5, = st.columns(1)
                            with colbtn5:
                                exp_html = st.form_submit_button("🖨️ Exportar HTML (PDF via impressão)")
                            if s:
                                try:
                                    updates = {
                                        "empresa": nv_empresa,
                                        "nome": nv_nome,
                                        "modalidade": nv_modal,
                                        "data": nv_data,
                                        "hora": nv_hora,
                                        "status": nv_status,
                                        "observacoes": nv_obs,
                                    }
                                    db.atualizar_campos_atendimento(aid, updates)
                                    if up_laudo_novo is not None:
                                        new_marker = save_uploaded_pdf(up_laudo_novo)
                                        db.set_anexo(aid, "laudo_pdf", new_marker or None)
                                        try:
                                            if isinstance(laudo_ref, str) and laudo_ref.startswith("db:"):
                                                old_id = int(laudo_ref.split(":",1)[1])
                                                db.excluir_arquivo(old_id)
                                        except Exception:
                                            pass
                                    if up_aval_novo is not None:
                                        new_marker2 = save_uploaded_pdf(up_aval_novo)
                                        db.set_anexo(aid, "avaliacao_pdf", new_marker2 or None)
                                        try:
                                            if isinstance(aval_ref, str) and aval_ref.startswith("db:"):
                                                old_id2 = int(aval_ref.split(":",1)[1])
                                                db.excluir_arquivo(old_id2)
                                        except Exception:
                                            pass
                                    st.toast("Alterações salvas com sucesso!", icon="✅")
                                    st.session_state[f"edit_open_{aid}"] = False
                                    st.rerun()
                                except Exception as e:
                                    Security.log_error("EDIT_SAVE_INLINE", e)
                                    st.error("Erro ao salvar as alterações. Verifique os dados e tente novamente.")
                            elif cancel:
                                st.session_state[f"edit_open_{aid}"] = False
                                st.rerun()
                            elif exp_csv:
                                try:
                                    row_df = pd.DataFrame([{
                                        "ID": row[0],
                                        "Empresa": row[1],
                                        "Nome": row[2],
                                        "Modalidade": row[3],
                                        "Data": row[4],
                                        "Hora": row[5],
                                        "Laudo PDF": row[6],
                                        "Avaliação PDF": row[7],
                                        "Status": row[8],
                                        "Observações": row[9],
                                    }])
                                    csv_bytes = row_df.to_csv(index=False, sep=';').encode("utf-8-sig")
                                    st.download_button("Baixar CSV do Atendimento", data=csv_bytes, file_name=f"atendimento_{aid}.csv", mime="text/csv", key=f"dl_csv_{aid}")
                                except Exception as e:
                                    st.error(f"Erro ao exportar CSV: {e}")
                            elif exp_pdf:
                                try:
                                    row_df = pd.DataFrame([{
                                        "ID": row[0],
                                        "Empresa": row[1],
                                        "Nome": row[2],
                                        "Modalidade": row[3],
                                        "Data": row[4],
                                        "Hora": row[5],
                                        "Laudo PDF": row[6],
                                        "Avaliação PDF": row[7],
                                        "Status": row[8],
                                        "Observações": row[9],
                                    }])
                                    pdf_bytes = generate_pdf_report(row_df)
                                    st.download_button("Baixar PDF do Atendimento", data=pdf_bytes, file_name=f"atendimento_{aid}.pdf", mime="application/pdf", key=f"dl_pdf_{aid}")
                                except Exception as e:
                                    st.error(f"Erro ao exportar PDF: {e}")
                            elif exp_html:
                                try:
                                    html = _build_html_attendance_summary(row)
                                    st.download_button("Baixar HTML do Atendimento", data=html.encode("utf-8"), file_name=f"atendimento_{aid}.html", mime="text/html", key=f"dl_html_{aid}")
                                except Exception as e:
                                    st.error(f"Erro ao exportar HTML: {e}")

        st.caption(f"Mostrando registros {start+1}–{end} de {total_rows} (página {page}/{total_pages})")

def _preview_pdf_from_ref(ref: str, title: str = "PDF"):
        try:
                content: bytes = b""
                filename = "arquivo.pdf"
                if isinstance(ref, str) and ref.startswith("db:"):
                        fid = int(str(ref).split(":", 1)[1])
                        reg = db.obter_arquivo_por_id(fid)
                        if not reg:
                                st.warning("Arquivo não encontrado")
                                return
                        content = reg.get("content") or b""
                        filename = reg.get("filename") or filename
                else:
                        if os.path.exists(str(ref)):
                                filename = os.path.basename(str(ref))
                                with open(ref, "rb") as f:
                                        content = f.read()
                if not content:
                        st.info("Sem conteúdo para visualizar.")
                        return
                b64 = base64.b64encode(content).decode("ascii")
                html = f"""
<div style='border:1px solid #e1e1e1;border-radius:8px;padding:6px;background:#fff;'>
    <div style='font-weight:600;margin-bottom:6px;'>{title} — {filename}</div>
    <iframe src='data:application/pdf;base64,{b64}' width='100%' height='600px' style='border:none;'></iframe>
</div>
"""
                components.html(html, height=640)
        except Exception as e:
                st.error(f"Falha ao visualizar: {e}")

def _build_html_attendance_summary(row_tuple):
        aid, empresa, nome, modalidade, data_s, hora_s, laudo_ref, aval_ref, status, observacoes = row_tuple
        def _label_for(ref):
                if not ref:
                        return "—"
                if isinstance(ref, str) and ref.startswith("db:"):
                        try:
                                fid = int(ref.split(":",1)[1])
                                reg = db.obter_arquivo_por_id(fid)
                                if reg:
                                        return f"(BD) {reg.get('filename','arquivo.pdf')}"
                        except Exception:
                                pass
                        return "(BD) arquivo.pdf"
                return os.path.basename(str(ref)) if os.path.exists(str(ref)) else str(ref)
        html = f"""
<!doctype html>
<html lang='pt-br'>
<head>
    <meta charset='utf-8'/>
    <title>Atendimento #{aid}</title>
    <style>
        body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 16px; }}
        h1 {{ margin-bottom: 6px; }}
        .card {{ border:1px solid #e1e1e1; border-radius:8px; padding:12px; margin: 10px 0; }}
        .row {{ display:flex; gap:16px; flex-wrap: wrap; }}
        .item {{ flex:1 1 260px; }}
        .muted {{ color:#666; }}
    </style>
    </head>
<body>
    <h1>Atendimento #{aid}</h1>
    <div class='muted'>Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
    <div class='card'>
        <div class='row'>
            <div class='item'><strong>Empresa:</strong> {empresa}</div>
            <div class='item'><strong>Nome:</strong> {nome}</div>
            <div class='item'><strong>Modalidade:</strong> {modalidade}</div>
        </div>
        <div class='row'>
            <div class='item'><strong>Data:</strong> {data_s}</div>
            <div class='item'><strong>Hora:</strong> {hora_s}</div>
            <div class='item'><strong>Status:</strong> {status}</div>
        </div>
        <div class='row'>
            <div class='item'><strong>Laudo:</strong> {_label_for(laudo_ref)}</div>
            <div class='item'><strong>Avaliação:</strong> {_label_for(aval_ref)}</div>
        </div>
        <div class='row'>
            <div class='item' style='flex:1 1 100%'><strong>Observações:</strong><br/>{observacoes or ''}</div>
        </div>
    </div>
    <p class='muted'>Dica: Abra este arquivo no navegador e use Imprimir → Salvar como PDF.</p>
</body>
</html>
"""
        return html

class AgendaPage:
    @staticmethod
    def render() -> None:
        render_page_header("📅 Agenda", "Agendamentos, fila de espera, triagem e teleconsulta")

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗓️ Agenda do Dia", "➕ Agendar", "🩺 Triagem", "⏳ Fila de Espera", "🎥 Teleconsulta"])

        pacientes = db.listar_pacientes()

        with tab1:
            st.markdown("### 🗓️ Agenda")
            col_a1, col_a2 = st.columns([2, 2])
            with col_a1:
                data_sel = st.date_input("Data", value=date.today(), key="agenda_data")
            with col_a2:
                medico_sel = st.selectbox("Médico", ["Todos"] + AGENDA_MEDICOS, key="agenda_medico")

            filtro_medico = None if medico_sel == "Todos" else medico_sel
            agendamentos = db.listar_agendamentos(data=data_sel.strftime("%Y-%m-%d"), medico=filtro_medico)

            if not agendamentos:
                empty_state("🗓️", "Agenda vazia", "Não há agendamentos para esta data. Adicione um novo abaixo.")
            else:
                horarios = []
                for ag in sorted(agendamentos, key=lambda x: str(x["hora"])):
                    status = ag["status"]
                    cor = {"Agendado": "#E8F4FD", "Check-in": "#FFF4E6", "Em Atendimento": "#E6F9E6",
                           "Concluído": "#F0F0F0", "Cancelado": "#FDECEA", "Reagendado": "#FFF8E1"}.get(status, "#FFFFFF")
                    horario = str(ag["hora"])[:5]
                    nome = ag["paciente_nome"] or f"Paciente #{ag['paciente_id']}"
                    medico = ag["medico"]
                    empresa = ag["empresa"] or ""
                    horarios.append(f"""
                    <div style='display:flex;align-items:center;gap:12px;background:{cor};
                         border-radius:8px;padding:10px 14px;margin:4px 0;border-left:4px solid #4A90D9'>
                        <span style='font-weight:700;font-size:1.1rem;min-width:52px;color:#1a1a1a'>{horario}</span>
                        <span style='font-weight:600;color:#1a1a1a'>{nome}</span>
                        <span style='color:#555;font-size:0.85rem'>• {medico} • {empresa}</span>
                        <span style='margin-left:auto;'>{status_badge(status)}</span>
                    </div>""")
                st.markdown("".join(horarios), unsafe_allow_html=True)

                st.markdown("### ⚙️ Ações do Agendamento")
                opcoes_ag = {f"#{a['id']} — {a['paciente_nome'] or '?'} ({str(a['hora'])[:5]}) {a['status']}": a["id"] for a in agendamentos}
                sel_ag = st.selectbox("Selecione o agendamento", list(opcoes_ag.keys()), key="agenda_sel_acao")
                ag_id = opcoes_ag[sel_ag]
                ac1, ac2, ac3, ac4, ac5 = st.columns(5)
                with ac1:
                    if st.button("✅ Check-in", key=f"ag_chk_{ag_id}"):
                        db.marcar_checkin(ag_id)
                        st.rerun()
                with ac2:
                    if st.button("🩺 Em Atend.", key=f"ag_atd_{ag_id}"):
                        db.atualizar_agendamento(ag_id, {"status": "Em Atendimento"})
                        st.rerun()
                with ac3:
                    if st.button("✅ Concluir", key=f"ag_conc_{ag_id}"):
                        db.atualizar_agendamento(ag_id, {"status": "Concluído"})
                        st.rerun()
                with ac4:
                    if st.button("📅 Reagendar", key=f"ag_rea_{ag_id}"):
                        st.session_state["reagendar_ag_id"] = ag_id
                        st.session_state["aba_agenda"] = "Agendar"
                        st.rerun()
                with ac5:
                    if st.button("✖ Cancelar", key=f"ag_canc_{ag_id}"):
                        db.cancelar_agendamento(ag_id)
                        st.rerun()

                # Totais do dia
                totais = {}
                for a in agendamentos:
                    totais[a["status"]] = totais.get(a["status"], 0) + 1
                st.caption(" | ".join(f"{k}: {v}" for k, v in totais.items()))

        with tab2:
            st.markdown("### ➕ Novo Agendamento")
            r_ag_id = st.session_state.get("reagendar_ag_id")
            reagendando = db.obter_agendamento(r_ag_id) if r_ag_id else None
            if reagendando:
                st.info(f"Reagendando: #{reagendando['id']} — {reagendando['paciente_nome']} em {reagendando['data']} às {str(reagendando['hora'])[:5]}")
            else:
                st.session_state.pop("reagendar_ag_id", None)

            n1, n2 = st.columns(2)
            with n1:
                nomes = {p["nome"]: p["id"] for p in pacientes}
                if nomes:
                    sel_nome = st.selectbox("Paciente *", list(nomes.keys()), key="ag_paciente")
                    pac_id = nomes[sel_nome]
                    pac = db.obter_paciente(pac_id)
                    empresa_sugerida = pac.get("empresa") if pac else None
                else:
                    sel_nome = None
                    pac_id = None
                    empresa_sugerida = None
                ag_empresa = st.text_input("Empresa", value=empresa_sugerida or "", key="ag_empresa")
                ag_medico = st.selectbox("Médico *", AGENDA_MEDICOS, key="ag_medico")
            with n2:
                ag_data = st.date_input("Data *", value=date.today(), key="ag_data")
                ag_hora = st.time_input("Horário *", value=time(9, 0), key="ag_hora")
                ag_tipo = st.selectbox("Tipo", ["Consulta", "Retorno", "Triagem", "Teleconsulta", "Procedimento"], key="ag_tipo")
                ag_duracao = st.selectbox("Duração", [30, 50, 60, 90, 120], index=1, format_func=lambda x: f"{x} min", key="ag_duracao")

            ag_especialidade = st.text_input("Especialidade", key="ag_especialidade", placeholder="Ex: Psicologia Clínica")
            ag_obs = st.text_area("Observações", key="ag_obs")

            if st.button("💾 Salvar Agendamento", type="primary", key="ag_salvar", use_container_width=True):
                if not sel_nome:
                    st.error("Cadastre um paciente antes de agendar.")
                else:
                    hora_str = ag_hora.strftime("%H:%M")
                    conflito = db.verificar_conflito(ag_medico, ag_data.strftime("%Y-%m-%d"), hora_str, int(ag_duracao), excluir_id=r_ag_id)
                    if conflito:
                        st.error(f"⚠️ Conflito de horário: {ag_medico} já possui atendimento nesse horário. Escolha outro horário.")
                    else:
                        dados = {
                            "paciente_id": pac_id,
                            "paciente_nome": sel_nome,
                            "empresa": ag_empresa.strip() or None,
                            "medico": ag_medico,
                            "especialidade": ag_especialidade.strip() or None,
                            "data": ag_data.strftime("%Y-%m-%d"),
                            "hora": hora_str,
                            "hora_fim": db._somar_minutos_hora(hora_str, int(ag_duracao)),
                            "duracao_min": int(ag_duracao),
                            "tipo": ag_tipo,
                            "observacoes": ag_obs.strip() or None,
                        }
                        if reagendando:
                            dados["status"] = "Agendado"
                            ok = db.atualizar_agendamento(r_ag_id, dados)
                            msg = "Agendamento reagendado com sucesso!"
                            if ok:
                                db.criar_lembretes_agendamento(r_ag_id)
                        else:
                            novo_id = db.inserir_agendamento(dados)
                            ok = novo_id is not None
                            msg = "Agendamento criado com sucesso!"
                            if ok:
                                db.criar_lembretes_agendamento(novo_id)
                        if ok:
                            st.toast(msg, icon="✅")
                            security.log_access("ADD_AGENDAMENTO", f"{sel_nome} - {ag_data} {hora_str}")
                            st.session_state.pop("reagendar_ag_id", None)
                            st.rerun()
                        else:
                            st.error("Erro ao salvar agendamento.")

        with tab3:
            st.markdown("### 🩺 Triagem Pré-Atendimento")
            agendamentos_triagem = db.listar_agendamentos(data=date.today().strftime("%Y-%m-%d"))
            if agendamentos_triagem:
                opcoes_t = {f"#{a['id']} — {a['paciente_nome'] or '?'} ({str(a['hora'])[:5]})": a["id"] for a in agendamentos_triagem}
                sel_t = st.selectbox("Agendamento", list(opcoes_t.keys()), key="tri_sel")
                t_id = opcoes_t[sel_t]
                ag_t = db.obter_agendamento(t_id)
            else:
                t_id = None
                ag_t = None
                empty_state("🗓️", "Sem agendamentos hoje", "Preencha os dados abaixo manualmente para registrar um agendamento.")

            t1, t2, t3 = st.columns(3)
            with t1:
                t_peso = st.number_input("Peso (kg)", min_value=0.0, step=0.1, key="tri_peso")
                t_pressao = st.text_input("Pressão arterial", placeholder="120/80", key="tri_pressao")
                t_saturacao = st.number_input("Saturação (%)", min_value=0.0, step=0.1, key="tri_sat")
            with t2:
                t_altura = st.number_input("Altura (m)", min_value=0.0, step=0.01, key="tri_altura")
                t_temp = st.number_input("Temperatura (°C)", min_value=0.0, step=0.1, key="tri_temp")
                t_glicemia = st.number_input("Glicemia (mg/dL)", min_value=0, step=1, key="tri_glic")
            with t3:
                t_fc = st.number_input("Freq. cardíaca (bpm)", min_value=0, step=1, key="tri_fc")
                t_grav = st.selectbox("Gravidade", ["Normal", "Prioritário", "Urgente"], key="tri_grav")
            t_queixa = st.text_area("Queixa principal", key="tri_queixa")
            t_hist = st.text_area("Histórico resumido", key="tri_hist")
            t_obs = st.text_area("Observações", key="tri_obs")

            if st.button("💾 Salvar Triagem", type="primary", key="tri_salvar", use_container_width=True):
                dados_t = {
                    "agendamento_id": t_id,
                    "paciente_id": ag_t["paciente_id"] if ag_t else None,
                    "data": date.today().strftime("%Y-%m-%d"),
                    "peso": t_peso or None, "altura": t_altura or None,
                    "pressao": t_pressao.strip() or None, "temperatura": t_temp or None,
                    "freq_cardiaca": t_fc or None, "saturacao": t_saturacao or None,
                    "glicemia": t_glicemia or None, "queixa_principal": t_queixa.strip() or None,
                    "historico_resumido": t_hist.strip() or None, "observacoes": t_obs.strip() or None,
                    "gravidade": t_grav, "avaliado_por": st.session_state.get("user_name", ""),
                }
                ok = db.salvar_triagem(dados_t)
                if ok:
                    st.toast("Triagem salva!", icon="✅")
                    st.rerun()
                else:
                    st.error("Erro ao salvar triagem.")

            triagens_hoje = db.listar_triagens(data=date.today().strftime("%Y-%m-%d"))
            if triagens_hoje:
                st.markdown("#### Triagens de hoje")
                df_tri = pd.DataFrame([{
                    "Hora": str(t["hora"])[:5] if t["hora"] else "",
                    "Médico": t["medico"] or "",
                    "Peso": t["peso"] or "", "PA": t["pressao"] or "",
                    "FC": t["freq_cardiaca"] or "", "Sat": t["saturacao"] or "",
                    "Gravidade": t["gravidade"] or "",
                } for t in triagens_hoje])
                st.dataframe(df_tri, use_container_width=True, hide_index=True)

        with tab4:
            st.markdown("### ⏳ Fila de Espera")
            fc1, fc2 = st.columns(2)
            with fc1:
                fe_nome = st.text_input("Nome do paciente *", key="fe_nome")
                fe_empresa = st.text_input("Empresa", key="fe_empresa")
            with fc2:
                fe_prior = st.selectbox("Prioridade", ["Normal", "Prioritário", "Urgente"], key="fe_prior")
                fe_obs = st.text_input("Observações", key="fe_obs")
            if st.button("➕ Entrar na Fila", type="primary", key="fe_add"):
                if not fe_nome.strip():
                    st.error("Informe o nome do paciente.")
                else:
                    ok = db.entrar_fila_espera(fe_nome.strip(), fe_empresa.strip() or None,
                                               date.today().strftime("%Y-%m-%d"),
                                               datetime.datetime.now().strftime("%H:%M"), fe_prior, fe_obs.strip() or None)
                    if ok:
                        st.toast("Paciente na fila!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao entrar na fila.")

            fila = db.listar_fila_espera()
            if not fila:
                st.info("Fila de espera vazia hoje.")
            else:
                st.markdown("#### Fila atual")
                for i, f in enumerate(fila, start=1):
                    cor = {"Urgente": "#FDECEA", "Prioritário": "#FFF4E6", "Normal": "#E8F4FD"}.get(f["prioridade"], "#FFFFFF")
                    st.markdown(f"""
                    <div style='display:flex;align-items:center;gap:10px;background:{cor};
                         border-radius:8px;padding:8px 12px;margin:3px 0;border-left:4px solid #4A90D9'>
                        <span style='font-weight:700;color:#4A90D9'>{i}.</span>
                        <span style='font-weight:600;color:#1a1a1a'>{f['paciente_nome']}</span>
                        <span style='color:#555;font-size:0.85rem'>• {f['hora_chegada']} • {f['prioridade']}</span>
                        <span style='margin-left:auto;color:#888'>{f['status']}</span>
                    </div>""", unsafe_allow_html=True)
                st.markdown("#### Ações")
                opcoes_f = {f"{f['id']} — {f['paciente_nome']} ({f['prioridade']})": f["id"] for f in fila}
                sel_f = st.selectbox("Selecione", list(opcoes_f.keys()), key="fila_sel")
                fid = opcoes_f[sel_f]
                fa1, fa2, fa3 = st.columns(3)
                with fa1:
                    if st.button("🩺 Chamar / Em Atend.", key=f"fila_atd_{fid}"):
                        db.atualizar_fila_espera(fid, "Em Atendimento")
                        st.rerun()
                with fa2:
                    if st.button("✅ Finalizar", key=f"fila_fin_{fid}"):
                        db.atualizar_fila_espera(fid, "Finalizado")
                        st.rerun()
                with fa3:
                    if st.button("🗑️ Remover", key=f"fila_rm_{fid}"):
                        db.remover_fila_espera(fid)
                        st.rerun()

        with tab5:
            st.markdown("### 🎥 Teleconsulta")
            tc1, tc2 = st.columns(2)
            with tc1:
                nomes_tc = {p["nome"]: p["id"] for p in pacientes}
                sel_tc = st.selectbox("Paciente *", list(nomes_tc.keys()) if nomes_tc else [""], key="tc_paciente") if nomes_tc else None
                pac_tc_id = nomes_tc.get(sel_tc) if nomes_tc else None
                tc_medico = st.selectbox("Médico *", AGENDA_MEDICOS, key="tc_medico")
                tc_data = st.date_input("Data *", value=date.today(), key="tc_data")
                tc_hora = st.time_input("Horário *", value=time(14, 0), key="tc_hora")
            with tc2:
                tc_plataforma = st.selectbox("Plataforma", ["Google Meet", "Zoom", "Microsoft Teams", "WhatsApp"], key="tc_plat")
                tc_link = st.text_input("Link da videochamada", key="tc_link", placeholder="https://meet.google.com/...")
                tc_duracao = st.selectbox("Duração", [30, 50, 60], index=1, format_func=lambda x: f"{x} min", key="tc_duracao")
                tc_obs = st.text_input("Observações", key="tc_obs")
            if st.button("💾 Criar Teleconsulta", type="primary", key="tc_salvar", use_container_width=True):
                if not sel_tc:
                    st.error("Cadastre um paciente antes de criar teleconsulta.")
                else:
                    hora_str = tc_hora.strftime("%H:%M")
                    ok = db.criar_teleconsulta({
                        "paciente_id": pac_tc_id, "medico": tc_medico,
                        "data": tc_data.strftime("%Y-%m-%d"), "hora": hora_str,
                        "plataforma": tc_plataforma, "link": tc_link.strip() or None,
                        "duracao_min": int(tc_duracao), "observacoes": tc_obs.strip() or None,
                    })
                    if ok:
                        st.toast("Teleconsulta agendada!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao criar teleconsulta.")

            teleconsultas = db.listar_teleconsulta(medico="Todos" if False else None)
            if teleconsultas:
                st.markdown("#### Teleconsultas agendadas")
                df_tc = pd.DataFrame([{
                    "Data": t["data"], "Hora": str(t["hora"])[:5], "Médico": t["medico"],
                    "Paciente": t.get("paciente_nome") or f"#{t['paciente_id']}",
                    "Plataforma": t["plataforma"], "Status": t["status"],
                } for t in teleconsultas])
                st.dataframe(df_tc, use_container_width=True, hide_index=True)

class ClinicalDocsPage:
    @staticmethod
    def render() -> None:
        render_page_header("📋 Documentos Clínicos", "Prescrições, atestados e encaminhamentos")

        tab1, tab2, tab3 = st.tabs(["💊 Prescrições", "📄 Atestados", "➡️ Encaminhamentos"])

        pacientes = db.listar_pacientes()
        nomes_pac = {p["nome"]: p["id"] for p in pacientes}
        medico_padrao = "Dr(a). Cláudia"

        # ── Prescrições ──
        with tab1:
            st.markdown("### ➕ Nova Prescrição")
            p1, p2 = st.columns(2)
            with p1:
                sel_nome = st.selectbox("Paciente *", list(nomes_pac.keys()) if nomes_pac else [""], key="presc_pac")
                presc_medico = st.selectbox("Médico *", AGENDA_MEDICOS, index=0, key="presc_medico")
                presc_data = st.date_input("Data *", value=date.today(), key="presc_data")
            with p2:
                presc_validade = st.number_input("Validade (dias)", min_value=1, max_value=90, value=10, key="presc_val")
                presc_ass = st.checkbox("Assinatura digital", value=False, key="presc_ass")
            presc_medic = st.text_area("💊 Medicamentos * (um por linha)", key="presc_medic",
                                       placeholder="Sertralina 50mg — 1 comprimido pela manhã\nClonazepam 2mg — 1 comprimido à noite")
            presc_orient = st.text_area("Orientações", key="presc_orient", placeholder="Tomar após o almoço. Não interromper sem orientação médica.")

            if st.button("💾 Salvar Prescrição", type="primary", key="presc_salvar", use_container_width=True):
                if not sel_nome or not presc_medic.strip():
                    st.error("Informe o paciente e ao menos um medicamento.")
                else:
                    ok = db.inserir_prescricao({
                        "paciente_id": nomes_pac.get(sel_nome),
                        "paciente_nome": sel_nome,
                        "medico": presc_medico,
                        "data": presc_data.strftime("%Y-%m-%d"),
                        "medicamentos": presc_medic.strip(),
                        "orientacoes": presc_orient.strip() or None,
                        "validade_dias": int(presc_validade),
                        "assinatura_digital": presc_ass,
                    })
                    if ok:
                        st.toast("Prescrição salva!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar prescrição.")

            st.markdown("---")
            st.markdown("### 🔎 Prescrições registradas")
            filtro_presc = st.text_input("Filtrar por paciente/médico", key="presc_filtro")
            prescricoes = db.listar_prescricoes(filtro=filtro_presc or None)
            if not prescricoes:
                st.info("Nenhuma prescrição encontrada.")
            else:
                df_presc = pd.DataFrame([{
                    "ID": p["id"], "Paciente": p["paciente_nome"] or "",
                    "Data": p["data"], "Médico": p["medico"],
                    "Status": p["status"], "Assinatura": "✓" if p["assinatura_digital"] else "",
                } for p in prescricoes])
                st.dataframe(df_presc, use_container_width=True, hide_index=True)

                with st.expander("📖 Ver detalhes de uma prescrição"):
                    opcoes = {f"#{p['id']} — {p['paciente_nome'] or '?'} ({p['data']})": p["id"] for p in prescricoes}
                    sel_p = st.selectbox("Prescrição", list(opcoes.keys()), key="presc_sel_det")
                    det = db.obter_prescricao(opcoes[sel_p])
                    if det:
                        st.markdown(f"**Médico:** {det['medico']}  |  **Data:** {det['data']}  |  **Validade:** {det['validade_dias']} dias")
                        st.markdown("**Medicamentos:**")
                        st.code(det["medicamentos"], language=None)
                        if det.get("orientacoes"):
                            st.markdown(f"**Orientações:** {det['orientacoes']}")
                    if st.button("🖨️ Gerar PDF da Prescrição", key=f"presc_pdf_{opcoes[sel_p]}"):
                        _gerar_prescricao_pdf(det)
                c_del1, c_del2 = st.columns(2)
                with c_del1:
                    opcoes_del = {f"#{p['id']} — {p['paciente_nome'] or '?'}": p["id"] for p in prescricoes}
                    sel_del = st.selectbox("Excluir prescrição", list(opcoes_del.keys()), key="presc_sel_del")
                    if st.button("🗑️ Excluir", key="presc_del_btn"):
                        db.excluir_prescricao(opcoes_del[sel_del])
                        st.rerun()

        # ── Atestados ──
        with tab2:
            st.markdown("### ➕ Novo Atestado")
            a1, a2 = st.columns(2)
            with a1:
                sel_nome_a = st.selectbox("Paciente *", list(nomes_pac.keys()) if nomes_pac else [""], key="atest_pac")
                atest_medico = st.selectbox("Médico *", AGENDA_MEDICOS, index=0, key="atest_medico")
                atest_data = st.date_input("Data *", value=date.today(), key="atest_data")
            with a2:
                atest_tipo = st.selectbox("Tipo", ["Atestado médico", "Atestado de comparecimento", "Atestado de aptidão", "Atestado de afastamento"], key="atest_tipo")
                atest_dias = st.number_input("Dias de afastamento", min_value=0, max_value=180, value=0, key="atest_dias")
                atest_cid = st.text_input("CID", key="atest_cid", max_chars=20, placeholder="Ex: F41.2")
            atest_diag = st.text_area("Diagnóstico / Justificativa", key="atest_diag")
            atest_orient = st.text_area("Orientações", key="atest_orient")
            atest_ass = st.checkbox("Assinatura digital", value=False, key="atest_ass")

            if st.button("💾 Emitir Atestado", type="primary", key="atest_salvar", use_container_width=True):
                if not sel_nome_a:
                    st.error("Informe o paciente.")
                else:
                    ok = db.inserir_atestado({
                        "paciente_id": nomes_pac.get(sel_nome_a),
                        "paciente_nome": sel_nome_a,
                        "medico": atest_medico,
                        "data": atest_data.strftime("%Y-%m-%d"),
                        "diagnostico": atest_diag.strip() or None,
                        "cid": atest_cid.strip() or None,
                        "dias_afastamento": int(atest_dias),
                        "tipo": atest_tipo,
                        "orientacoes": atest_orient.strip() or None,
                        "assinatura_digital": atest_ass,
                    })
                    if ok:
                        st.toast("Atestado emitido!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao emitir atestado.")

            st.markdown("---")
            st.markdown("### 🔎 Atestados registrados")
            filtro_atest = st.text_input("Filtrar por paciente/CID", key="atest_filtro")
            atestados = db.listar_atestados(filtro=filtro_atest or None)
            if not atestados:
                st.info("Nenhum atestado encontrado.")
            else:
                df_atest = pd.DataFrame([{
                    "ID": a["id"], "Paciente": a["paciente_nome"] or "",
                    "Data": a["data"], "Tipo": a["tipo"], "CID": a["cid"] or "",
                    "Dias": a["dias_afastamento"] or 0, "Médico": a["medico"],
                } for a in atestados])
                st.dataframe(df_atest, use_container_width=True, hide_index=True)
                with st.expander("📖 Ver detalhes de um atestado"):
                    opcoes_a = {f"#{a['id']} — {a['paciente_nome'] or '?'} ({a['data']})": a["id"] for a in atestados}
                    sel_a = st.selectbox("Atestado", list(opcoes_a.keys()), key="atest_sel_det")
                    det_a = db.obter_atestado(opcoes_a[sel_a])
                    if det_a:
                        st.markdown(f"**Paciente:** {det_a['paciente_nome']}  |  **Médico:** {det_a['medico']}  |  **Data:** {det_a['data']}")
                        st.markdown(f"**Tipo:** {det_a['tipo']}  |  **CID:** {det_a['cid'] or '—'}  |  **Afastamento:** {det_a['dias_afastamento'] or 0} dias")
                        if det_a.get("diagnostico"):
                            st.markdown(f"**Diagnóstico:** {det_a['diagnostico']}")
                    if st.button("🖨️ Gerar PDF do Atestado", key=f"atest_pdf_{opcoes_a[sel_a]}"):
                        _gerar_atestado_pdf(det_a)
                opcoes_del_a = {f"#{a['id']} — {a['paciente_nome'] or '?'}": a["id"] for a in atestados}
                sel_del_a = st.selectbox("Excluir atestado", list(opcoes_del_a.keys()), key="atest_sel_del")
                if st.button("🗑️ Excluir Atestado", key="atest_del_btn"):
                    db.excluir_atestado(opcoes_del_a[sel_del_a])
                    st.rerun()

        # ── Encaminhamentos ──
        with tab3:
            st.markdown("### ➕ Novo Encaminhamento")
            e1, e2 = st.columns(2)
            with e1:
                sel_nome_e = st.selectbox("Paciente *", list(nomes_pac.keys()) if nomes_pac else [""], key="enc_pac")
                enc_medico = st.selectbox("Médico *", AGENDA_MEDICOS, index=0, key="enc_medico")
                enc_data = st.date_input("Data *", value=date.today(), key="enc_data")
            with e2:
                enc_esp = st.text_input("Especialidade *", key="enc_esp", placeholder="Ex: Psiquiatria")
                enc_dest = st.text_input("Profissional de destino", key="enc_dest", placeholder="Ex: Dr. João Psiquiatra")
                enc_urg = st.checkbox("⚠️ Urgente", value=False, key="enc_urg")
                enc_ret = st.checkbox("Solicitar relatório de retorno", value=False, key="enc_ret")
            enc_motivo = st.text_area("Motivo do encaminhamento", key="enc_motivo")

            if st.button("💾 Emitir Encaminhamento", type="primary", key="enc_salvar", use_container_width=True):
                if not sel_nome_e or not enc_esp.strip():
                    st.error("Informe o paciente e a especialidade.")
                else:
                    ok = db.inserir_encaminhamento({
                        "paciente_id": nomes_pac.get(sel_nome_e),
                        "paciente_nome": sel_nome_e,
                        "medico": enc_medico,
                        "data": enc_data.strftime("%Y-%m-%d"),
                        "especialidade": enc_esp.strip(),
                        "profissional_destino": enc_dest.strip() or None,
                        "motivo": enc_motivo.strip() or None,
                        "urgente": enc_urg,
                        "retorno_relatorio": enc_ret,
                    })
                    if ok:
                        st.toast("Encaminhamento emitido!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao emitir encaminhamento.")

            st.markdown("---")
            st.markdown("### 🔎 Encaminhamentos registrados")
            filtro_enc = st.text_input("Filtrar por paciente/especialidade", key="enc_filtro")
            encaminhamentos = db.listar_encaminhamentos(filtro=filtro_enc or None)
            if not encaminhamentos:
                st.info("Nenhum encaminhamento encontrado.")
            else:
                df_enc = pd.DataFrame([{
                    "ID": e["id"], "Paciente": e["paciente_nome"] or "",
                    "Data": e["data"], "Especialidade": e["especialidade"],
                    "Destino": e["profissional_destino"] or "", "Urgente": "⚠️" if e["urgente"] else "",
                    "Status": e["status"],
                } for e in encaminhamentos])
                st.dataframe(df_enc, use_container_width=True, hide_index=True)
                with st.expander("📖 Ver detalhes de um encaminhamento"):
                    opcoes_e = {f"#{e['id']} — {e['paciente_nome'] or '?'} ({e['data']})": e["id"] for e in encaminhamentos}
                    sel_e = st.selectbox("Encaminhamento", list(opcoes_e.keys()), key="enc_sel_det")
                    det_e = db.obter_encaminhamento(opcoes_e[sel_e])
                    if det_e:
                        st.markdown(f"**Paciente:** {det_e['paciente_nome']}  |  **Médico:** {det_e['medico']}  |  **Data:** {det_e['data']}")
                        st.markdown(f"**Especialidade:** {det_e['especialidade']}  |  **Destino:** {det_e['profissional_destino'] or '—'}")
                        if det_e.get("motivo"):
                            st.markdown(f"**Motivo:** {det_e['motivo']}")
                    if st.button("🖨️ Gerar PDF do Encaminhamento", key=f"enc_pdf_{opcoes_e[sel_e]}"):
                        _gerar_encaminhamento_pdf(det_e)
                opcoes_del_e = {f"#{e['id']} — {e['paciente_nome'] or '?'}": e["id"] for e in encaminhamentos}
                sel_del_e = st.selectbox("Excluir encaminhamento", list(opcoes_del_e.keys()), key="enc_sel_del")
                if st.button("🗑️ Excluir Encaminhamento", key="enc_del_btn"):
                    db.excluir_encaminhamento(opcoes_del_e[sel_del_e])
                    st.rerun()


def _gerar_prescricao_pdf(presc: dict) -> None:
    """Gera PDF de prescrição usando fpdf2."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "PRESCRIÇÃO MÉDICA", ln=True, align="C")
        pdf.ln(4)
        pdf.set_draw_color(77, 167, 104)
        pdf.set_line_width(0.8)
        pdf.line(10, 26, 200, 26)
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"Paciente: {presc.get('paciente_nome') or 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Médico: {presc.get('medico') or ''}", ln=True)
        pdf.cell(0, 7, f"Data: {presc.get('data')}", ln=True)
        pdf.cell(0, 7, f"Validade: {presc.get('validade_dias')} dias", ln=True)
        if presc.get("assinatura_digital"):
            pdf.cell(0, 7, "Assinatura digital: SIM", ln=True)
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Medicamentos:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, presc.get("medicamentos") or "")
        if presc.get("orientacoes"):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Orientações:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, presc.get("orientacoes"))
        pdf.ln(12)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"___________________________", ln=True, align="C")
        pdf.cell(0, 7, presc.get("medico") or "", ln=True, align="C")
        pdf.cell(0, 7, "Assinatura", ln=True, align="C")
        _baixar_pdf_streamlit(pdf, f"prescricao_{presc.get('id', '')}.pdf")
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")


def _gerar_atestado_pdf(atest: dict) -> None:
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "ATESTADO MÉDICO", ln=True, align="C")
        pdf.ln(4)
        pdf.set_draw_color(77, 167, 104)
        pdf.set_line_width(0.8)
        pdf.line(10, 26, 200, 26)
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"Paciente: {atest.get('paciente_nome') or 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Médico: {atest.get('medico') or ''}", ln=True)
        pdf.cell(0, 7, f"Data: {atest.get('data')}", ln=True)
        pdf.cell(0, 7, f"Tipo: {atest.get('tipo') or 'Atestado médico'}", ln=True)
        pdf.cell(0, 7, f"CID: {atest.get('cid') or '—'}  |  Afastamento: {atest.get('dias_afastamento') or 0} dias", ln=True)
        if atest.get("assinatura_digital"):
            pdf.cell(0, 7, "Assinatura digital: SIM", ln=True)
        pdf.ln(4)
        if atest.get("diagnostico"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Diagnóstico / Justificativa:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, atest["diagnostico"])
        if atest.get("orientacoes"):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Orientações:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, atest["orientacoes"])
        pdf.ln(12)
        pdf.cell(0, 7, "___________________________", ln=True, align="C")
        pdf.cell(0, 7, atest.get("medico") or "", ln=True, align="C")
        pdf.cell(0, 7, "Assinatura", ln=True, align="C")
        _baixar_pdf_streamlit(pdf, f"atestado_{atest.get('id', '')}.pdf")
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")


def _gerar_encaminhamento_pdf(enc: dict) -> None:
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "ENCAMINHAMENTO MÉDICO", ln=True, align="C")
        pdf.ln(4)
        pdf.set_draw_color(77, 167, 104)
        pdf.set_line_width(0.8)
        pdf.line(10, 26, 200, 26)
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"Paciente: {enc.get('paciente_nome') or 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Médico: {enc.get('medico') or ''}", ln=True)
        pdf.cell(0, 7, f"Data: {enc.get('data')}", ln=True)
        pdf.cell(0, 7, f"Especialidade: {enc.get('especialidade') or ''}", ln=True)
        pdf.cell(0, 7, f"Profissional de destino: {enc.get('profissional_destino') or '—'}", ln=True)
        if enc.get("urgente"):
            pdf.cell(0, 7, "URGENTE", ln=True)
        pdf.ln(4)
        if enc.get("motivo"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Motivo:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, enc["motivo"])
        pdf.ln(12)
        pdf.cell(0, 7, "___________________________", ln=True, align="C")
        pdf.cell(0, 7, enc.get("medico") or "", ln=True, align="C")
        pdf.cell(0, 7, "Assinatura", ln=True, align="C")
        _baixar_pdf_streamlit(pdf, f"encaminhamento_{enc.get('id', '')}.pdf")
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")


def _baixar_pdf_streamlit(pdf: FPDF, nome_arquivo: str) -> None:
    """Dispara download do PDF gerado (buffer em memória)."""
    import io as _io
    buffer = _io.BytesIO()
    pdf.output(buffer)
    st.download_button(
        label=f"⬇️ Baixar {nome_arquivo}",
        data=buffer.getvalue(),
        file_name=nome_arquivo,
        mime="application/pdf",
    )

class CompaniesPage:
    @staticmethod
    def render() -> None:
        render_page_header("🏢 Empresas", "Cadastro, convênios, contratos e faturamento")

        # ── Alertas de contrato vencendo ──
        try:
            vencendo = db.listar_empresas_com_contrato_vencendo(30)
            if vencendo:
                for v in vencendo:
                    venc = v.get("validade_contrato")
                    st.warning(f"⚠️ Contrato de {v['nome']} {'venceu' if venc and venc < date.today() else 'vence em'} {venc}")
        except Exception:
            pass

        tab1, tab2, tab3, tab4 = st.tabs(["🔍 Empresas", "➕ Nova Empresa", "📋 Convênios", "💰 Faturamento"])

        with tab1:
            st.markdown("### 🔎 Buscar Empresas")
            col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
            with col_f1:
                busca = st.text_input("Buscar por Nome, CNPJ, Razão Social ou E-mail", key="emp_busca")
            with col_f2:
                so_ativas = st.checkbox("Somente ativas", value=False, key="emp_ativas")
            with col_f3:
                st.markdown("&nbsp;")
                if st.button("🔍 Buscar", key="emp_buscar_btn", use_container_width=True):
                    pass

            empresas = db.listar_empresas(busca or None, ativas_apenas=so_ativas)
            if not empresas:
                st.info("Nenhuma empresa encontrada.")
            else:
                df_emp = pd.DataFrame([{
                    "ID": e["id"],
                    "Nome": e["nome"],
                    "CNPJ": e["cnpj"] or "",
                    "Responsável": e["responsavel"] or "",
                    "Telefone": e["telefone"] or "",
                    "Funcionários": e["quantidade_funcionarios"] or 0,
                    "Plano": e["plano"] or "",
                    "Contrato": e["validade_contrato"] or "",
                    "Status": "Ativa" if e["ativo"] else "Inativa",
                } for e in empresas])
                st.dataframe(df_emp, use_container_width=True, hide_index=True, height=320)
                st.caption(f"{len(empresas)} empresa(s) encontrada(s). Gerencie convênios e faturamento nas abas ao lado.")

        with tab2:
            st.markdown("### ➕ Cadastrar Nova Empresa")
            c1, c2 = st.columns(2)
            with c1:
                e_nome = st.text_input("Nome da empresa *", key="ne_nome", max_chars=255)
                e_cnpj = st.text_input("CNPJ", key="ne_cnpj", max_chars=30)
                e_razao = st.text_input("Razão social", key="ne_razao", max_chars=255)
                e_resp = st.text_input("Responsável legal", key="ne_resp", max_chars=255)
            with c2:
                e_tel = st.text_input("Telefone", key="ne_tel", max_chars=30)
                e_email = st.text_input("E-mail", key="ne_email", max_chars=255)
                e_end = st.text_input("Endereço", key="ne_end", max_chars=255)
                e_qtd = st.number_input("Quantidade de funcionários", min_value=0, step=1, value=0, key="ne_qtd")
            c3, c4 = st.columns(2)
            with c3:
                e_plano = st.text_input("Plano", key="ne_plano", max_chars=100, placeholder="Ex: Básico, Completo")
                e_dt_contrato = st.date_input("Data do contrato", value=None, key="ne_dt_contrato")
            with c4:
                e_vl_contrato = st.date_input("Validade do contrato", value=None, key="ne_vl_contrato")
            e_obs = st.text_area("Observações", key="ne_obs", max_chars=2000)

            if st.button("💾 Salvar Empresa", type="primary", key="ne_salvar", use_container_width=True):
                if not e_nome.strip():
                    st.error("Preencha o campo Nome da empresa (obrigatório).")
                else:
                    duplicados = db.buscar_empresas_duplicadas(e_nome, e_cnpj)
                    if duplicados:
                        st.warning("⚠️ Possível duplicidade de cadastro encontrada:")
                        for d in duplicados:
                            st.warning(f"  • #{d['id']} — {d['nome']} ({d.get('cnpj') or 'sem CNPJ'})")
                        st.error("Cadastro não realizado. Verifique se a empresa já existe.")
                    else:
                        dados = {
                            "nome": e_nome.strip(),
                            "cnpj": e_cnpj.strip() or None,
                            "razao_social": e_razao.strip() or None,
                            "endereco": e_end.strip() or None,
                            "telefone": e_tel.strip() or None,
                            "email": e_email.strip() or None,
                            "responsavel": e_resp.strip() or None,
                            "quantidade_funcionarios": int(e_qtd),
                            "plano": e_plano.strip() or None,
                            "data_contrato": e_dt_contrato,
                            "validade_contrato": e_vl_contrato,
                            "observacoes": e_obs.strip() or None,
                            "ativo": True,
                        }
                        novo_id = db.inserir_empresa(dados)
                        if novo_id:
                            st.toast("Empresa cadastrada com sucesso!", icon="✅")
                            security.log_access("ADD_EMPRESA", e_nome.strip())
                            st.rerun()
                        else:
                            st.error("Erro ao cadastrar empresa.")

        with tab3:
            st.markdown("### 📋 Convênios por Empresa")
            empresas_todas = db.listar_empresas()
            if not empresas_todas:
                st.info("Cadastre empresas na aba ➕ Nova Empresa.")
            else:
                opcoes = {f"#{e['id']} — {e['nome']}": e["id"] for e in empresas_todas}
                sel = st.selectbox("Selecione a empresa", list(opcoes.keys()), key="conv_sel_emp")
                eid = opcoes[sel]

                st.markdown("#### ➕ Adicionar Convênio")
                cc1, cc2 = st.columns(2)
                with cc1:
                    c_op = st.text_input("Operadora", key=f"conv_op_{eid}", max_chars=255, placeholder="Ex: Unimed")
                    c_num = st.text_input("Número da carteira", key=f"conv_num_{eid}", max_chars=100)
                with cc2:
                    c_val = st.date_input("Validade", value=None, key=f"conv_val_{eid}")
                c_obs = st.text_input("Observações", key=f"conv_obs_{eid}")
                if st.button("➕ Salvar Convênio", type="primary", key=f"conv_add_{eid}"):
                    if not c_op.strip():
                        st.error("Informe a operadora.")
                    else:
                        ok = db.inserir_convenio(eid, {
                            "operadora": c_op.strip(), "numero_carteira": c_num.strip() or None,
                            "validade": c_val, "observacoes": c_obs.strip() or None,
                        })
                        if ok:
                            st.toast("Convênio adicionado!", icon="✅")
                            st.rerun()
                        else:
                            st.error("Erro ao salvar convênio.")

                convenios = db.listar_convenios(eid)
                if not convenios:
                    st.info("Nenhum convênio cadastrado para esta empresa.")
                else:
                    df_conv = pd.DataFrame([{
                        "Operadora": c["operadora"],
                        "Nº Carteira": c["numero_carteira"] or "",
                        "Validade": c["validade"] or "",
                        "Obs": c["observacoes"] or "",
                    } for c in convenios])
                    st.dataframe(df_conv, use_container_width=True, hide_index=True)
                    for c in convenios:
                        if st.button(f"🗑️ Excluir {c['operadora']}", key=f"conv_del_{c['id']}"):
                            db.excluir_convenio(c["id"])
                            st.rerun()

        with tab4:
            st.markdown("### 💰 Faturamento por Empresa")
            empresas_todas = db.listar_empresas()
            if not empresas_todas:
                st.info("Cadastre empresas na aba ➕ Nova Empresa.")
            else:
                opcoes = {f"#{e['id']} — {e['nome']}": e["id"] for e in empresas_todas}
                sel = st.selectbox("Selecione a empresa", list(opcoes.keys()), key="fat_sel_emp")
                eid = opcoes[sel]
                emp = db.obter_empresa(eid)

                total_atts = db.contar_atendimentos_empresa(emp["nome"]) if emp else 0
                st.info(f"📊 **{emp['nome']}** — Total de atendimentos registrados: **{total_atts}**")

                st.markdown("#### ➕ Lançar Faturamento")
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    f_ano = st.selectbox("Ano", list(range(date.today().year, date.today().year - 3, -1)), key=f"fat_ano_{eid}")
                with fc2:
                    f_mes = st.selectbox("Mês", list(range(1, 13)), format_func=lambda m: f"{m:02d}", key=f"fat_mes_{eid}")
                with fc3:
                    f_valor = st.number_input("Valor total (R$)", min_value=0.0, step=100.0, value=0.0, key=f"fat_valor_{eid}")
                f_qtd = st.number_input("Quantidade de atendimentos", min_value=0, step=1, value=total_atts, key=f"fat_qtd_{eid}")
                f_obs = st.text_input("Observações", key=f"fat_obs_{eid}")
                if st.button("💾 Salvar Faturamento", type="primary", key=f"fat_save_{eid}"):
                    ok = db.salvar_faturamento_empresa(eid, f_mes, f_ano, f_valor, int(f_qtd), f_obs.strip() or None)
                    if ok:
                        st.toast("Faturamento salvo!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar faturamento.")

                faturas = db.listar_faturamento_empresa(eid, f_ano)
                if faturas:
                    df_fat = pd.DataFrame([{
                        "Mês": f"{f['mes']:02d}/{f['ano']}",
                        "Valor (R$)": float(f["valor_total"] or 0),
                        "Atendimentos": f["quantidade_atendimentos"] or 0,
                        "Obs": f["observacoes"] or "",
                    } for f in faturas])
                    st.dataframe(df_fat, use_container_width=True, hide_index=True)
                    total_fat = sum(float(f["valor_total"] or 0) for f in faturas)
                    st.success(f"💰 Total lançado no ano {f_ano}: **R$ {total_fat:,.2f}**")

class PatientsPage:
    @staticmethod
    def render() -> None:
        render_page_header("👥 Pacientes", "Prontuário eletrônico, anamnese e evolução clínica")

        # ── Alertas de aniversário ──
        try:
            aniversariantes = db.listar_aniversariantes(date.today().day, date.today().month)
            if aniversariantes:
                nomes = ", ".join([a["nome"] for a in aniversariantes])
                st.success(f"🎂 Aniversariantes de hoje: {nomes}")
        except Exception:
            pass

        tab1, tab2, tab3 = st.tabs(["🔍 Consultar", "➕ Novo Paciente", "📂 Prontuário"])

        with tab1:
            st.markdown("### 🔎 Buscar Pacientes")
            col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
            with col_f1:
                busca = st.text_input("Buscar por Nome, CPF, Telefone ou E-mail", key="pac_busca")
            with col_f2:
                so_ativos = st.checkbox("Somente ativos", value=False, key="pac_ativos")
            with col_f3:
                st.markdown("&nbsp;")
                if st.button("🔍 Buscar", key="pac_buscar_btn", use_container_width=True):
                    pass

            pacientes = db.listar_pacientes(busca or None, ativos_apenas=so_ativos)
            if not pacientes:
                st.info("Nenhum paciente encontrado.")
            else:
                df_pac = pd.DataFrame([{
                    "ID": p["id"],
                    "Nome": p["nome"],
                    "CPF": p["cpf"] or "",
                    "Telefone": p["telefone"] or "",
                    "E-mail": p["email"] or "",
                    "Status": "Ativo" if p["ativo"] else "Inativo",
                } for p in pacientes])
                st.dataframe(df_pac, use_container_width=True, hide_index=True, height=320)
                st.caption(f"{len(pacientes)} paciente(s) encontrado(s). Selecione na aba Prontuário para ver o prontuário completo.")

        with tab2:
            st.markdown("### ➕ Cadastrar Novo Paciente")
            c1, c2 = st.columns(2)
            with c1:
                p_nome = st.text_input("Nome completo *", key="np_nome", max_chars=255)
                p_cpf = st.text_input("CPF", key="np_cpf", max_chars=20)
                p_rg = st.text_input("RG", key="np_rg", max_chars=30)
                p_data_nasc = st.date_input("Data de nascimento", value=None, key="np_dt_nasc", min_value=date(1900, 1, 1), max_value=date.today())
            with c2:
                p_tel = st.text_input("Telefone", key="np_tel", max_chars=30)
                p_email = st.text_input("E-mail", key="np_email", max_chars=255)
                p_end = st.text_input("Endereço", key="np_end", max_chars=255)
            p_obs = st.text_area("Observações", key="np_obs", max_chars=2000)

            if st.button("💾 Salvar Paciente", type="primary", key="np_salvar", use_container_width=True):
                if not p_nome.strip():
                    st.error("Preencha o campo Nome completo (obrigatório).")
                else:
                    duplicados = db.buscar_pacientes_duplicados(p_nome, p_cpf)
                    if duplicados:
                        st.warning("⚠️ Possível duplicidade de cadastro encontrada:")
                        for d in duplicados:
                            st.warning(f"  • #{d['id']} — {d['nome']} ({d.get('telefone') or 'sem telefone'})")
                        st.error("Cadastro não realizado. Verifique se o paciente já existe.")
                    else:
                        dados = {
                            "nome": p_nome.strip(),
                            "cpf": p_cpf.strip() or None,
                            "rg": p_rg.strip() or None,
                            "data_nascimento": p_data_nasc,
                            "telefone": p_tel.strip() or None,
                            "email": p_email.strip() or None,
                            "endereco": p_end.strip() or None,
                            "observacoes": p_obs.strip() or None,
                            "ativo": True,
                        }
                        novo_id = db.inserir_paciente(dados)
                        if novo_id:
                            st.toast("Paciente cadastrado com sucesso!", icon="✅")
                            security.log_access("ADD_PACIENTE", p_nome.strip())
                            st.rerun()
                        else:
                            st.error("Erro ao cadastrar paciente. Verifique os dados e tente novamente.")

        with tab3:
            st.markdown("### 📂 Prontuário do Paciente")
            pacientes_todos = db.listar_pacientes()
            if not pacientes_todos:
                st.info("Cadastre pacientes na aba ➕ Novo Paciente.")
                return

            opcoes = {f"#{p['id']} — {p['nome']}": p["id"] for p in pacientes_todos}
            sel = st.selectbox("Selecione o paciente", list(opcoes.keys()), key="pac_sel_pront")
            pid = opcoes[sel]
            pac = db.obter_paciente(pid)
            if not pac:
                st.error("Paciente não encontrado.")
                return

            col_p1, col_p2 = st.columns([1, 3])
            with col_p1:
                if pac.get("foto_b64"):
                    st.markdown(
                        f"<img src='data:{pac.get('foto_mime') or 'image/jpeg'};base64,{pac['foto_b64']}' style='width:140px;height:140px;border-radius:50%;object-fit:cover;'/>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown("<div style='width:140px;height:140px;border-radius:50%;background:#1E5631;display:flex;align-items:center;justify-content:center;font-size:60px;'>👤</div>", unsafe_allow_html=True)
                up_foto = st.file_uploader("Foto", type=["jpg", "jpeg", "png", "webp"], key=f"pac_foto_{pid}")
                if up_foto:
                    fb = up_foto.getvalue()
                    if len(fb) > 2 * 1024 * 1024:
                        st.error("❌ Máx 2MB")
                    else:
                        b64 = base64.b64encode(fb).decode("utf-8")
                        db.salvar_foto_paciente(pid, b64, up_foto.type or "image/jpeg")
                        st.toast("Foto atualizada!", icon="✅")
                        st.rerun()
            with col_p2:
                st.markdown(f"### {pac['nome']}")
                dt_nasc = pac.get("data_nascimento")
                idade = ""
                if dt_nasc:
                    try:
                        n = pd.to_datetime(str(dt_nasc)).date()
                        idade = f"{int((date.today() - n).days / 365.25)} anos"
                    except Exception:
                        idade = ""
                st.markdown(
                    f"**CPF:** {pac.get('cpf') or '—'} | **RG:** {pac.get('rg') or '—'} | **Nasc.:** {dt_nasc or '—'} ({idade})\n\n"
                    f"**Telefone:** {pac.get('telefone') or '—'} | **E-mail:** {pac.get('email') or '—'}\n\n"
                    f"**Endereço:** {pac.get('endereco') or '—'}\n\n"
                    f"**Status:** {'🟢 Ativo' if pac.get('ativo') else '🔴 Inativo'}"
                )

            st.divider()
            sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📋 Anamnese", "🩺 Evolução Clínica", "📅 Histórico de Atendimentos"])

            with sub_tab1:
                anam = db.obter_anamnese(pid)
                st.markdown("### 📋 Anamnese Digital")
                aq = st.text_area("Queixa principal", value=(anam or {}).get("queixa_principal") or "", key=f"ana_q_{pid}")
                ahd = st.text_area("Histórico da doença atual", value=(anam or {}).get("historico_doenca") or "", key=f"ana_hd_{pid}")
                ahf = st.text_area("Histórico familiar", value=(anam or {}).get("historico_familiar") or "", key=f"ana_hf_{pid}")
                amd = st.text_area("Medicamentos em uso", value=(anam or {}).get("medicamentos") or "", key=f"ana_md_{pid}")
                aal = st.text_area("Alergias", value=(anam or {}).get("alergias") or "", key=f"ana_al_{pid}")
                ahab = st.text_area("Hábitos", value=(anam or {}).get("habitos") or "", key=f"ana_hb_{pid}")
                aobs = st.text_area("Observações", value=(anam or {}).get("observacoes") or "", key=f"ana_obs_{pid}")
                if st.button("💾 Salvar Anamnese", type="primary", key=f"ana_save_{pid}"):
                    dados_anam = {
                        "queixa_principal": aq, "historico_doenca": ahd, "historico_familiar": ahf,
                        "medicamentos": amd, "alergias": aal, "habitos": ahab, "observacoes": aobs,
                    }
                    if db.salvar_ou_atualizar_anamnese(pid, dados_anam):
                        st.toast("Anamnese salva!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar anamnese.")

            with sub_tab2:
                st.markdown("### 🩺 Evolução Clínica")
                ev_data = st.date_input("Data", value=date.today(), key=f"ev_data_{pid}")
                ev_texto = st.text_area("Registro da evolução", key=f"ev_texto_{pid}", height=150)
                if st.button("➕ Adicionar Evolução", type="primary", key=f"ev_add_{pid}"):
                    if not ev_texto.strip():
                        st.warning("Escreva o texto da evolução.")
                    elif db.inserir_evolucao(pid, ev_data, ev_texto.strip()):
                        st.toast("Evolução registrada!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao registrar evolução.")

                evolucoes = db.listar_evolucoes(pid)
                if not evolucoes:
                    st.info("Nenhuma evolução registrada ainda.")
                else:
                    for ev in evolucoes:
                        with st.container(border=True):
                            st.markdown(f"**{ev['data']}**")
                            st.write(ev["texto"])
                            if st.button("🗑️ Excluir", key=f"ev_del_{ev['id']}"):
                                db.excluir_evolucao(ev["id"])
                                st.rerun()

            with sub_tab3:
                st.markdown("### 📅 Histórico de Atendimentos")
                atts = db.listar_atendimentos_do_paciente(pid)
                if not atts:
                    st.info("Nenhum atendimento vinculado a este paciente.")
                else:
                    df_atts = pd.DataFrame(atts, columns=[
                        "ID", "Empresa", "Nome", "Modalidade", "Data", "Hora",
                        "Laudo PDF", "Avaliação PDF", "Status", "Observações",
                    ])
                    st.dataframe(df_atts[["ID", "Empresa", "Modalidade", "Data", "Hora", "Status"]], use_container_width=True, hide_index=True)
                    st.caption(f"Total: {len(atts)} atendimento(s).")

            st.divider()
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                if st.button("✏️ Editar Dados", key=f"pac_edit_{pid}", use_container_width=True):
                    st.session_state[f"edit_pac_{pid}"] = True
            with ac2:
                novo_status = 0 if pac.get("ativo") else 1
                if st.button("🔄 Ativar/Inativar", key=f"pac_status_{pid}", use_container_width=True):
                    db.atualizar_paciente(pid, {"ativo": novo_status})
                    st.rerun()
            with ac3:
                if st.button("🗑️ Excluir Paciente", key=f"pac_del_{pid}", use_container_width=True):
                    if db.excluir_paciente(pid):
                        st.toast("Paciente excluído!", icon="🗑️")
                        st.rerun()
                    else:
                        st.error("Erro ao excluir paciente.")

            if st.session_state.get(f"edit_pac_{pid}"):
                st.markdown("### ✏️ Editar Dados do Paciente")
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_nome = st.text_input("Nome completo", value=pac["nome"], key=f"ep_nome_{pid}")
                    e_cpf = st.text_input("CPF", value=pac.get("cpf") or "", key=f"ep_cpf_{pid}")
                    e_rg = st.text_input("RG", value=pac.get("rg") or "", key=f"ep_rg_{pid}")
                with ec2:
                    e_tel = st.text_input("Telefone", value=pac.get("telefone") or "", key=f"ep_tel_{pid}")
                    e_email = st.text_input("E-mail", value=pac.get("email") or "", key=f"ep_email_{pid}")
                    e_end = st.text_input("Endereço", value=pac.get("endereco") or "", key=f"ep_end_{pid}")
                e_obs = st.text_area("Observações", value=pac.get("observacoes") or "", key=f"ep_obs_{pid}")
                if st.button("💾 Salvar Alterações", type="primary", key=f"ep_save_{pid}"):
                    dados_upd = {
                        "nome": e_nome.strip(), "cpf": e_cpf.strip() or None,
                        "rg": e_rg.strip() or None, "telefone": e_tel.strip() or None,
                        "email": e_email.strip() or None, "endereco": e_end.strip() or None,
                        "observacoes": e_obs.strip() or None,
                    }
                    if db.atualizar_paciente(pid, dados_upd):
                        st.session_state[f"edit_pac_{pid}"] = False
                        st.toast("Alterações salvas!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar alterações.")

class SettingsPage:
    @staticmethod
    def render() -> None:
        render_page_header("⚙️ Configurações", "Administração do Sistema")

        # CSS Local para Configurações (Apenas o estilo, sem injeção de script)

        st.markdown(
            """
<style>
/* Usar body.page-settings para ter mais especificidade e garantir override do estilo global */
.page-settings .stButton>button {
    background: linear-gradient(90deg, #4DA768 0%, #2ecc71 100%) !important;
    color: #ffffff !important;
    border: none !important;
}
.page-settings .stButton>button:hover { opacity: 0.95 !important; transform: translateY(-1px) !important; background: linear-gradient(90deg, rgba(77,167,120,0.14) 0%, rgba(58,158,95,0.14) 100%) !important; }
.page-settings .stJson, .page-settings pre {
    background: #f6fbf7 !important; /* tom suave compatível */
    border-radius: 8px !important;
    color: #4DA768 !important;
}
.page-settings .stSuccess, .page-settings .stSuccess>div { background: rgba(77,167,120,0.08) !important; color: #4DA768 !important; }
.page-settings .stError, .page-settings .stError>div { background: rgba(223,50,80,0.06) !important; }
/* Garantir que os cards também usem hover verde dentro da página de configurações */
.page-settings .stMetric:hover {
    box-shadow: 0 4px 18px rgba(44,62,80,0.13) !important;
    background: linear-gradient(135deg, rgba(77,167,120,0.12) 0%, rgba(255,255,255,0.0) 100%) !important;
}
</style>
""",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.subheader("🛠️ Painel de Controle")

        conn_ok = verificar_conexao()
        stats = DatabaseManager.get_statistics()
        cards = [
            {"icon": "🗄️", "title": "Banco de Dados", "value": "Conectado" if conn_ok else "Offline"},
            {"icon": "🐘", "title": "Postgres", "value": "Ativo"},
            {"icon": "📋", "title": "Atendimentos", "value": stats.get("total_atendimentos", 0)},
        ]

        display_cards(cards)

        st.markdown("### 🎨 Personalização Visual")
        st.markdown("#### ✨ Temas Premium (1 clique)")
        st.caption("Escolha uma paleta pronta para mudar toda a identidade visual do sistema.")
        theme_names = list(PREMIUM_THEMES.keys())
        current_theme = st.session_state.get('premium_theme', '')
        theme_sel = st.pills(
            "Tema",
            options=theme_names,
            default=None,
            key="theme_pills",
            selection_mode="single",
        )
        if theme_sel and theme_sel != current_theme:
            t = PREMIUM_THEMES[theme_sel]
            st.session_state['premium_theme'] = theme_sel
            st.session_state['accent_color'] = t['accent']
            st.session_state['main_bg_color'] = t['bg']
            st.session_state['card_bg_hex'] = t['card_bg']
            st.session_state['card_text_color'] = t['card_text']
            db.save_preference('premium_theme', theme_sel)
            for k, v in [('accent_color', t['accent']), ('main_bg_color', t['bg']),
                         ('card_bg_hex', t['card_bg']), ('card_text_color', t['card_text'])]:
                db.save_preference(k, v)
            st.rerun()
        if current_theme:
            st.success(f"🎨 Tema ativo: **{current_theme}**")

        ui_col1, ui_col2 = st.columns(2)
        with ui_col1:
            dm = st.toggle("Ativar Tema Dark Ultra-Premium 🌙", value=st.session_state.get('premium_dark_mode', False), key="dm_toggle")
            if dm != st.session_state.get('premium_dark_mode', False):
                st.session_state['premium_dark_mode'] = dm
                db.save_preference('premium_dark_mode', 'true' if dm else 'false')
                st.rerun()
        
        st.write("---")
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Cores do Sistema")
            accent_color = st.color_picker("Barra Lateral e Botões", value=st.session_state.get('accent_color', '#4DA768'))
            if accent_color != st.session_state.get('accent_color', '#4DA768'):
                st.session_state['accent_color'] = accent_color
                db.save_preference('accent_color', accent_color)
                st.rerun()
            
            main_bg = st.color_picker("Fundo Principal do App", value=st.session_state.get('main_bg_color', '#73C883'))
            if main_bg != st.session_state.get('main_bg_color', '#73C883'):
                st.session_state['main_bg_color'] = main_bg
                db.save_preference('main_bg_color', main_bg)
                st.rerun()
        
        with c2:
            st.caption("Cores dos Cards")
            card_bg_hex = st.color_picker("Fundo dos Cards", value=st.session_state.get('card_bg_hex', '#ffffff'))
            if card_bg_hex != st.session_state.get('card_bg_hex', '#ffffff'):
                st.session_state['card_bg_hex'] = card_bg_hex
                db.save_preference('card_bg_hex', card_bg_hex)
                st.rerun()
                
            card_txt = st.color_picker("Texto dos Cards", value=st.session_state.get('card_text_color', '#ffffff'))
            if card_txt != st.session_state.get('card_text_color', '#ffffff'):
                st.session_state['card_text_color'] = card_txt
                db.save_preference('card_text_color', card_txt)
                st.rerun()
        
        if st.button("🔄 Resetar Cores Padrão"):
            st.session_state['premium_theme'] = ''
            st.session_state['accent_color'] = '#4DA768'
            st.session_state['card_text_color'] = '#ffffff'
            st.session_state['main_bg_color'] = '#73C883'
            st.session_state['card_bg_hex'] = '#ffffff'
            st.session_state['premium_dark_mode'] = False
            # Limpar do banco
            for key in ['accent_color', 'card_text_color', 'main_bg_color', 'card_bg_hex', 'premium_dark_mode', 'premium_theme']:
                db.delete_preference(key)
            st.rerun()
        
        st.write("---")
        st.markdown("### 📷 Foto de Perfil")
        st.caption("Essa foto aparecerá no card da barra lateral.")
        
        photo_col1, photo_col2 = st.columns([1, 2])
        with photo_col1:
            # Preview da foto atual
            if st.session_state.get('profile_photo_b64'):
                st.markdown(
                    f"""<div style='width:80px;height:80px;border-radius:50%;
                    overflow:hidden;border:3px solid rgba(255,255,255,0.4);
                    box-shadow:0 4px 16px rgba(0,0,0,0.2);'>
                    <img src='data:image/jpeg;base64,{st.session_state['profile_photo_b64']}'
                    style='width:100%;height:100%;object-fit:cover;'/></div>""",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    """<div style='width:80px;height:80px;border-radius:50%;
                    background:rgba(255,255,255,0.15);border:3px solid rgba(255,255,255,0.3);
                    display:flex;align-items:center;justify-content:center;
                    font-size:32px;'>&#128100;</div>""",
                    unsafe_allow_html=True
                )
        with photo_col2:
            uploaded_photo = st.file_uploader(
                "Escolher foto",
                type=["jpg", "jpeg", "png", "webp"],
                key="profile_photo_upload",
                label_visibility="collapsed"
            )
            if uploaded_photo:
                photo_bytes = uploaded_photo.getvalue()
                if len(photo_bytes) > 2 * 1024 * 1024:
                    st.error("❌ Foto muito grande. Máximo: 2MB.")
                else:
                    b64_photo = base64.b64encode(photo_bytes).decode('utf-8')
                    mime = uploaded_photo.type or 'image/jpeg'
                    # Salva na sessão
                    st.session_state['profile_photo_b64'] = b64_photo
                    st.session_state['profile_photo_mime'] = mime
                    # Salva permanentemente no banco
                    try:
                        db.save_preference('profile_photo_b64', b64_photo)
                        db.save_preference('profile_photo_mime', mime)
                        st.toast("Foto salva com sucesso!", icon="✅")
                    except Exception:
                        st.toast("Foto atualizada (apenas nesta sessão).", icon="⚠️")
                    st.rerun()
            if st.session_state.get('profile_photo_b64'):
                if st.button("🗑️ Remover foto", key="remove_photo_btn"):
                    st.session_state.pop('profile_photo_b64', None)
                    st.session_state.pop('profile_photo_mime', None)
                    try:
                        db.delete_preference('profile_photo_b64')
                        db.delete_preference('profile_photo_mime')
                    except Exception:
                        pass
                    st.rerun()

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            if st.button("🧹 Limpar Cache"):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.success("Cache limpo!")

        with col2:
            if st.button("🩺 Verificar Banco"):
                if verificar_conexao():
                    st.success("Conexão com banco OK!")
                else:
                    st.error("Falha na conexão com o banco.")

        with col3:
            if st.button("♻️ Reinicializar DB"):
                if DatabaseManager.initialize_database(force=True):
                    st.success("Banco reinicializado!")
                else:
                    st.error("Erro ao reinicializar banco.")

        with col4:
            if st.button("📊 Estatísticas"):
                st.json(stats)

        with col5:
            if st.button("🔎 Diagnóstico"):
                try:
                    st.subheader("Config snapshot (vars detectadas)")
                    st.json(db.debug_config_snapshot())
                except Exception as e:
                    Security.log_error("DEBUG_SNAPSHOT", e)
                    st.warning("Falha ao coletar dados de diagnóstico.")
                try:
                    st.subheader("Diagnóstico do banco")
                    st.json(db.get_db_diagnostics())
                except Exception as e:
                    Security.log_error("DB_DIAG", e)
                    st.warning("Falha ao consultar diagnóstico do banco.")

        with col6:
            # Backup do sistema Avançado (JSON)
            if st.button("💾 Gerar Backup", help="Gera um backup completo do banco em formato JSON"):
                try:
                    backup_bytes = db.exportar_dados_seguranca()
                    st.session_state["last_backup_time"] = datetime.now()
                    st.download_button(
                        label="📥 Baixar Backup", 
                        data=backup_bytes, 
                        file_name=f"backup_clinica_full_{datetime.now().strftime('%Y%m%d_%H%M')}.json", 
                        mime="application/json",
                        key="btn_dl_backup"
                    )
                    st.success("Backup gerado com sucesso!")
                except Exception as e:
                    Security.log_error("BACKUP_GEN", e)
                    st.error("Erro interno ao gerar backup.")

        # Seção de Status de Backup (UX #10)
        if "last_backup_time" in st.session_state:
            st.caption(f"Último backup gerado nesta sessão: {st.session_state['last_backup_time'].strftime('%H:%M:%S')}")

        st.markdown("### 📋 Auditoria Avançada (últimos 100)")
        try:
            aud = db.listar_auditoria(100)
            if aud:
                st.dataframe(pd.DataFrame(aud), use_container_width=True, height=300)
            else:
                st.info("Sem registros de auditoria ainda.")
        except Exception as e:
            Security.log_error("AUDIT_LIST", e)
            st.warning("Não foi possível carregar os logs de auditoria.")

        # Fim do container configurado via with na linha 1156

class LaudosPage:
    @staticmethod
    def render() -> None:
        render_page_header("📑 Laudos", "Modelos, emissão, versões e autenticação")

        tab1, tab2, tab3 = st.tabs(["📝 Modelos", "🖨️ Emitir Laudo", "🔎 Laudos Emitidos"])

        pacientes = db.listar_pacientes()
        nomes_pac = {p["nome"]: p["id"] for p in pacientes}

        # ── Modelos ──
        with tab1:
            st.markdown("### ➕ Novo Modelo de Laudo")
            m1, m2 = st.columns(2)
            with m1:
                mo_nome = st.text_input("Nome do modelo *", key="modelo_nome", max_chars=255)
                mo_categoria = st.selectbox("Categoria", ["Geral", "Psicológico", "Médico", "Pericial", "Admissional"], key="modelo_cat")
                mo_titulo = st.text_input("Título", key="modelo_tit", max_chars=255, placeholder="Ex: Laudo Psicológico")
            with m2:
                mo_tipo_exame = st.text_input("Tipo de exame", key="modelo_tipo", max_chars=255)
                mo_ass = st.checkbox("Exigir assinatura digital", value=False, key="modelo_ass")
            mo_cabecalho = st.text_input("Cabeçalho", key="modelo_cab", max_chars=500,
                                         placeholder="Ex: LABORATÓRIO DE PSICOLOGIA LTDA - CRP 00/00000")
            mo_corpo = st.text_area("Corpo do modelo * (use {nome}, {empresa}, {medico}, {data})", key="modelo_corpo", height=220,
                                    placeholder="A Sr(a). {nome}, referente à empresa {empresa}, foi submetido(a) a avaliação...")
            mo_rodape = st.text_input("Rodapé", key="modelo_rod", max_chars=500,
                                      placeholder="Ex: Documento válido com assinatura digital.")

            if st.button("💾 Salvar Modelo", type="primary", key="modelo_salvar", use_container_width=True):
                if not mo_nome.strip() or not mo_corpo.strip():
                    st.error("Informe nome e corpo do modelo.")
                else:
                    ok = db.inserir_modelo_laudo({
                        "nome": mo_nome.strip(), "categoria": mo_categoria,
                        "titulo": mo_titulo.strip() or None, "cabecalho": mo_cabecalho.strip() or None,
                        "corpo": mo_corpo.strip(), "rodape": mo_rodape.strip() or None,
                        "tipo_exame": mo_tipo_exame.strip() or None,
                        "assinatura_digital": mo_ass, "ativo": True,
                    })
                    if ok:
                        st.toast("Modelo salvo!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar modelo.")

            st.markdown("---")
            st.markdown("### 📚 Modelos cadastrados")
            cat_filtro = st.selectbox("Categoria", ["(Todas)"] + ["Geral", "Psicológico", "Médico", "Pericial", "Admissional"], key="modelo_filtro_cat")
            modelos = db.listar_modelos_laudos(None if cat_filtro == "(Todas)" else cat_filtro)
            if not modelos:
                st.info("Nenhum modelo cadastrado.")
            else:
                df_mod = pd.DataFrame([{
                    "ID": m["id"], "Nome": m["nome"], "Categoria": m["categoria"],
                    "Tipo Exame": m["tipo_exame"] or "", "Assinatura": "✓" if m["assinatura_digital"] else "",
                    "Ativo": "Sim" if m["ativo"] else "Não",
                } for m in modelos])
                st.dataframe(df_mod, use_container_width=True, hide_index=True)
                with st.expander("✏️ Editar modelo"):
                    opcoes_m = {f"#{m['id']} — {m['nome']}": m["id"] for m in modelos}
                    sel_m = st.selectbox("Selecione o modelo", list(opcoes_m.keys()), key="modelo_sel_edit")
                    det_m = db.obter_modelo_laudo(opcoes_m[sel_m])
                    if det_m:
                        ed_nome = st.text_input("Nome", value=det_m["nome"], key=f"mod_ed_nome_{det_m['id']}")
                        ed_corpo = st.text_area("Corpo", value=det_m["corpo"], key=f"mod_ed_corpo_{det_m['id']}", height=160)
                        ed_titulo = st.text_input("Título", value=det_m["titulo"] or "", key=f"mod_ed_tit_{det_m['id']}")
                        if st.button("💾 Atualizar Modelo", key=f"mod_ed_save_{det_m['id']}"):
                            db.atualizar_modelo_laudo(det_m["id"], {"nome": ed_nome, "corpo": ed_corpo, "titulo": ed_titulo or None})
                            st.toast("Modelo atualizado!", icon="✅")
                            st.rerun()
                opcoes_del_m = {f"#{m['id']} — {m['nome']}": m["id"] for m in modelos}
                sel_del_m = st.selectbox("Excluir modelo", list(opcoes_del_m.keys()), key="modelo_sel_del")
                if st.button("🗑️ Excluir Modelo", key="modelo_del_btn"):
                    db.excluir_modelo_laudo(opcoes_del_m[sel_del_m])
                    st.rerun()

        # ── Emitir Laudo ──
        with tab2:
            st.markdown("### 🖨️ Emitir Laudo a partir de Modelo")
            modelos_ativos = db.listar_modelos_laudos()
            if not modelos_ativos:
                st.warning("Crie um modelo na aba 📝 Modelos antes de emitir laudos.")
            else:
                l1, l2 = st.columns(2)
                with l1:
                    sel_l_nome = st.selectbox("Paciente *", list(nomes_pac.keys()) if nomes_pac else [""], key="laudo_pac")
                    opcoes_mod = {f"#{m['id']} — {m['nome']}": m["id"] for m in modelos_ativos}
                    sel_l_mod = st.selectbox("Modelo *", list(opcoes_mod.keys()), key="laudo_mod")
                with l2:
                    laudo_medico = st.selectbox("Médico *", AGENDA_MEDICOS, index=0, key="laudo_medico")
                    laudo_empresa = st.text_input("Empresa", key="laudo_empresa")

                modelo = db.obter_modelo_laudo(opcoes_mod[sel_l_mod])
                paciente_info = db.obter_paciente(nomes_pac[sel_l_nome]) if sel_l_nome else None
                empresa_padrao = paciente_info.get("empresa") if paciente_info else None
                if empresa_padrao:
                    laudo_empresa = st.text_input("Empresa", value=empresa_padrao, key="laudo_empresa2")

                if modelo:
                    conteudo_pre = modelo["corpo"]
                    substituicoes = {
                        "{nome}": sel_l_nome or "",
                        "{empresa}": empresa_padrao or laudo_empresa or "",
                        "{medico}": laudo_medico,
                        "{data}": date.today().strftime("%d/%m/%Y"),
                    }
                    for k, v in substituicoes.items():
                        conteudo_pre = conteudo_pre.replace(k, v)
                    st.markdown("**Pré-visualização / Edição do conteúdo:**")
                    laudo_conteudo = st.text_area("Conteúdo do laudo", value=conteudo_pre, height=260, key="laudo_conteudo")
                    if st.button("📜 Gerar PDF do Laudo", key="laudo_gerar_pdf"):
                        _gerar_laudo_completo_pdf(modelo, {
                            "paciente_nome": sel_l_nome, "empresa": empresa_padrao or laudo_empresa,
                            "medico": laudo_medico, "conteudo": laudo_conteudo,
                        })
                    if st.button("💾 Salvar e Emitir Laudo", type="primary", key="laudo_emitir", use_container_width=True):
                        if not sel_l_nome:
                            st.error("Informe o paciente.")
                        else:
                            laudo_id = db.inserir_laudo_emitido({
                                "modelo_id": modelo["id"],
                                "paciente_id": nomes_pac.get(sel_l_nome),
                                "paciente_nome": sel_l_nome,
                                "empresa": empresa_padrao or laudo_empresa or None,
                                "medico": laudo_medico,
                                "tipo_exame": modelo["tipo_exame"] or None,
                                "conteudo": laudo_conteudo,
                                "assinatura_digital": modelo["assinatura_digital"],
                            })
                            if laudo_id:
                                st.toast("Laudo emitido com código de autenticação!", icon="✅")
                                security.log_access("EMITIR_LAUDO", f"{sel_l_nome}")
                                st.rerun()
                            else:
                                st.error("Erro ao emitir laudo.")

        # ── Laudos Emitidos ──
        with tab3:
            st.markdown("### 🔎 Laudos Emitidos")
            filtro_l = st.text_input("Filtrar por paciente/exame/código", key="laudo_filtro")
            laudos = db.listar_laudos_emitidos(filtro=filtro_l or None)
            if not laudos:
                st.info("Nenhum laudo emitido.")
            else:
                df_l = pd.DataFrame([{
                    "ID": l["id"], "Paciente": l["paciente_nome"] or "",
                    "Exame": l["tipo_exame"] or "", "Médico": l["medico"] or "",
                    "Versão": l["versao"], "Código": l["codigo_autenticacao"] or "",
                    "Status": l["status"], "Data": l["criado_em"],
                } for l in laudos])
                st.dataframe(df_l, use_container_width=True, hide_index=True)

                st.markdown("#### 📖 Detalhes / Versões")
                opcoes_l = {f"#{l['id']} — {l['paciente_nome'] or '?'} (v{l['versao']})": l["id"] for l in laudos}
                sel_l = st.selectbox("Laudo", list(opcoes_l.keys()), key="laudo_sel_det")
                det_l = db.obter_laudo_emitido(opcoes_l[sel_l])
                if det_l:
                    st.info(f"Código de autenticação: **{det_l['codigo_autenticacao']}**  |  Versão: {det_l['versao']}  |  Status: {det_l['status']}")
                    novo_conteudo = st.text_area("Conteúdo (editar para nova versão)", value=det_l["conteudo"], height=180, key=f"laudo_ed_{det_l['id']}")
                    if st.button("➕ Gerar Nova Versão", key=f"laudo_nv_{det_l['id']}"):
                        if db.adicionar_versao_laudo(det_l["id"], novo_conteudo, st.session_state.get("user_name", "")):
                            st.toast("Nova versão registrada!", icon="✅")
                            st.rerun()
                    versoes = db.listar_versoes_laudo(det_l["id"])
                    if versoes:
                        st.markdown("**Histórico de versões:**")
                        for v in versoes:
                            st.caption(f"v{v['versao']} — {v['criado_em']} — {v['editado_por'] or '—'}")
                    if st.button("🖨️ Gerar PDF", key=f"laudo_pdf_{det_l['id']}"):
                        _gerar_laudo_completo_pdf({"cabecalho": "", "rodape": "", "titulo": "LAUDO", "assinatura_digital": det_l["assinatura_digital"]}, {
                            "paciente_nome": det_l["paciente_nome"], "empresa": det_l["empresa"],
                            "medico": det_l["medico"], "conteudo": det_l["conteudo"],
                        })
                opcoes_del_l = {f"#{l['id']} — {l['paciente_nome'] or '?'}": l["id"] for l in laudos}
                sel_del_l = st.selectbox("Excluir laudo", list(opcoes_del_l.keys()), key="laudo_sel_del")
                if st.button("🗑️ Excluir Laudo", key="laudo_del_btn"):
                    db.excluir_laudo_emitido(opcoes_del_l[sel_del_l])
                    st.rerun()

            st.markdown("#### ✅ Verificar autenticidade")
            cod_verif = st.text_input("Digite o código de autenticação", key="laudo_cod_verif")
            if cod_verif and st.button("🔍 Verificar", key="laudo_verif_btn"):
                res = db.verificar_autenticidade_laudo(cod_verif)
                if res:
                    st.success(f"✅ Laudo autêntico! Paciente: {res['paciente_nome']} — Exame: {res['tipo_exame'] or '—'} — Versão: {res['versao']} — Emitido em: {res['criado_em']}")
                else:
                    st.error("❌ Código não encontrado. O laudo pode ser falso ou adulterado.")


def _gerar_laudo_completo_pdf(modelo: dict, dados: dict) -> None:
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_draw_color(77, 167, 104)
        pdf.set_line_width(0.8)
        cabecalho = modelo.get("cabecalho") or ""
        if cabecalho:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, cabecalho, align="C")
            pdf.ln(1)
        pdf.line(10, 24, 200, 24)
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, (modelo.get("titulo") or "LAUDO").upper(), ln=True, align="C")
        pdf.ln(3)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"Paciente: {dados.get('paciente_nome') or 'N/A'}", ln=True)
        pdf.cell(0, 7, f"Empresa: {dados.get('empresa') or '—'}", ln=True)
        pdf.cell(0, 7, f"Médico: {dados.get('medico') or ''}", ln=True)
        pdf.cell(0, 7, f"Data: {date.today().strftime('%d/%m/%Y')}", ln=True)
        if dados.get("codigo_autenticacao"):
            pdf.cell(0, 7, f"Código de autenticação: {dados['codigo_autenticacao']}", ln=True)
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, dados.get("conteudo") or "")
        rodape = modelo.get("rodape") or ""
        if rodape:
            pdf.ln(6)
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 5, rodape, align="C")
        pdf.ln(10)
        pdf.cell(0, 7, "___________________________", ln=True, align="C")
        pdf.cell(0, 7, dados.get("medico") or "", ln=True, align="C")
        if modelo.get("assinatura_digital"):
            pdf.cell(0, 7, "Documento com assinatura digital", ln=True, align="C")
        _baixar_pdf_streamlit(pdf, f"laudo_{dados.get('paciente_nome', 'paciente')}.pdf")
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")


class DocsEditorPage:
    @staticmethod
    def render() -> None:
        render_page_header("📝 Editor de Laudos", "Preenchimento de laudos via Google Docs")
        try:
            import gdocs
        except Exception as e:
            st.error(f"Falha ao carregar módulo Google Docs: {e}")
            return

        if not gdocs.configurado():
            st.warning(
                "Configure **GOOGLE_CLIENT_ID**, **GOOGLE_CLIENT_SECRET** e **GOOGLE_REDIRECT_URI** "
                "no arquivo `.streamlit/secrets.toml` para usar o Google Docs. "
                "Crie as credenciais em console.cloud.google.com → APIs & Services → Credentials → OAuth 2.0 Client ID."
            )
            DocsEditorPage._manual_link()
            return

        # ── Callback OAuth (retorno do Google com ?code=...) ──
        params = st.query_params
        if "code" in params:
            st.session_state["google_pending_code"] = params["code"]
            st.session_state["google_pending_state"] = params.get("state", "")
            st.query_params.clear()
        if st.session_state.get("google_pending_code"):
            with st.spinner("Conectando ao Google..."):
                try:
                    gdocs.exchange_code(
                        st.session_state.pop("google_pending_code", ""),
                        expected_state=st.session_state.pop("google_pending_state", ""),
                    )
                    st.success("Conta Google conectada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao conectar com o Google: {e}")
                    st.session_state.pop("google_pending_code", None)
                    st.session_state.pop("google_pending_state", None)

        creds = gdocs.get_credentials()
        if not creds:
            st.info("Conecte sua conta Google para preencher modelos de laudo automaticamente.")
            url = gdocs.authorization_url()
            st.markdown(
                f'<a href="{url}" target="_blank" style="text-decoration:none;">'
                '<div style="background:linear-gradient(135deg,#4285F4 0%,#356AC3 100%);color:#fff;'
                'padding:16px;border-radius:12px;text-align:center;font-size:1.05rem;font-weight:700;'
                'box-shadow:0 8px 24px rgba(66,133,244,.35);">'
                '🔗 Conectar com Google Docs'
                '<div style="font-size:.8rem;font-weight:500;opacity:.85;">Abre o login do Google em nova aba</div>'
                '</div></a>',
                unsafe_allow_html=True,
            )
            st.caption("Após autorizar, você voltará ao app já conectado.")
            return

        # ── Conectado ──
        st.success(f"✅ Conectado: {gdocs.account_info() or 'Google Docs'}")
        if st.button("🔌 Desconectar", key="gdocs_disconnect"):
            gdocs.disconnect()
            st.rerun()

        st.markdown("---")
        st.markdown("### 🚀 Preencher modelo de laudo no Google Docs")
        pacientes = db.listar_pacientes()
        nomes_pac = {p["nome"]: p["id"] for p in pacientes}
        sel_nome = st.selectbox("Paciente *", list(nomes_pac.keys()) if nomes_pac else [""], key="gdocs_pac")

        l1, l2 = st.columns(2)
        with l1:
            template_url = st.text_input(
                "URL do Documento Modelo *",
                key="gdocs_tpl",
                placeholder="https://docs.google.com/document/d/.../edit",
                help="O documento deve conter os campos {nome}, {empresa}, {medico} e {data} no corpo.",
            )
        with l2:
            medico = st.selectbox("Médico", AGENDA_MEDICOS, index=0, key="gdocs_med")

        if sel_nome and template_url.strip():
            if st.button("📄 Preencher e Criar Cópia no Google Docs", type="primary", key="gdocs_go", use_container_width=True):
                paciente_info = db.obter_paciente(nomes_pac[sel_nome]) if sel_nome else None
                placeholders = {
                    "{nome}": sel_nome,
                    "{empresa}": (paciente_info or {}).get("empresa") or "",
                    "{medico}": medico,
                    "{data}": date.today().strftime("%d/%m/%Y"),
                }
                doc_name = f"Laudo - {sel_nome} - {date.today().strftime('%d/%m/%Y')}"
                with st.spinner("Copiando e preenchendo o documento no Google Docs..."):
                    try:
                        new_url = gdocs.fill_template(template_url.strip(), placeholders, doc_name)
                    except Exception as e:
                        st.error(f"Erro ao preencher o documento: {e}")
                        new_url = None
                if new_url:
                    st.session_state["last_docs_url"] = new_url
                    st.success("Documento criado com sucesso!")
                    st.markdown(
                        f'<a href="{new_url}" target="_blank" style="text-decoration:none;">'
                        '<div style="background:linear-gradient(135deg,#4DA768 0%,#3e8a54 100%);color:#fff;'
                        'padding:16px;border-radius:12px;text-align:center;font-size:1.1rem;font-weight:700;'
                        'box-shadow:0 8px 24px rgba(77,167,104,.35);">'
                        '🚀 Abrir Laudo no Google Docs'
                        '<div style="font-size:.8rem;font-weight:500;opacity:.85;">Abre em nova aba</div>'
                        '</div></a>',
                        unsafe_allow_html=True,
                    )
        else:
            st.info("👆 Selecione o paciente e cole a URL do documento modelo para habilitar a geração.")

        DocsEditorPage._manual_link()

    @staticmethod
    def _manual_link() -> None:
        st.markdown("---")
        st.markdown("### 🔗 Abertura manual de documento")
        docs_url = st.text_input(
            "URL do Google Docs",
            value=st.session_state.get("last_docs_url", "https://docs.google.com/document/d/1FDYCKMZaEMWAiOO1ovq9R0bQ0L4vTpEZr6DGohcppJY/edit"),
            placeholder="Ex: https://docs.google.com/document/d/.../edit",
            key="gdocs_manual_url",
        )
        if docs_url:
            st.session_state["last_docs_url"] = docs_url
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown(
                    f'<a href="{docs_url}" target="_blank" style="text-decoration:none;">'
                    '<div style="background:linear-gradient(135deg,#4DA768 0%,#3e8a54 100%);color:#fff;'
                    'padding:20px;border-radius:16px;text-align:center;font-size:1.2rem;font-weight:800;'
                    'box-shadow:0 10px 30px rgba(77,167,104,.4);">'
                    '🚀 Abrir Editor de Laudos (Google Docs)'
                    '<div style="font-size:.8rem;font-weight:500;opacity:.8;margin-top:5px;">Abre em nova aba segura</div>'
                    '</div></a>',
                    unsafe_allow_html=True,
                )

class AIPage:
    @staticmethod
    def render() -> None:
        render_page_header("🤖 Inteligência Artificial", "Resumos, previsões, OCR e rascunhos clínicos")

        tab1, tab2, tab3, tab4 = st.tabs(["📝 Resumo de Paciente", "📉 Previsão de Faltas", "🔍 OCR de Documento", "💊 Rascunho de Receita"])

        from ai_manager import AIManager

        with tab1:
            st.markdown("### 📝 Resumo Clínico de Paciente (IA)")
            pacientes = db.listar_pacientes()
            if not pacientes:
                st.info("Cadastre pacientes para usar o resumo.")
            else:
                opcoes = {p["nome"]: p["id"] for p in pacientes}
                sel = st.selectbox("Paciente", list(opcoes.keys()), key="ia_resumo_pac")
                if st.button("✨ Gerar Resumo com IA", type="primary", key="ia_resumo_btn"):
                    pac = db.obter_paciente(opcoes[sel])
                    anam = db.obter_anamnese(opcoes[sel])
                    evols = db.listar_evolucoes(opcoes[sel])
                    import json
                    with st.spinner("IA gerando resumo clínico..."):
                        resumo = AIManager.summarize_patient(
                            json.dumps(pac, default=str),
                            json.dumps(evols[:15], default=str),
                            json.dumps(anam, default=str),
                        )
                    st.session_state["ia_resumo_res"] = resumo
                resumo = st.session_state.get("ia_resumo_res", "")
                if resumo:
                    st.markdown("#### 📄 Resumo gerado")
                    st.info(resumo)
                    if st.button("🧹 Limpar resumo", key="ia_resumo_limpar"):
                        st.session_state.pop("ia_resumo_res", None)
                        st.rerun()

        with tab2:
            st.markdown("### 📉 Previsão de Faltas (no-show)")
            st.caption("Análise estatística + IA dos agendamentos para estimar risco de faltas.")
            ags = db.listar_agendamentos()
            if not ags:
                st.info("Sem agendamentos. Registre agendamentos na Agenda.")
            else:
                df_ia = pd.DataFrame([{
                    "medico": a["medico"], "status": a["status"], "data": str(a["data"]),
                    "dia_semana": _dia_semana(a["data"]), "empresa": a["empresa"] or "",
                    "tipo": a["tipo"] or "",
                } for a in ags])
                status_counts = df_ia["status"].value_counts().to_dict()
                por_medico = df_ia.groupby("medico")["status"].apply(lambda s: dict(s.value_counts())).to_dict()
                stats = {"total": len(df_ia), "por_status": status_counts, "por_medico": por_medico}
                st.markdown("#### 📊 Estatísticas atuais")
                st.json(stats, expanded=False)
                if st.button("🔮 Gerar Análise de Faltas", type="primary", key="ia_falta_btn"):
                    import json
                    with st.spinner("IA analisando padrões de faltas..."):
                        analise = AIManager.predict_no_show(json.dumps(stats, default=str))
                    st.session_state["ia_falta_res"] = analise
                analise = st.session_state.get("ia_falta_res", "")
                if analise:
                    st.markdown("#### 📄 Análise gerada")
                    st.info(analise)
                    if st.button("🧹 Limpar análise", key="ia_falta_limpar"):
                        st.session_state.pop("ia_falta_res", None)
                        st.rerun()

        with tab3:
            st.markdown("### 🔍 Extrair Texto de Documento (OCR)")
            st.caption("Envie um PDF ou imagem para extrair o texto com a IA.")
            up_ocr = st.file_uploader("Arquivo (PDF ou imagem)", type=["pdf", "png", "jpg", "jpeg"], key="ia_ocr_up")
            if up_ocr:
                st.caption(f"{up_ocr.name} — {len(up_ocr.getvalue()) / 1024:.1f} KB")
                if st.button("🔍 Extrair Texto", type="primary", key="ia_ocr_btn"):
                    with st.spinner("IA extraindo texto..."):
                        texto = AIManager.extract_text_ocr(up_ocr.getvalue(), up_ocr.name)
                    st.session_state["ia_ocr_res"] = texto or "Nenhum texto identificado."
            ocr_res = st.session_state.get("ia_ocr_res", "")
            if ocr_res:
                st.markdown("#### 📄 Texto extraído")
                st.code(ocr_res, language=None)
                if st.button("🧹 Limpar OCR", key="ia_ocr_limpar"):
                    st.session_state.pop("ia_ocr_res", None)
                    st.rerun()

        with tab4:
            st.markdown("### 💊 Rascunho de Receita com IA")
            st.caption("A IA sugere um rascunho de prescrição. O médico deve revisar antes de assinar.")
            r1, r2 = st.columns(2)
            with r1:
                esp = st.selectbox("Especialidade", ["Psiquiatria", "Psicologia", "Clínico Geral", "Neurologia", "Pediatria"], key="ia_rec_esp")
            with r2:
                queixa = st.text_input("Queixa / contexto", key="ia_rec_queixa", placeholder="Ex: ansiedade, insônia, dor...")
            if st.button("✨ Gerar Rascunho", type="primary", key="ia_rec_btn"):
                if not queixa.strip():
                    st.error("Descreva a queixa.")
                else:
                    with st.spinner("IA gerando rascunho..."):
                        rascunho = AIManager.clinical_draft_receipt(esp, queixa.strip())
                    st.session_state["ia_rec_res"] = rascunho
            rasc = st.session_state.get("ia_rec_res", "")
            if rasc:
                st.markdown("#### 📄 Rascunho")
                st.info(rasc)
                if st.button("🧹 Limpar rascunho", key="ia_rec_limpar"):
                    st.session_state.pop("ia_rec_res", None)
                    st.rerun()


def _dia_semana(data):
    try:
        return ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][data.weekday()]
    except Exception:
        try:
            return ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][pd.to_datetime(str(data)).weekday()]
        except Exception:
            return ""

class FinancePage:
    @staticmethod
    def render() -> None:
        render_page_header("💰 Financeiro", "Lançamentos, fluxo de caixa, DRE e notas fiscais")

        tab1, tab2, tab3 = st.tabs(["💸 Lançamentos", "📊 Fluxo de Caixa / DRE", "🧾 Notas Fiscais"])

        with tab1:
            st.markdown("### ➕ Novo Lançamento")
            l1, l2, l3 = st.columns(3)
            with l1:
                fin_tipo = st.selectbox("Tipo *", ["Receita", "Despesa"], key="fin_tipo")
                fin_categoria = st.selectbox("Categoria *", _fin_categorias(fin_tipo), key="fin_cat")
                fin_descricao = st.text_input("Descrição", key="fin_desc", max_chars=255)
            with l2:
                fin_valor = st.number_input("Valor (R$) *", min_value=0.0, step=10.0, value=0.0, key="fin_valor")
                fin_data = st.date_input("Data *", value=date.today(), key="fin_data")
                fin_pagamento = st.selectbox("Forma de pagamento", ["", "Dinheiro", "Pix", "Cartão de crédito", "Cartão de débito", "Boleto", "Transferência"], key="fin_pag")
            with l3:
                empresas_fin = db.listar_empresas()
                fin_empresa = st.selectbox("Empresa", [""] + [e["nome"] for e in empresas_fin], key="fin_empresa")
                fin_convenio = st.text_input("Convênio", key="fin_convenio", max_chars=255)
                fin_status = st.selectbox("Status", ["Pago", "Pendente", "Cancelado"], key="fin_status")
            fin_obs = st.text_input("Observações", key="fin_obs", max_chars=500)

            if st.button("💾 Salvar Lançamento", type="primary", key="fin_salvar", use_container_width=True):
                if fin_valor <= 0:
                    st.error("Informe um valor maior que zero.")
                else:
                    emp_id = None
                    for e in empresas_fin:
                        if e["nome"] == fin_empresa:
                            emp_id = e["id"]
                            break
                    ok = db.inserir_lancamento({
                        "tipo": fin_tipo, "categoria": fin_categoria,
                        "descricao": fin_descricao.strip() or None,
                        "valor": float(fin_valor), "data": fin_data.strftime("%Y-%m-%d"),
                        "forma_pagamento": fin_pagamento or None,
                        "status": fin_status, "empresa_id": emp_id,
                        "empresa_nome": fin_empresa or None,
                        "convenio": fin_convenio.strip() or None,
                        "observacoes": fin_obs.strip() or None,
                    })
                    if ok:
                        st.toast("Lançamento registrado!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar lançamento.")

            st.markdown("---")
            st.markdown("### 🔎 Lançamentos")
            fl1, fl2, fl3 = st.columns(3)
            with fl1:
                fl_tipo = st.selectbox("Filtrar tipo", ["(Todos)", "Receita", "Despesa"], key="fin_filtro_tipo")
            with fl2:
                fl_dini = st.date_input("Data inicial", value=None, key="fin_filtro_dini")
            with fl3:
                fl_dfim = st.date_input("Data final", value=None, key="fin_filtro_dfim")
            lancamentos = db.listar_lancamentos(
                periodo_inicio=fl_dini.strftime("%Y-%m-%d") if fl_dini else None,
                periodo_fim=fl_dfim.strftime("%Y-%m-%d") if fl_dfim else None,
                tipo=None if fl_tipo == "(Todos)" else fl_tipo,
            )
            if not lancamentos:
                st.info("Nenhum lançamento encontrado.")
            else:
                df_fin = pd.DataFrame([{
                    "ID": l["id"], "Tipo": l["tipo"], "Categoria": l["categoria"],
                    "Descrição": l["descricao"] or "", "Data": l["data"],
                    "Valor (R$)": float(l["valor"]),
                    "Pagamento": l["forma_pagamento"] or "",
                    "Empresa": l["empresa_nome"] or "",
                    "Status": l["status"],
                } for l in lancamentos])
                st.dataframe(df_fin, use_container_width=True, hide_index=True)
                receitas = sum(float(l["valor"]) for l in lancamentos if l["tipo"] == "Receita")
                despesas = sum(float(l["valor"]) for l in lancamentos if l["tipo"] == "Despesa")
                st.success(f"Receitas: R$ {receitas:,.2f}  |  Despesas: R$ {despesas:,.2f}  |  **Resultado: R$ {receitas - despesas:,.2f}**")
                opcoes_fin = {f"#{l['id']} — {l['descricao'] or l['categoria']}": l["id"] for l in lancamentos}
                sel_fin = st.selectbox("Excluir lançamento", list(opcoes_fin.keys()), key="fin_sel_del")
                if st.button("🗑️ Excluir", key="fin_del_btn"):
                    db.excluir_lancamento(opcoes_fin[sel_fin])
                    st.rerun()

        with tab2:
            st.markdown("### 📊 Fluxo de Caixa")
            r1, r2 = st.columns(2)
            with r1:
                dre_dini = st.date_input("Período inicial", value=date(date.today().year, 1, 1), key="dre_dini")
            with r2:
                dre_dfim = st.date_input("Período final", value=date.today(), key="dre_dfim")
            resumo = db.resumo_financeiro(
                dre_dini.strftime("%Y-%m-%d"), dre_dfim.strftime("%Y-%m-%d"))
            cards_dre = [
                {"icon": "⬆️", "title": "Receitas", "value": f"R$ {resumo['receitas']:,.2f}"},
                {"icon": "⬇️", "title": "Despesas", "value": f"R$ {resumo['despesas']:,.2f}"},
                {"icon": "📊", "title": "Resultado", "value": f"R$ {resumo['resultado']:,.2f}"},
            ]
            display_cards(cards_dre)

            if resumo["por_categoria"]:
                df_cat = pd.DataFrame([{
                    "Categoria": c["categoria"], "Tipo": c["tipo"],
                    "Valor (R$)": float(c["total"]),
                } for c in resumo["por_categoria"]])
                st.markdown("#### Por categoria")
                st.dataframe(df_cat, use_container_width=True, hide_index=True)
                cat_receitas = df_cat[df_cat["Tipo"] == "Receita"]
                cat_despesas = df_cat[df_cat["Tipo"] == "Despesa"]
                if not cat_receitas.empty:
                    fig_d1 = px.bar(cat_receitas, x="Categoria", y="Valor (R$)", title="Receitas por categoria",
                                    color_discrete_sequence=['#4CAF50'])
                    fig_d1.update_layout(height=320, font=dict(color="white"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_d1, use_container_width=True)
                if not cat_despesas.empty:
                    fig_d2 = px.bar(cat_despesas, x="Categoria", y="Valor (R$)", title="Despesas por categoria",
                                    color_discrete_sequence=['#D32F2F'])
                    fig_d2.update_layout(height=320, font=dict(color="white"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_d2, use_container_width=True)

            if resumo["por_pagamento"]:
                st.markdown("#### Por forma de pagamento")
                df_pag = pd.DataFrame([{
                    "Forma": p["forma_pagamento"] or "Não informado",
                    "Valor (R$)": float(p["total"]),
                } for p in resumo["por_pagamento"]])
                st.dataframe(df_pag, use_container_width=True, hide_index=True)

        with tab3:
            st.markdown("### 🧾 Emitir Nota Fiscal")
            n1, n2 = st.columns(2)
            with n1:
                empresas_nf = db.listar_empresas()
                nf_empresa = st.selectbox("Empresa *", [e["nome"] for e in empresas_nf] if empresas_nf else [""], key="nf_empresa")
                nf_numero = st.text_input("Número", key="nf_numero", max_chars=50)
                nf_data = st.date_input("Data de emissão *", value=date.today(), key="nf_data")
            with n2:
                nf_tipo = st.selectbox("Tipo", ["NFSe", "Nota Fiscal Eletrônica", "Recibo"], key="nf_tipo")
                nf_serie = st.text_input("Série", key="nf_serie", max_chars=10)
                nf_valor = st.number_input("Valor (R$) *", min_value=0.0, step=10.0, value=0.0, key="nf_valor")
            nf_descricao = st.text_input("Descrição", key="nf_desc", max_chars=255)
            nf_obs = st.text_input("Observações", key="nf_obs", max_chars=500)
            if st.button("💾 Salvar Nota Fiscal", type="primary", key="nf_salvar", use_container_width=True):
                if not nf_empresa or nf_valor <= 0:
                    st.error("Informe a empresa e um valor maior que zero.")
                else:
                    emp_id = None
                    for e in empresas_nf:
                        if e["nome"] == nf_empresa:
                            emp_id = e["id"]
                            break
                    ok = db.inserir_nota_fiscal({
                        "empresa_id": emp_id, "empresa_nome": nf_empresa,
                        "numero": nf_numero.strip() or None, "serie": nf_serie.strip() or None,
                        "tipo": nf_tipo, "data_emissao": nf_data.strftime("%Y-%m-%d"),
                        "valor": float(nf_valor), "descricao": nf_descricao.strip() or None,
                        "observacoes": nf_obs.strip() or None,
                    })
                    if ok:
                        st.toast("Nota fiscal registrada!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar nota fiscal.")

            st.markdown("---")
            st.markdown("### 🔎 Notas Fiscais")
            nf_filtro = st.text_input("Filtrar por empresa/número", key="nf_filtro")
            notas = db.listar_notas_fiscais(filtro=nf_filtro or None)
            if not notas:
                st.info("Nenhuma nota fiscal encontrada.")
            else:
                df_nf = pd.DataFrame([{
                    "ID": n["id"], "Empresa": n["empresa_nome"] or "",
                    "Número": n["numero"] or "", "Tipo": n["tipo"],
                    "Data": n["data_emissao"], "Valor (R$)": float(n["valor"]),
                    "Status": n["status"],
                } for n in notas])
                st.dataframe(df_nf, use_container_width=True, hide_index=True)
                opcoes_nf = {f"#{n['id']} — {n['empresa_nome'] or '?'} ({n['numero'] or 'sem número'})": n["id"] for n in notas}
                sel_nf = st.selectbox("Excluir nota fiscal", list(opcoes_nf.keys()), key="nf_sel_del")
                if st.button("🗑️ Excluir", key="nf_del_btn"):
                    db.excluir_nota_fiscal(opcoes_nf[sel_nf])
                    st.rerun()


def _fin_categorias(tipo: str) -> list:
    if tipo == "Receita":
        return ["Consulta", "Exame", "Plano de saúde", "Particular", "Empresa", "Outros"]
    return ["Salário", "Aluguel", "Fornecedores", "Impostos", "Equipamentos", "Marketing", "Transporte", "Outros"]

class SecurityPage:
    @staticmethod
    def render() -> None:
        render_page_header("🔐 Segurança & LGPD", "Consentimentos, auditoria, backup e portabilidade")

        tab1, tab2, tab3, tab4 = st.tabs(["📜 Consentimentos", "🔍 Auditoria", "💾 Backup", "🗂️ Dados do Paciente (LGPD)"])

        with tab1:
            st.markdown("### ➕ Registrar Consentimento")
            pacientes = db.listar_pacientes()
            nomes_pac = {p["nome"]: p["id"] for p in pacientes}
            if not pacientes:
                st.info("Cadastre pacientes primeiro.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    sel_nome = st.selectbox("Paciente *", list(nomes_pac.keys()), key="cons_pac")
                    cons_tipo = st.selectbox("Tipo de consentimento *", [
                        "Coleta e uso de dados pessoais",
                        "Compartilhamento com empresas",
                        "Divulgação de imagem",
                        "Comunicação por WhatsApp/e-mail",
                        "Compartilhamento com profissionais",
                    ], key="cons_tipo")
                    cons_ass = st.checkbox("Paciente assentiu (aceitou)", value=True, key="cons_ass")
                with c2:
                    cons_data = st.date_input("Data de assinatura *", value=date.today(), key="cons_data")
                    cons_val = st.date_input("Validade", value=None, key="cons_val")
                    cons_ver = st.text_input("Versão do documento", key="cons_ver", max_chars=20, placeholder="Ex: v1.0")
                cons_desc = st.text_area("Descrição", key="cons_desc", max_chars=1000)
                if st.button("💾 Registrar Consentimento", type="primary", key="cons_salvar", use_container_width=True):
                    ok = db.registrar_consentimento({
                        "paciente_id": nomes_pac.get(sel_nome),
                        "paciente_nome": sel_nome,
                        "tipo": cons_tipo,
                        "descricao": cons_desc.strip() or None,
                        "assinado_em": cons_data.strftime("%Y-%m-%d"),
                        "validade": cons_val,
                        "assentimento": cons_ass,
                        "documento_versao": cons_ver.strip() or None,
                        "registrado_por": st.session_state.get("user_name", ""),
                    })
                    if ok:
                        st.toast("Consentimento registrado!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Erro ao registrar consentimento.")

                st.markdown("---")
                st.markdown("### 📜 Consentimentos registrados")
                cons = db.listar_consentimentos()
                if not cons:
                    st.info("Nenhum consentimento registrado.")
                else:
                    df_cons = pd.DataFrame([{
                        "ID": c["id"], "Paciente": c["paciente_nome"] or "",
                        "Tipo": c["tipo"], "Data": c["assinado_em"] or "",
                        "Validade": c["validade"] or "", "Assentiu": "✅" if c["assentimento"] else "❌",
                        "Versão": c["documento_versao"] or "",
                    } for c in cons])
                    st.dataframe(df_cons, use_container_width=True, hide_index=True)
                    opcoes_cons = {f"#{c['id']} — {c['paciente_nome'] or '?'} ({c['tipo'][:40]})": c["id"] for c in cons}
                    sel_cons = st.selectbox("Revogar consentimento", list(opcoes_cons.keys()), key="cons_sel_rev")
                    if st.button("🚫 Revogar", key="cons_rev_btn"):
                        db.revogar_consentimento(opcoes_cons[sel_cons])
                        st.rerun()

        with tab2:
            st.markdown("### 🔍 Registro de Auditoria")
            st.caption("Trilha de auditoria das ações realizadas no sistema (LGPD Art. 37).")
            lim = st.slider("Quantidade de registros", 20, 500, 100, step=20, key="audit_lim")
            auditoria = db.listar_auditoria(limit=lim)
            if not auditoria:
                st.info("Nenhum registro de auditoria.")
            else:
                df_aud = pd.DataFrame([{
                    "ID": a["id"], "Ação": a["acao"], "Entidade": a["entidade"],
                    "Detalhes": a["detalhes"] or "", "Usuário": a["usuario"] or "",
                    "Data": a["criado_em"],
                } for a in auditoria])
                st.dataframe(df_aud, use_container_width=True, hide_index=True, height=400)

        with tab3:
            st.markdown("### 💾 Backup do Sistema")
            st.caption("Gere um backup completo em JSON com todas as tabelas do sistema.")
            if st.button("🔄 Gerar Backup Completo", type="primary", key="backup_gerar"):
                with st.spinner("Gerando backup..."):
                    dados = db.backup_completo()
                st.download_button(
                    "⬇️ Baixar Backup (JSON)",
                    data=dados,
                    file_name=f"backup_mvpdepsicologia_{date.today().strftime('%Y%m%d')}.json",
                    mime="application/json",
                )
            st.markdown("---")
            st.markdown("### ⚠️ Área de Risco")
            st.warning("A exclusão de dados é permanente e não pode ser desfeita. Use com cautela conforme a LGPD.")
            em = st.text_input("Digite 'EXCLUIR' para habilitar", key="seg_risco_input")
            if em == "EXCLUIR":
                st.error("🔴 Modo de risco ativado. Nenhuma ação destrutiva é executada automaticamente por segurança.")

        with tab4:
            st.markdown("### 🗂️ Portabilidade de Dados (LGPD Art. 18)")
            st.caption("Exporte todos os dados de um paciente em JSON para portabilidade.")
            pacientes2 = db.listar_pacientes()
            if not pacientes2:
                st.info("Cadastre pacientes primeiro.")
            else:
                opcoes = {p["nome"]: p["id"] for p in pacientes2}
                sel_lgpd = st.selectbox("Paciente", list(opcoes.keys()), key="lgpd_pac")
                if st.button("⬇️ Exportar Dados do Paciente (JSON)", type="primary", key="lgpd_exportar"):
                    with st.spinner("Exportando dados..."):
                        dados = db.exportar_dados_paciente_lgpd(opcoes[sel_lgpd])
                    st.download_button(
                        "⬇️ Baixar Dados do Paciente",
                        data=dados,
                        file_name=f"dados_lgpd_{sel_lgpd.replace(' ', '_')}.json",
                        mime="application/json",
                    )

class ExtrasPage:
    @staticmethod
    def render() -> None:
        render_page_header("🛠️ Extras & Recursos", "Importação, WhatsApp, lembretes e guia rápido")

        tab1, tab2, tab3, tab4 = st.tabs(["📥 Importação CSV", "💬 WhatsApp", "⏰ Lembretes", "📖 Guia Rápido"])

        with tab1:
            st.markdown("### 📥 Importação de Pacientes (CSV)")
            st.caption("Formato: nome, cpf, nascimento (DD/MM/AAAA), telefone, email, empresa")
            up_csv = st.file_uploader("Arquivo CSV", type=["csv"], key="imp_csv")
            if up_csv:
                try:
                    import io as _io
                    content = up_csv.getvalue().decode("utf-8-sig")
                    linhas = [l.strip() for l in content.splitlines() if l.strip()]
                    import csv as _csv
                    reader = list(_csv.reader(_io.StringIO(content)))
                    st.info(f"{len(reader)} linha(s) detectada(s).")
                    st.dataframe(pd.DataFrame(reader[:10]), use_container_width=True, hide_index=True)
                    if st.button("🚀 Importar Pacientes", type="primary", key="imp_btn"):
                        import csv as _csv2
                        ok = 0
                        erros = 0
                        for row in _csv2.reader(_io.StringIO(content)):
                            row = [c.strip() for c in row]
                            if not row or not row[0]:
                                continue
                            if row[0].lower() in ("nome", "name", "paciente"):
                                continue
                            dados_p = {"nome": row[0], "cpf": row[1] if len(row) > 1 else None,
                                       "nascimento": row[2] if len(row) > 2 else None,
                                       "telefone": row[3] if len(row) > 3 else None,
                                       "email": row[4] if len(row) > 4 else None,
                                       "empresa": row[5] if len(row) > 5 else None, "ativo": True}
                            if db.inserir_paciente(dados_p):
                                ok += 1
                            else:
                                erros += 1
                        st.toast(f"Importação concluída: {ok} importados, {erros} com erro.", icon="✅")
                        st.rerun()
                except Exception as ex:
                    st.error(f"Erro ao ler CSV: {ex}")
            st.download_button(
                "⬇️ Baixar modelo CSV",
                data="nome;cpf;nascimento;telefone;email;empresa\nMaria Silva;123.456.789-00;01/01/1990;(11)99999-9999;maria@email.com;Empresa X",
                file_name="modelo_pacientes.csv",
                mime="text/csv",
            )

        with tab2:
            st.markdown("### 💬 Envio de WhatsApp")
            st.caption("Gera link do WhatsApp com mensagem pronta (abre no navegador).")
            pacientes_w = db.listar_pacientes()
            if not pacientes_w:
                st.info("Cadastre pacientes primeiro.")
            else:
                opcoes = {p["nome"]: p["id"] for p in pacientes_w}
                sel = st.selectbox("Paciente", list(opcoes.keys()), key="wpp_pac")
                pac = db.obter_paciente(opcoes[sel])
                telefone = pac.get("telefone") if pac else None
                if telefone:
                    st.info(f"Telefone do paciente: {telefone}")
                    msg = st.text_area("Mensagem", key="wpp_msg", value=f"Olá {sel}! Aqui é da clínica. Gostaríamos de confirmar sua consulta. 😊")
                    numero_limpo = "".join(ch for ch in str(telefone) if ch.isdigit())
                    if numero_limpo.startswith("55"):
                        numero_wpp = numero_limpo
                    else:
                        numero_wpp = "55" + numero_limpo
                    import urllib.parse as _up
                    url = f"https://wa.me/{numero_wpp}?text={_up.quote(msg)}"
                    st.markdown(f"🔗 **Link:** `{url}`")
                    st.link_button("📲 Abrir WhatsApp", url, use_container_width=True)
                else:
                    st.warning("Este paciente não possui telefone cadastrado.")

        with tab3:
            st.markdown("### ⏰ Lembretes de Consultas")
            st.caption("Lembretes criados automaticamente ao agendar (24h antes via SMS e 2h antes via WhatsApp).")
            pendentes = db.listar_lembretes_pendentes()
            if not pendentes:
                st.info("Nenhum lembrete pendente de envio no momento.")
            else:
                df_lem = pd.DataFrame([{
                    "Paciente": l["paciente_nome"] or l.get("agendamento_data") or "",
                    "Canal": l["canal"], "Enviar em": l["data_hora_envio"],
                    "Agendamento": f"{l.get('agendamento_data')} {str(l.get('agendamento_hora'))[:5] if l.get('agendamento_hora') else ''}",
                    "Mensagem": (l["mensagem"] or "")[:60],
                } for l in pendentes])
                st.dataframe(df_lem, use_container_width=True, hide_index=True)
                st.caption("Obs: o envio real por SMS/WhatsApp requer integração com provedores (Twilio, etc.). No momento os lembretes ficam registrados e prontos para envio.")

        with tab4:
            st.markdown("### 📖 Guia Rápido do Sistema")
            guia = [
                ("👥 Pacientes", "Cadastro, prontuário, anamnese, evolução clínica, busca e aniversariantes."),
                ("🏢 Empresas", "Cadastro de empresas, convênios, contratos e faturamento por empresa."),
                ("📅 Agenda", "Agendamentos com conflito de horário, fila de espera, triagem e teleconsulta."),
                ("📋 Docs Clínicos", "Prescrições, atestados e encaminhamentos com geração de PDF."),
                ("📑 Laudos", "Modelos de laudos, emissão com código de autenticação e histórico de versões."),
                ("🤖 IA", "Resumo de paciente, previsão de faltas, OCR de documentos e rascunho de receita."),
                ("💰 Financeiro", "Lançamentos de receitas/despesas, fluxo de caixa, DRE e notas fiscais."),
                ("🔐 Segurança", "Consentimentos LGPD, auditoria, backup e portabilidade de dados."),
                ("☰ Relatórios", "Relatórios gerais, por empresa, tendências e taxa de faltas."),
            ]
            for titulo, desc in guia:
                st.markdown(f"**{titulo}** — {desc}")
            st.markdown("---")
            st.markdown("### 🎯 Dica")
            st.info("Use a IA Assistente na barra lateral para perguntar sobre seus dados (ex: 'Quantos atendimentos houve este mês?').")

class ReportsPage:
    @staticmethod
    def render() -> None:
        render_page_header("📊 Relatórios", "Análises e Exportações")

        tabR1, tabR2, tabR3, tabR4 = st.tabs(["📊 Geral", "🏢 Por Empresa", "📈 Tendências", "❌ Taxa de Faltas"])

        appointments = DatabaseManager.get_all_appointments()

        with tabR1:
            col1, col2 = st.columns(2)
            with col1:
                periodo = st.selectbox("Período", ["Últimos 7 dias", "Últimos 30 dias", "Ano atual", "Tudo"], key="rep_periodo")
            with col2:
                formato = st.selectbox("Formato", ["CSV", "Excel"], key="rep_formato")
            if not appointments:
                st.info("Sem dados para relatório.")
            else:
                df = pd.DataFrame(appointments, columns=[
                    "ID", "Empresa", "Nome", "Modalidade", "Data", "Hora",
                    "Laudo PDF", "Avaliação PDF", "Status", "Observações"
                ])
                if periodo == "Últimos 7 dias":
                    limite = date.today() - timedelta(days=7)
                    df = df[df["Data"].apply(lambda x: _parse_data(x) >= limite)]
                elif periodo == "Últimos 30 dias":
                    limite = date.today() - timedelta(days=30)
                    df = df[df["Data"].apply(lambda x: _parse_data(x) >= limite)]
                elif periodo == "Ano atual":
                    df = df[df["Data"].apply(lambda x: _parse_data(x).year == date.today().year)]

                df.insert(0, "Nº", range(1, len(df) + 1))
                st.markdown("### 🧾 Resumo")
                total_atendimentos = len(df)
                total_empresas = df["Empresa"].nunique() if not df.empty else 0
                total_modalidades = df["Modalidade"].nunique() if not df.empty else 0
                cards = [
                    {"icon": "📋", "title": "Total Atendimentos", "value": total_atendimentos},
                    {"icon": "🏢", "title": "Empresas", "value": total_empresas},
                    {"icon": "🧾", "title": "Modalidades", "value": total_modalidades},
                ]
                display_cards(cards)
                st.markdown("### 📋 Tabela de Atendimentos")
                try:
                    st.dataframe(df, use_container_width=True, height=420)
                except Exception:
                    st.table(df)
                if not df.empty:
                    modal_counts = df["Modalidade"].value_counts()
                    fig = px.bar(x=modal_counts.index, y=modal_counts.values, title="Atendimentos por Modalidade",
                                 color_discrete_sequence=['#1E5631'])
                    fig.update_traces(marker=dict(line=dict(color='rgba(255,255,255,0.2)', width=1)))
                    fig.update_layout(xaxis_title="Modalidade", yaxis_title="Quantidade", height=400, font=dict(color="white"),
                                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown("### ⬇️ Exportar Relatório")
                if formato == "CSV":
                    csv_data = df.to_csv(index=False, sep=";").encode("utf-8-sig")
                    st.download_button("⬇️ Baixar CSV", data=csv_data, file_name="relatorio_atendimentos.csv", mime="text/csv")
                elif formato == "Excel":
                    try:
                        import io
                        buf = io.BytesIO()
                        df.to_excel(buf, index=False, engine="openpyxl")
                        st.download_button(
                            "⬇️ Baixar Excel",
                            data=buf.getvalue(),
                            file_name="relatorio_atendimentos.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except ImportError:
                        st.warning("Para exportar Excel, instale a biblioteca openpyxl: `pip install openpyxl`")

        with tabR2:
            st.markdown("### 🏢 Relatório por Empresa")
            if not appointments:
                st.info("Sem dados de atendimentos.")
            else:
                df_e = pd.DataFrame(appointments, columns=[
                    "ID", "Empresa", "Nome", "Modalidade", "Data", "Hora",
                    "Laudo PDF", "Avaliação PDF", "Status", "Observações"
                ])
                df_e["Data"] = df_e["Data"].apply(lambda x: _parse_data(x))
                grupo = df_e.groupby("Empresa").agg(
                    Atendimentos=("ID", "count"),
                    Pacientes=("Nome", "nunique"),
                    Modalidades=("Modalidade", "nunique"),
                ).reset_index().sort_values("Atendimentos", ascending=False)
                st.dataframe(grupo, use_container_width=True, hide_index=True)
                if not grupo.empty:
                    fig_e = px.bar(grupo, x="Empresa", y="Atendimentos", title="Atendimentos por Empresa",
                                   color="Atendimentos", color_continuous_scale="greens")
                    fig_e.update_layout(height=420, font=dict(color="white"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_e, use_container_width=True)
                st.markdown("#### 💰 Faturamento por Empresa")
                empresas_fat = db.listar_empresas()
                linhas_fat = []
                for e in empresas_fat:
                    fat = db.listar_faturamento_empresa(e["id"])
                    for f in fat:
                        linhas_fat.append({"Empresa": e["nome"], "Período": f"{f['mes']:02d}/{f['ano']}",
                                           "Valor (R$)": float(f["valor_total"] or 0), "Atendimentos": f["quantidade_atendimentos"] or 0})
                if linhas_fat:
                    df_fat = pd.DataFrame(linhas_fat)
                    st.dataframe(df_fat, use_container_width=True, hide_index=True)
                    total_geral = df_fat["Valor (R$)"].sum()
                    st.success(f"💰 **Faturamento total lançado: R$ {total_geral:,.2f}**")
                else:
                    st.caption("Nenhum faturamento lançado. Use Empresas → Faturamento.")

        with tabR3:
            st.markdown("### 📈 Tendências de Atendimentos")
            if not appointments:
                st.info("Sem dados de atendimentos.")
            else:
                df_t = pd.DataFrame(appointments, columns=[
                    "ID", "Empresa", "Nome", "Modalidade", "Data", "Hora",
                    "Laudo PDF", "Avaliação PDF", "Status", "Observações"
                ])
                df_t["Data"] = pd.to_datetime(df_t["Data"], dayfirst=True, errors="coerce")
                df_t = df_t.dropna(subset=["Data"])
                serie = df_t.groupby(df_t["Data"].dt.date).size().reset_index(name="Atendimentos")
                serie.columns = ["Data", "Atendimentos"]
                fig_t = px.line(serie, x="Data", y="Atendimentos", title="Atendimentos por dia",
                                markers=True, color_discrete_sequence=['#4CAF50'])
                fig_t.update_layout(height=400, font=dict(color="white"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_t, use_container_width=True)
                if not serie.empty:
                    media = serie["Atendimentos"].mean()
                    st.metric("Média de atendimentos/dia", f"{media:.1f}")
                st.markdown("#### 📅 Atendimentos por mês")
                df_t["Mês"] = df_t["Data"].dt.to_period("M").astype(str)
                mensal = df_t.groupby("Mês").size().reset_index(name="Atendimentos")
                fig_m = px.bar(mensal, x="Mês", y="Atendimentos", color_discrete_sequence=['#2D7D32'])
                fig_m.update_layout(height=350, font=dict(color="white"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_m, use_container_width=True)

        with tabR4:
            st.markdown("### ❌ Taxa de Faltas (por agendamentos)")
            ags = db.listar_agendamentos()
            if not ags:
                st.info("Sem agendamentos registrados. Use a Agenda para criar agendamentos.")
            else:
                df_f = pd.DataFrame(ags)
                total_ag = len(df_f)
                cancelados = len(df_f[df_f["status"] == "Cancelado"])
                concluidos = len(df_f[df_f["status"].isin(["Concluído", "Em Atendimento", "Check-in"])])
                faltas_estimadas = cancelados
                taxa = (faltas_estimadas / total_ag * 100) if total_ag else 0
                cards_f = [
                    {"icon": "📅", "title": "Agendamentos", "value": total_ag},
                    {"icon": "✅", "title": "Concluídos", "value": concluidos},
                    {"icon": "✖", "title": "Cancelados/Faltas", "value": cancelados},
                    {"icon": "📉", "title": "Taxa de Faltas", "value": f"{taxa:.1f}%"},
                ]
                display_cards(cards_f)
                st.markdown("#### Faltas por médico")
                por_medico = df_f[df_f["status"] == "Cancelado"].groupby("medico").size().reset_index(name="Cancelamentos")
                if not por_medico.empty:
                    fig_f = px.bar(por_medico, x="medico", y="Cancelamentos", title="Cancelamentos por médico",
                                   color_discrete_sequence=['#D32F2F'])
                    fig_f.update_layout(height=350, font=dict(color="white"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_f, use_container_width=True)
                st.markdown("#### Distribuição por status")
                status_counts = df_f["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Quantidade"]
                st.dataframe(status_counts, use_container_width=True, hide_index=True)

class UploadPage:
    @staticmethod
    def render() -> None:
        render_page_header("📤 Upload de Arquivos", "Gerencie arquivos PDF")
        uploaded_file = st.file_uploader("Escolha um arquivo PDF", type=["pdf"])
        if uploaded_file:
            size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            st.info(f"Arquivo: {uploaded_file.name} — {size_mb:.2f} MB")
            if st.button("Salvar Arquivo", type="primary"):
                with st.spinner("Validação IA: Verificando tipo de documento..."):
                    from ai_manager import AIManager
                    is_valid, msg = AIManager.validate_clinical_pdf(uploaded_file.getvalue())
                
                if not is_valid:
                    st.error(f"❌ Upload bloqueado: {msg}")
                else:
                    saved_path = save_uploaded_pdf(uploaded_file)
                    if saved_path:
                        st.toast("Arquivo salvo com sucesso!", icon="✅")
        st.markdown("### 📁 Arquivos Salvos")
        # Listar do banco
        try:
            arquivos = db.listar_arquivos()
        except Exception as e:
            arquivos = []
            st.warning(f"Falha ao listar arquivos do banco: {e}")
        if arquivos:
            for arq in arquivos:
                col1, col2 = st.columns([3, 1])
                with col1:
                    size_kb = (arq.get("size") or 0) // 1024
                    st.write(f"📄 {arq.get('filename','arquivo.pdf')} ({size_kb} KB)")
                with col2:
                    file_id = arq.get("id")
                    if file_id and st.button("Baixar", key=f"dl_db_{file_id}"):
                        reg = db.obter_arquivo_por_id(int(file_id))
                        if reg:
                            st.download_button(
                                label="Clique para baixar",
                                data=reg["content"],
                                file_name=reg.get("filename","arquivo.pdf"),
                                mime=reg.get("content_type","application/pdf"),
                                key=f"download_data_{file_id}"
                            )
        else:
            st.info("Nenhum arquivo no banco ainda.")


class AuthPage:
    @staticmethod
    def render():
        """Página de autenticação Premium."""
        if 'user_authenticated' not in st.session_state:
            st.session_state['user_authenticated'] = False
        if 'user_name' not in st.session_state:
            st.session_state['user_name'] = ''
        if 'login_attempts' not in st.session_state:
            st.session_state['login_attempts'] = 0
        if 'lockout_time' not in st.session_state:
            st.session_state['lockout_time'] = None

        if st.session_state['lockout_time']:
            time_diff = (datetime.now() - st.session_state['lockout_time']).total_seconds()
            if time_diff < 30:
                st.error(f"🚨 Muitas tentativas falhas. Tente novamente em {int(30 - time_diff)} segundos.")
                return
            else:
                st.session_state['lockout_time'] = None
                st.session_state['login_attempts'] = 0

        # ── CSS global da tela de login ──
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
            [data-testid="stHeader"], footer, #MainMenu { display: none !important; }
            [data-testid="stAppViewContainer"] {
                background-image: url("data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wCEAAQGBgkHCQkJCQkLCQoJCwsLCwsLCw0KDAsMCg0NDQ0ODg0NDQ0MEA8QDA0OEBAQEA4PEhISDxIRERIUEhQSEg4BBAUFCAYIBwgIBwkHCAcJCAgHBwgICgcIBwgHCgoJCAkJCAkKCQkJBwkJCQoKCwsKCgoICQgKCgoKCg8QDw8Pfv/CABEIBRwC4AMBIgACEQEDEQH/xAD1AAABBQEBAQEAAAAAAAAAAAADAQIEBQYHAAgJAQACAwEBAQAAAAAAAAAAAAABAgADBAUGBxAAAQQCAgICAwEBAQAAAAAAAQACAwQFEQYSEBMUFgcVIDAXQBEAAQMEAwEBAQEAAAAAAAAAAgABAwQQERITFCAwBRVAEgABAgIGBQcJBQYGAgIDAAMBAAIRIQMSMUFRYRAicYGRMlJyobHB8BMgIzBCYpLR4QRTgqKyQGNzwtLxJDNDUJPiYIMUs6PD8qDT4xMAAgEDAwMDAwMDBQEAAAAAAAERECAhMUBRMFBhQXGBkaGxAiLwEmCQMlJwwdGA/9oACAEBAAAAAOxPI0j2Djx/Ocqqr3ucque5VVVVV8RSK5SeVV857ld73lVfK97XKqr5XeXz1ci+973lVPeXzebMN5SNZHhCe5Xu8rler1er1c5CKqq573q96OXxXoq+Vy+c93n+8qO8rl89FV/ve95V8qeVfJzFCOYdBBhxfO8pF89yqrnkVzlc57neV5Huc9zvOIqr7z1V/i+VfKvnL5XKqu95feTzl8qe8vvcwQhGP8IcKvY5/n+cqq9yv88j3K5z3Pcrnke97lUhPKvnK5xFVfL5VVzld53l8vvKvlavl973vcucRXqgww62vUikV6uV7nqrnOe8jnuUj3OeR5CK4j3OXznOe5fL5Xqvno5yKRUXyL73vL5VRPJzBSq/yMBEraQBCOepHOVyve96kKpHOcQj3kcUpSK4j3q5VcVVVfK5HK5VVHuVfKip5UVU973k5ipVc5Aii1tBVOK4j3K5znPVz3vK97yve8pCEIYhnve8qu85SOcrlVzvK5yOc5HKqe95U97yO8nvcyadXO8EMWvos/4rnq571ernPe5z3PeV73lKYpikIUxlc4j1VXOc9z3ed5Vci+Vy+VfL73kVFRWe5whnKvhCiV1JQw1I/wA56ue571I8hHq4pXPeQpJBiEKUpXvV73OVXq571f5Vcqr7y+8qeVUTy+95Pc9Qr1VRx4kCloa2GpEV73Oc95PEI95HvcR7yFKQxCmIYhCvIRzle57nOeq+c9FV/lTy+8qeT3lT3kxTlKqOHHiQKagp6Yave9znPcR7nveQj3uUjiFI8hCFeV5CPIR7nOcrnK9yu8rvL5U8i+97yeRfJ5PQTMMjvMjRYNLQ0mMzCL7xHueQkl6+cRz3Kr1e97lcRyor3+kPc4ryOI8nveQbGuV7RtV6e81q+VXuVOrGGdrnDjRoFNRUHIcFJIV7yOe5z1d5XL57nOVznkV7lc9Xvc5/vOVHu8rn+VF97z1RfOTy+Xy+8qKv0qcMhrvNjRYVLRUPIsUd5COe96vVXL5z3PVzle9xHvIpHOI57nvG5XKqqrlcj1eqKq+8nlRXeTy+976GMwi+82NGgVFDR8ixpiEcV7nK5XoVyue4jn+VziPI5zyvc570f5yuVfOeqr7zvOTzneVFXyr7ye8vu+Ee5r2+jxINNSUXH8mZ5nFd57iee9XOe5znq573Oe8j3vc8io53iuc5feV6Kjlcnnec5fIvlVfIvlXuvjq1USPHr6amouP5Yhiuc5xHq5z3PernPI5VeR5FI95Fcr1e53neXyv89VXzvKqqqr5F8vl8qKnu4KZyOa0EeBTU1ByPLEkK573Ec9SPe5zlI5yvcpSOe8j1e571VfOc1znq/wA7zvK5FV3l97yovlT3kVO3PI5VZ4EaDS01HyLMFK5xCOc4j3q57nv897nuc97yue4jn+f53lequcrl8quX3lRXoqKvk95fe95E7YZ6qiIOLBpaej5NliucV73EI56vc8jvOe9z1e57yvI57nK5fK5z/O853l8q+VfeVVTy+8qL7y+VE7PK85fIgocSlpqTlWTK4hXPeZVe95HK9XEcrnOe4r3EI9yPd7xPPd5XOX3lVfe97z/e8i+VPOTyr7y9lO/z0RqQYtLS0nMMaR0h7nme5XEe97nPc9XKriuI4j3uc5Vd5yud5XqqO95feXyOVUXyp73l8nnO92SQrntRGQ4lPR0vM8U8kh7yFc5SPI57nqRVVzle95CEc5yu8quV/nK/3vL5fe8vvKq+95UX3kR3lV3ZTIRVRqQodPR0vNcS4xyvK5ykcZ7nOe5zlc56+IpCkf5yvV7fOc4vve95yp5U8qr73vKqeX3vI5F92iQIhFRiQ4dNR0POsOQxilI9XEeR6vc57lcrnOQiuMU2b0biI9PIawmoRFXzkVVVFaquRU97zk95yJ7p8hjnEaxsauqaDP8AOsW+QYhiu85o/OI5znuc9XPMYj/FMb5y+iyO85fNPBy5JkpDWxvRY3m+Rie8qv8AO8rEa3yO+ipLHOL4bI9VWZ3O85yDznKdz1bBzgjlJ7zyq8r32V+dfPdK+R/ojZvX0Wcw9bA9IYNLQjBC8qeK9RI5BOYiFI55R/QUoRVMgmgqqrN5Xn2UIaQUhnJHqM99N7d5Cqq+953J+WaSUvkaT5luOt7titWQW6zG6mEOyR5x4pJTGqT1c4b4SRWHOT3prtdJYVzvDSPVVWYx+CyxykNyCf1ckWlqvp3blK93nq5fcj5BpJfm0sqLzHCdi29xUgy3WV3+J6JOkOeWR4itkQyNG9lcQY48BZUv0hDkkzVK5xY7Y1XVZXF4XLSY+PsOXzOo60VNXfTG6pqO7r5s08c2j49xy/nPZxbosSm57oYXSgZfb9MTq+I3s2U6VGtI73EDHO9oTQXwQDAhZZTm9N+NvrmwKrjR2x6qoyWIxuSlcUz7uozl5jb9QgfSvQMjFA+xrDWNlquO8Uu7DyclbrMatRb0/wBC8u6xpF7RgNvaySOZYAe9nhSAsH4DhQmgjknyZZ/SfzY+kfomShHibHqajH4PJZQnNcvb9Yh8l6LNjZn6e6/yA1ribfpOeAe85zy2zlsHmuX9VZjqbYdIzHdJVW/ufOt5PJZqVTIcLiCdHY6MMEIMQUibOlzmu/My2+9rjykGgKmlxnPcvlV4Lfdm4zbXNPpo2OL9x4nlH0Vl+fbjU85uTRRyBws7jcPrtTy+Hv6jsXUsz4vb8H0G0mWxWT/HPGVyq30Svjiq4VfHuJ9pYSnl/N6N9Odc857Gx6uixXN8xlpGV1ttw2y0FfV2tXD+k7DiXab3j3VX4n64ylMJZFU/5Om5zZ4jO9Qz/wBVUx3m7XieqWllKdOkORQkRDwjxYcSLBhUore9sZFiYnxfyTXfXDVML0SuoMNzXK5WS7OZGxn0dxVydJ2vovDMLpPoD55vep83+t+e/Mm1wnScr3f5PhSczawtDq+xRDGkdfyPXJt7JmHK1zxqkc6JDDDSDT0y2mhmutVf8H8J1f3FPUjEjVVFz7m2XyRI+HixrakTWNt/qnVfMuKldpo+d9aqPq74s2V5wS6+hL35Robvn8vTRNf2wB5MnqGN6TdEsJ0gZpMRxldGmQRQ4bK+DSGtbm09Zuk/kNSdy+r+gvd4casoub8zz/JqW8fni6Nmeu5dLvfoDh2NXqG7+dt5o/rD4Zurm+4x1js3yjlbmizt/wC6P02dJkyux8/vbrR3hrNSDnKJwT+LHDEhxKaJDubK2LZEj/kH1DYb/wChi+80NTTcx5NUcXr+hXvt1tvmDO7a15Fc1eslyNB1n5w0PQPrz4Li6LV2xes/JeS0OvZay9vYVkqSbdQSsKIklpG2MlUlNYatECMFqsUp50mUT86uv73JfZRfIkWtpudcQpObC1Wj7FKsOGcx7LVcou8beOm2ew50HqX2VxP54iaHtNJ1f5Ix3f8ApdnIttX0H49sZC1fSlZ5sGYQEYz2tKgzC9H8rhnb47mlXgzeufP/AN4mVrY1dUc/+fs7nih1/b7qUOJpvmbmH0TwO6yFxcN1uA3f2n8bFy4ex13XvkrGd86nbnttN0L5DsDkzP0XFrIp4Ej0UBGt8Z4PMiklDjK97ysVH8NqO28G+0LlUZGrqnC/OGVzxx63u+lmFtYHzXyj6x2PxtXxpt10Dnmz+0PmHhtd0i50fU/k3Id26tdybHUbj5VmSXYXSODLPKUjJCNleENSIjSNevpBXv8AEfw7G/QvIvo/pEOSkatqcZ8yYuhOlz3nY21hIo/nLlf13qwS2KUeQ5/9YfOWWoarrlD2L5MyHZut3s+x0W0+ZbIzs71VkEBvNLHYg2kGOQwRAlf5pfK1g0fx7j/Wa3u/euHbvZAranIfLGJoC+H0XTXc6Snz7RfYOznTveWvyXJ/oLzCuDX5P5zwvQOrS5Fnqen8EupLrLpjnglqYzWDQDIqTFkE88fgOeZjHwgfLBvRNZ9YfPHRt5EhU/NeKXEqUrvNeMbZDYpWp5xZClYhH+YrpIiIEIkf4Njo97tYEshWiYQqNLJeMYvAipG8KVOlLKGc/wAIItmn2r899I3oaiq51wCzK9SvX3ns8pCtUvmqXwSv87xjKUjnFOR3klJ1bRRrGT5YyR08/wApnAGJkMEWIR9n6RIOUv5kibvrL7y+eelbwFbUZX5+45VNUryEeVzzGe5z195G+MUsg0idJmTbKwtrW2tbGzwtB3jrrp94wgmOc3wBnMJg4DK9eWanbSrJ3kVfxeR20rP0P+d+k7+NW0ua47zLl3imNIKYjlIvlIZ6L7xzPXzyOIRzpBSEdK0Gmd3LqrLDUpQy4t88cBKiTZyspdV1fTzuWanU2Ryy58dv4nsPq7b9C/nfpXQI9XTZvkPKubveYsgp3+ZXB85Xq7zi21vJVSue95XyDlNJnWs53dOmwbPWkhHj2URRRbT0JopNLQ0Gi5Zqbm6u4976Q78f20Wa7L9ucU6PvIMGoz/HeQYAxTPkkM4NTKtF8RXL4K12lt1cpCeMR8o8iROmSpDu7dHqbjdtIpxRI0+sBLzV/aVETE0Gt5brjaTePbEJYfnfH4pzX6A+teU9H39XWwKPiXPeREnHIcxXBpNX9GSHIhmM9SfOGouHq8jnEeSRKkyp0k7yd66BQ323jWYnx2xIUkos7oZtdFwOf23Lta3U76fRjuvfnPs/nvkX0R9Rcz6P0Spr4NLyV+a507CekyTvBRbz6jyvoMqXAk2rfk3TXz3PUlXdeJIkyp0qQZ3u/wC8oL3erJV1LEMtJocdsa9lnT85zu85jr4eu6lIrhy4X5+7L514/wB8+oud9K6LVV8Cj5HZ6vkdTt8Xxx01wqPpP1DkIec5t0LnXadL75K0WhL5zq9me3/pEibPkmM5PoLc57QdHbTWUNY0Gvk2UqstqzWZnlGX6HzHZVm06Jb5PUwCfn7sPm3j/ffpnD9H6RW11fQ8fsdjyGB9Cc/wKci8yg6r9PZGvh8B6Rz7pPW/fJVzpjOV+Kxu+0M8r7CxmnK5v0Du85f718kedjFZyPqee3t/no97nuV5bo/MdrTbTsMU7SQvzu6J8x8g7z9N5DofTautgZ7j1zseMQfofnuOrt781RKPsH03zZlxwK7pnfSDfk2dqpPve9S4PFdA1Gb6N2AY4zmfQW5zmj3UV2SuchRRbjXc/wCv23uc6qDyvKdQ5dtqHcdhIlQ20/MDtvyryTuf05m+hdPq6yHmuP3Wr4zB+jefYusm8fpKnt30pw6l3WToA5f6wB8pP1plVEpuRgsX9Pn0Pfreq8z6B3Gb0nT8vEp6nWQ7bD65trcQhWWS5PlOq8v22c3O+mGjXDfzp6T8p8j+g/pDP7zqdXTDzHIbLccPgfR+BwtdlRcwid6+jeVcqk6bPR8r9Yj+UvauSqxuaUdUpbfqnLtP0vscEA/oPaZ3Q7uzztRR9FxFPqcppJet8YOY45leqcx2+Y33S6nD77Rv/NrqPyZzX6M73UbXq1dnn5Xkknc8Rg/QmQ57X8i6586u+gPojj2AysrrPP8AC/YoflJuqkeRcHgN02s12w23Yshb4y8jfQGwzmi6W6NXRD2DonPR9Ur7cBs1xbK9U5ptcru+iUgbPXH/ADT6l8jVnXfoWj2fWKmhLkuOzdzxWD3/ACvN4Hzd9WfLKfQn0Rxflq6KbncT9kw/leJqpLQi5RrV2OPf07P/AFxxDocK2o+/a/OaLZEfXZoeuHCPmNPolFBruN4XrvPNjiepWs2001bmPhHpXyFobn6sy246jWUMjI8Rtt7xGq+gsvy4HzF9N8Bg/Qv0Rwv53s+oL7m32TXfKsrWuraENJRbTV9Ixhuod/8AnrQ2wInctfn9Ht311jV0cO3jydNGfGjlDyTBbLO6jC93XZ1oQ2PwTrPkLcy/rXG7jpUTPnyPD7vccYo/oHL8n98y94wuM+gfojmXN3l0muxnTYnyr2fbzs1xjnd3Dm7Hp3KLDu31N835fS6ad0HY0EmaJwYRAR5UhIiiPNhNq8nIseTfSV1SjsPQ/mgfyhrrv6959t+nwc8fLcFutrx7O97zXJzfNvR9zwnvX0PEMUTXMj5r5X7RtvZnjmWlSy2vSJMGo/Qb5kXJ9WTsuvoLnokpEpouFo9Lq72w5xsIOXrw56ZkLwWys+YdCxfaKD83xZ/Odb+wOYbXqNdnzZb5qtdnzWj6vH5G7gd337516r0IplGhGwaHkWw3CZjndMa7H4Ok6xedJwXULbLRe9aqgvemvzxzz80ayxOKuttfR+TaOvzt9zbX6qLGwOg6Nd0/5wueO9+uOR7DqNVSOynyXd6Kkj6MNM+k9f0MxJKIzz3rHEwpAQYmRxmxzd3tLvpmPqtD9Fc2k9x1NDoemMrwW0CvFltNoYKmjz8VUZzRc022trN7wTX9M530z8znNJM+x+Fa/s1dU0mS+Q9IaWdXEbIVUGrvO8JrzgZ5HCjQIPNIq2fUI/Ge+Y/dSdubu2modJ02kiXgM5HsYsnR5XP9BkOw9JTXHNt5p66BaZTn/YKX4N823svu35t2XahU+VpeVYXlcgpDPKYpCK8iqqq571er3lkcQPf3e5kRcJ2bG6eTZxe9aSi0fRq5+XDSgNv2Ry2Ev1LS5avtucbq3srXltuS3lfnd5upi/ePzPse1CpMtVc/wHHvHkGKYrzFequJ5yud5zleQsbntB0vmXcrTnO5MS3kub9A6ah02osTZjH0nR9G3n+sqNFIs67L85pdhz3ag1244xyLb9TzvxG1Nun2f83a7tgqTKVGJwHHiGKY5CmJ4jnEVVd5XPcpVeRZWY4z0nZ5fo06FraIrfobU0N/M1qYDifUtxZTMPkOgZKVJj3XNaXf882dXvNpyklwI/wS1nRT/XHzho+7R6XJU+PwfHDlMYpjq4pHud5FVVe9znOIUnLdVoJxky9jsZteo/ozV0V5tvTsrw227XMbzpA4TXcx6PruaUvROe7Gl2G9h4izJsPzcWPt+j/QPznfd6jZ/JVeSwnHTnMc5XOKUqkcjfL5z3Ocrykdi7c19LJxDoXXsqbwvozXUGhUFJJkUQ+tMme5Zi6Qn1Fh+Z0nRee7Cl1fS86znGxyfyE0Wm+iOmYV1zWwINblsHx6Uc0kziPKUhCeRiNIrlc57yF8UqS08j9LRvUX0brKLQ7LDUNiHFSe28r0FlZ8557nNF2jnFP0HAbCm2upn0jLm+/M8S3/ANV6d8cNfnqyrzeB49MkFlEeUjzFKqtajfPcqleV71OSPbx/TubdC0kepF9Ga6k0ur4HRlJk6Lsz811uDk+UdovJvOKne4XW0+p1Vmyorb78+2anM/cpngFX5+qpqDnvIpsmQchCvIUrnOa1G+c5SlI9zzFfQbqoI7G3ei2NhzT6O1lPfu+b95uLzhl9rZd3znr2f5l7cXfMqvd4TVVa8c+s6Hnup6P+d4dv76ykOCCBnqyipOdclnyJJSkeQx20WxrJYETyke4zyPM8lDpAmKZwiberzH0ZrajQzc8zbfMX0LntTyzovHYfNPqzh/TtBzyt3WJ01SDmlv16TSXXwXa2ffOuk9HFX0FZnKfnvJLCRKKZXnKXG6z12AQvI5xHFeUhXu5/pb9xSvZG3TKHv+orL68scq2vdoKdvuG0VLqqk30Tz6BtMVpqzY4+j3tvzM/wr0uP9pWzvRo0KirMxU8+5NYnkGI98gnsJKvnD07We8RXEIYpFU0KWQ7/AC03SZeR+hNTVXVF0Dn+xHA4noc5QNBp5JcZ9Kc1g7HF6auvuLQfoim7FT/mHtNX9Tn96NFhUlXlKjBcosDySkKYgM3o+cVBbyz3diNqq4xyEWrt+ZdPIUj3PfbtqPo/T1l1m95wDqU8HJ7M+Y5VrS9ej5XsvOYusx2lgyKYE/tU6P8Amjl/srpjnMjxoFPU4+qw3KJ8k7znNRR9VYcI1FxfWd9Sz46Pccjnvx/UctaPKpFVUcz6Q1Vfa6KNmL+bUXHKuU5avwvd+qaSe3nsTUZPQxdZsqOfalrvzC7P9JyXowEWFUUmRq8PymbLdIMzPXt0bNZDqRoPTLjYfPlgxXkc6JLmsLKK73vL5Vb9JayvtrWBW1wNdKw3CMfeL0QOy65mcHD0eY0ES13NHqJowfOG+lGe1I8eDVZ/JVWP5NKOUeBut7KkSOaTezV2J2mr6HL4QLylUhbirnPe5V85EVw/orZRrUMaPHzu85/pOHRIs3V8x0XcLvFQdPmLyJtclX9XewXOZJiu8MMaFWZXNVGU49MkEydN0y2JJlcvtOzzo3eOwS/mLkcbziyJJTOc5zvKvvI5WbDretsotFT5jbZPZ1PHb2lr7/6ZlEymMhaTP3EbY6CpuAHh82KUz0EIEGryOfqsnxydXxtXhepMJKk46l7v9Kdgj8d4JSxxFlSJB3E85PL73l8vldiOl9s6a/PZbhWk011gIeY6DGH366l5XK1+hprWHrrxra67Fyw7zkQQo8OoyNDW4nj9L7eT8P0QRJpZNl98UvIeNVoPGkSjlI9ysarfJ5UX3nG5V0HpWX+oMXo8LZWPSav44bsJdf02ft4lDAvqq0h6fSQ4bLGTykhjPQYY8Snx9NW4jgRtaexyO6GSWeXtIlY0L5UyZKMR6+RrWqxjEavvKp+J9R6hjO/zM3fADpg8Mz2yxP1VbZaxFTV97XWMK7tI10AruYEMZfJFjxKnH1NbjuNnJLs8zsBllFkFc+RLsLCZJO53kRiIxBs8g2eRHF4N1LrmK+gb3l1dTdG1dzgsD1m70QH4m5q4FxElRpxbaVXzjcxKYzlbGjxKnK1NRjuLSJEuxzmtCWWUxDzbKxsZkgh3r5WsYMbRBYnhNb4juAdH65T972OB4nzbe/T1zRwL1ki5DEiU0C6jHj6OwNGj+n8tfKI7zBRYtVnaSjxvE5kiZPodUEkk55s+xsrGWaRKkl94QRNaAYgBREYxpHfP3R+pRuydM47zuNruu3oIomMGMLDQL9qwWPeR7lzBZb3K0EeLWUVBncbxGdLk2Gd10Q8udNsJ86wmSp8w5HeY2OBrBAGAQ2+aLz3/ADx1joMHsHVuNc+TbdbSDEjhGMQRR4/S3VeIkGKYjneNJK7yAjxK6mzecxXEbKTJsM7roc2fNmSpCzrWzsphTO8wYo40EEIxiYjRKQvy32XqdT2rq/C8ZJ2vV5whMY0IxAACScDzle96uxhpBVVgQRa2qzGYxHE7OTJsc1sY8yfIOtP2Gzmyiv51okECPKsPMG0QxiYNg/FL8k9Z7TM6d1XiuXm7zeCggCAQI4giGNpDFe8hXr4xiucwIY1dV5nJ4PidlKmWee10eXNMmh459L2MwpmfN3So0WunQtNp18ghjZHExg2D+c77sPQrz6Q5Jx+Z03sBlaNqeaNGN955HvVXO9zE5TKrBhj11bmshgOIWUyfZZzYBkTC1exxHZ5c0yM4xoUHGn0tD1K3f5jGCCMYNJ1WIIMy5ke84w2oq+a1E8i+8qe87yKiSDFM5WCGGurcxj+d8RtJc6zodWM8r2V6jIsZLWLZkr/KGvzWL0PRLB7GNY2OwDL2IZHlRFIR6uGrvI/yuVVej1crve914xDq9ghgrq7L4/mnF7CXNtaLWhNJ9g+v106UGHd34NlQZgWIuMNZazXyVQTRDbFiRosHxHuK4jyke9Xe8jnK56uVyvV/l99GSHHc8Qxhrq3L4/mHFbGROs6rThkSwc86T0SSRzBeeoA17srXwp+5tCtGxjRBEJUjtc/z/FUqr7yL5XEc9XOV71Xy++iDuOQggjFW1+VxvKOLzZcy0rdKGZLruddJ3zze8JsNhB7XCc70nWodYU/msYwYmIiq1HKqeajmtcxfOcYhHq9VVXqqfSZ0lFIIIh1tblsPyHiVgWVPWRHvrCt570/oKuaOK4ooyWzamB1bBQtN5zGsaIbGJ5E83zVYwUYfkariGlSCuVfO8qqq/WB2yivYAYYNTl8DwrklIsq0vB05Z+r5z2jopTJ5yxwDjza6HC6hxcG8C9oWN8IbPK1ERqNGuov08VhCIyDjRR3e87yOe5/2wXxyvYIQoNTl+ZfNGfzG91l9z7c9DB8rfUtTrp8gj/MaEEdg8wkXfZ1b1XKpCPeQpinPJUriP9wyT1y1kLiY/vSIm6unM85fKQntO9JBSMEFkGoy/AM3GzU3QXuc0l+SRpZs45ZU6Uo5IamTynjtkbU7e1NczbCz+cdpe3Fpaz5tgsqYRfSa+DyukpEZ57lNK7bplV7nOR3nYArJJFaITYFRyHDlQhp1geZIMsmTLNzXcbrUj5PVLLg66XyvJazcTsl11xuX/O3bNVbW1xPFyvrensCL4r6Y6OlJ5PMGwSEV5HEc9fcyK2U7yCA6v5/zMr/EkSTypBJBzEeLj2d9vdns9lPsafKxqPG9Xc/J9JaSk+QtffT5UiQsg5iq1GD3vREEew95BwosM01xCGIvve5gYczysDHLkeVTUcvny5MiQQxylKVoKHmOZrdts7INbVmjdgviU0zTlDQZL0kynMZ5PO95j9NejaAt/wCFS5ykxuo6g4xJLvL73LjNku8yPHBy4nveTykfLOVXnLILIKUUCkwt9Nkayd5yob3NxK+QhHkcciuL7yt94okG7U6yqqMdi82/tm5aR73K1nssRsl3hxo/zdzQ6+I/yi8PzQu8ET0eg/eKozBedySnNe5zlK4RVRXBcjVcJlr0/SXWeqq6vpKY5tXRchmHIb3ieJ9r+bLVBxY/yZjLsh1a7w0KP3hsbGK4Q2p4itCUr3K47/CP551J5hle0SeY5vTrDnFTXOWQTzZxujYDGzkkO8jgx/tDyyPeBHi/HPLLZ84IX+IhHKNGxisaRjXKvhF8cjXlI96vGXxAsc1itaJGJ9IYXnMuRMDJM4z7Gf1v4omSXuVnmov6CsKZUDHrPj3gUCu0cPKyXkc9XuVVf7y+V6+VCecvlRXuZ53k8jVa1XsY0vfejcvBNWxbIkDmtsr3UfAEkhimdXNvIP6ltIRyAj5j5R5Nn5DAZA5XqQiqrlVVVXo73nKrvL5UKrUd5Hj8jEUnharsfVuK1UqSOw9NlhlOsdRT/Hco5nu5hD9737No6Qgxg538688pqyPHyRCvUjnq5XeVVV/l95X+VXKqqrve8itajU84vS9h2vlOJ9N8syXJ8Upr7Wcg+dM5d6f2awVtNCD9gXOkDF6JybiXPaWpDGyJSvcr3ucqqvnK5VVFV3lI56K97moisaxFT2t6t1nHYeqFOksmzTNsHy7Ld/KPF8r43RaOn0AnTf1VIUgWpA4lynBUddFh5MpXOe573eV3nKqr7zl85yveVyvIrWo5rBNJ6N1nr+w5FknulPPMmzGyUHoemfnrExMRS72mFMSZ+rbzqFqVfA+fYWlrYEbJlI9z3PJ53lVyu95yecq+cSXsu4bk9ADMVMbLc+QDPTzdO+j+S4Sv9JmrYzFmkfDl6S1+ITn5zATaxz0N3C/XMxhM8yi+f8biaGugRsq4jnPeRyu87yqqu87y+Rzndb+xqSRJaeaSwv3cp57E7R0+HiuA42kCQh5U2U2XKWEu1yXyvJkMxNIbZZiRY579j3lajBZn5/zGNz9bBi5dS+eVz3ef7zl87z1d5U85WfZFzTjc0Esh9NZXEznOZnDzVNQjjpNnDtvLMfOxvQrriXCpL1dWYrx2Fg/swqu82PjuA0ORz9bBiZdXue8r/KrvKrlVVd5FVV7r1+ugMAr1jS1QsaDHblJz4AxHNNdYelFkFw3T9D8pYJYxjyovOk95P2aa47RwsLwKtyufqYkPMI9zyFcrkcqu8rnL5Fd5Z31aaEBYxiiCVoxjECPj/XMdyFLLnqd5pBcV0Don59ZGuQmw0vs1jE8v7MI6Skeq55w2Hls5Ux4eZa9xCEc5UVy+cqv8q+Xy9H7FbVfjRhPUPmjSOF0LGR9KoDGLImlfKdJh1OysfiXDp73rDR32Cq11P63o+UkKm5fyCHm8vVAhZlhHFeRzvL5Vd56uRzk8q9n3OkoxEGJ82OJiAjRpdfjIevIB7ynlSnzVfVu1uT+aIeTgJ7z7CdUTtd+qXjSBwaDknNIOczFUGFmRuK95FIiuXyqqk85UVV73oNVVwSeYIwFZDGMb6/IQNNJMZ5HGsXkOlLd6TjHG1bUQwUqPKQof2OU5B12a47hKylylXHhZdpCPeRVc5fOXyucqq5Fd9GWGhrYPplbKkNAEAIp31eKdZ2JZQ5jpJpJj+x/QNB8n44qvIWkxwUX3v2ZdIUFblOM5CspsrVxImW8V7iOc5XqrvK5/l8q+X300/U1+Us5EMs2HHkxawznU+MS4NZ+kEJJlEkHdjtnsvg8ziOj0lhfZTOza/wB+zJyeh1uQ4lRVNJmKyDGzDCOe9Ckc7zvOd56vRVRRfWELUV+dlyKWyt6wkaFBlK6sxEbSLb+e+c4sxStodUP5GCGcTCgdpNKvNU0n67mc2FV4viNZUUmaroEbOAI5xHOJ5yqr1V3nqvvON9TRdFQVNoOFPtqyJLhVB3Op8pV6KbNdKLJMV8o1P69xnziGGltk4iLr7fMyF/XUrhQKbD8ShVlBRVlfHzcYrnuI9yq7z1cqq5XKr73va6vOVU6vjaObSq2qV75FLjKXT2E0jpjpMk8gtGTQcL5ML02BJoK9DDPucX+yZFiwKTA8YjVtBS1kKNmAE8ryEcvlc57vK5z3L5bzu7dbnKqwqpGgm0qpBhSJcaFz2p2st8tTypRSHLkNrN+QaQaHtKCNU+9557D9hisi1tFzzj7KqipqqNFr5RnEIQj3Pe97iuV7lXzGSOkLtcyNlNYaidnCgq4856RMBS6+eUx5Msk0c4uP0k/5ff5gqqBkU97yp79oygi1mb5xyttTTU1TDhaS388hTFI5xFI57nK9V95XVpOoZotbWW+oLn2npGWcb1di6DWz5ySJEo0l5y52/wA9zeOBqZKhiUnvJ73v2kdGjVWX5pzdKeopa2DGvbZzzOKdxXPeqle9zkVFcrp2nqI8CLP2LaYLs9JsgmrcHmd5NfIlSDkkkkRASuT1cYKNxEG3jU9V5E9+0vosaly/LMK2pqaasqLOdbqpHvIZ7iFcrjeI5Wp5yOtNRTQa1lvrGU7K2BMlxPQ8nj9tZFOWcYhiyKkvP87EBGQvP1sLu0l0YIYf1uHGiUmV5Lk2VNTT1cSfLtBFc8hSGc95fK55CL5jveda6Okqob7rVBqh11dLmQJNfnMbpriW+RMJMYSTlMvWxIgIrR4SVZ3z5tjIlv8A0YHFh0OT5HnB1FXT1cpp7ESnSQ5xiPMVyuUhHNRyql3e09RELe6mJUhDQ202sVmbxWg0JCznOlNzuH1FVChAjRGZmssTXN2S2lS/foWyNBz+S5BSR6yrp4s2C6aNTkOQz3kcR5XeVVXzSO9fXlLTjLbaqDXxq2JYWtRLrqHDT72ZKnMZBg0PLu2LQxI8WLBxFq+fPvp3r8Nx9/Ci1+cyfH6uFXVdTLBQ1dVId4qmUjnNIpCCYVznohF6B0qjqQyLjWV0KtixDXUX0Km49Ds7OtVQxCjynYZvLBoIAI06RIsrOVYtvhfooGJAzWQ5BBrYVZGlZ6lytY/zHncV6o0zjkr0kF85r/L1br+fqwSrbUxKyNTsl2ggDoONYjX6fCEasRig6J0P5u8Mg/OtLOTOtJxbyp0H6Dhh1mcw3JY1ZGr5A8TBwfiC9Ic47TBFLI6RXKUniecvuu9UoK+OW42oc8GjZNvokWNWcQyu41PK3lZHgmHquw8Lz7fI1ZNna6ZtzOW6Z9/hh1mawHLY1bEWVm8pS5Ujokkj3k94ZWllMivc5z0d5vZel1NMhrfaRM4lLDtb+PEbQcOznQNfxoUvyVTfWvW6bkSIo1ly5MmwvrnQy7b7ijxKzMc153DiV9omHo8XEf5PeMR/vNFFsJwoxfK5yG8ztXQ6Sq8e62MKhi0j5egAGrr+HZ/oew4vGkvUEIBej7X55YrfDmTZMsxZ3iyf1AjwqrMcuxVWA0ukyNDhS+RX+KV3lHFLNkBjOI5CI93u1bapqXSrrZ12ZZVKbSer49Vwaj6Pr+PVp5LXRIotR2X5yrXqgj2cqUaXLJLJ+m8aFT5jlGUrQ3MbI0WMpE816PJMTyMd40iPGcUTite4vZ9jSV8l13sK7NsqmS9IeuqR/PdZ0Db8ZjjdIUQGm6bj8G3yKKxlzzSJVgp/0zDApMvyTOwTWtRhq/nqOGxzjLJY5nlccsIav80jHvN2TU1ld6foNRByjaxsm/m1kWJ8812+3fGBMecYmxfbW75PEChALYS7CRKLKd+nUeBR5XkdNBu0yebzeYRRE897iMK0bnyS1nvEa0gypI69rqeGkrQ6umqIEMErQzKoMHgFPveg8UkRnG8gmQ7jqHGYwkR9aGXNnEkyZf6fRoefyHJ6xLsPOqzDwSs89hFM5/hlESQanIiKwqPafq+0o4iSNFpYGeiwgzNHJqBxPnqp3PS+JGrDzXyBJHr+m5vPNYwp40KBHeWX79aokGgxXLq+/FQZOp5+d0VTtMp/He0bXTFqHeaNSObI90XeUYRzLjYVVAGtSToZVW2LwCr2HTONtGCVKlPrn1GivcgpI77OR4USHHU36gxYFDg+bj0EXDVGPqFSsnHQqyWSkHBmLNDB80QyuM3z9/uqeHX2Gh1UCkr4qyNEWDHTgVRren8i8yGSaWQD0Or6LlXJGkzNFGaiLIJ9/RK6k53gND7OZWBzsih9KY8jiDMsN5EmCjsUIlMUSk3uwj5qLa6i8iQ6yuMa6m1KROEV+r6fyJ6RkPIkkYzE9DjDHFfOuLETSPZK+7YlVR84yOnh46jzObe2qmy1KkgNYoH2DRRpjWqWM6UGJIkb7ZwcnDutVfVcCLS2Mm1LCPi+JG2HVOCAgW7zzRyJsCnt9TBjFgWkp8mKZGB/QWHVUXNATKnCQsKF8ZXlQzCp6rEcwJFcpreEekdIBImwui7rNZod1f6yrqmURbYtxRWvLOVm3HUvnYaLJtqO2sq1YvuhUwZWlj0NrIHLgMn/AHpBqaHnFhCzuYqsHIWJIaQ7lBQzhQrawXKWQCSFCODaxPTHM19VUMv9R0aBSFz4LyXMEzm/KAdN6X8+w7X0+ISc58S0zG1jz5Pop4tgsAvh/oJBqs3lfV+Dr8jUHHCsBSisk0qS62qnygKeFPhSq6XVnkuhW2YKKJIlW3b7jPDqIVrcSHB5jzAvQOjcAhylMAs+GhLaskz7HTVYnyJc6HCZL+64NVniZLNZeDz0hI8ez8UvmUaViHW4A0LTNWXBFBcop+WnRYxTF0fXT1tcKyuDoPmvOk2fSeGxCRnTZD2QHPqJ2zlXkjOzJV5Fk1sSL97QalgMhzyozmVl+iesUMV0MUGBLRgJzWzaZY8kMoMU1Ha4555gQED1zTU0Kmh9B1kM/M+bj3HR+FMIaJZqUlZPs0mSLiqta81jADPeW2+xa2Bo87zrn9fhosoMeZJVyky5lhGkwSi0E7OJIY8SEq5IApWBKKP6NIlAGrHbTYzeTxIOx2/MhlC2XGuCyyOM8paN0y0COzfUyLT7FrJVnQ8ixlVz2xLAc+TMcyXlLiko7+yHWR54SQpkKQE8WsnT41axqxwtMwRYgZrYUxWSWa3bcsIONISYWPeyiCnzogYNnNjtNKlCd9h1+vrszxKjxlNMp4l7URNjNkQwU8qONY5GGb4MYM+GYPoK2FWKxgxRiiWtTNgtlgDNYj5Gr2vNgMMjrN56mYRLU5KV0qakWFbGbZ/YZNHA55yik5uWbCWRmLLUjm5TN3bA2FhGa2zJWthRJ91QAl1BtRWQQBfSNK2sYDxXyhNlOPp9ZzSHNm+EWHf3EMBn+ZJY+DeRh37Fi/YWnbF49hcfjrOTDdClWwnrhpjUkCsHJ5RRrAUmgS2pCQzq+FYV8WHYOFEi+dFQsZtnXWuuvcjVvWzbOlEzmjj6CHEj2jIJJQWW4zP+xddAzvMsJziPaCE08uXHfTUR2SpdbJmsPCr5RrmvjEtq2K+vqbKVAGlTNUdTDN4BxxnHPY39tmqedIkWsMxhTrSTVejyUPEkyWSbCtT7alD59iMFy25nxoyT7EPvU6RGJKEV06X5jUJCpvWM2NMmVrElVcBh4YqwZHtAg2R1Le6GsoJd/XXpxR0Nfuky6co08RAXJ7WJ9gRaXD4zkVRYFjufIsq8jaO0FUnDbVB5VPHkw7q3gtrXTvQ3y3Niihm9WrGM+COTALHEBdFZ0kS0s5cywzUvQ5yy0NlGS9q4ziH8WdST/q4OTy2J4hPm1xpqWTWil5K8bdy6OCIS2+bhSNNRevolfJZKFHvMzoAx40YseG+oe8tO4xa6jvdHU2MuXcHJaSjWNVcZ+90dF5D1Wqpym0Z+xwMPV805hdy44JR5QX+q4cunsBeBoKaMyYGNMbJjRY1iiGCo1BZQoSOJJh+Vg4cNkR84lvcR7jxDzj0uk0Tqw5pcTRZy+PU3cmDU/QWdz1Px6NPIAU95oz0y9nXNr0aGrvySIYJ8CZUqKeKPNm0FvEHCtKZoxufHmwo8lollR7m3tYgXSbCUHeV9Yaqv5o2xLO7qHQtBUXD+zYqPU8etJQgTfH8N1HCUIFLHlwEpLSDJjsd5saZHnxZlXavBahGkbzT+m5l7Z5gz5p83Mu6W0DXaaRJ1JaSRW2WhJLEYg5ugpVt7HMhx2VPKjx56ma4mGgXsmqmZurn1dlqaoNtkSus1kSgmFlNhVOCavhV6aoldfUk0VQ6U5mkiTp8nOTZWiMGBKs4WpV19Ai61pKzO2FLobP8A/9oACAECEAAAAOILXrYwwyBmgUs7AMzSQyASCQwyzjrZdWpJhjgyGBmdmkBIIEDFgYwlnCXQyVCEwsSxMJLWNJDIBLDLIJBDOGuhkoqaQmMSxZyzOWMkIDSwsIRJJwmtauqghjJCWYs5axmMJkhdlhgaSTiG166s5MkgBhYx2IJaMSZCDJIZJiNtlVVDyLJJIZDJGSSMYCZJDJDJJZbXTQwDANJCDJIJGMkkkhkYSEEXWLnzuoIjRWMhAIMaGGSSQySGQS55moKxlMQkh4JIQ7QSFpICJIDJa4ozxXBAkgsYFYRLgCYZIJIJJDLLBTlIIIAZS0Yo0DMSYZJBIJJJCbpTkaKQsgjGMQbao7MQAxkhMhU1mXnPldYFGa6SBLLydeeu1stEWNJJGhkm1pc2bM00buVXV0wGOfHptp0WY7xRzYWEjSGAk2b2tbPmbZ0+TqwVaKXRRnubTXr5ObqJzY8hIkEDObzqtbNnfZn6mBNFCxOXsBp6mHXhuvrxabmIjyiqo6LXy1brLM+V33u+DLoes8vrA4te3Hztwrz6XZ4CtS0HTZZbweq1lGXZqzpoz9CmvLr4/XqbDr214XFeZ7CxjAIsd2Xn77XTNorzV67tF9FT8vo3ZqNGKzXWkqSGQwM0hkbHdrZKNS5aZtuDyjFt15adPObatT51aSGQwwyYqekdK4UNeevU9IK57iZqwLe+rWjQmCEx1hXlDa++jBU6LWqKIIAoCrG7nUsdUaJZTcEsSPmqy3b81OqVgRjFgQQoIh0dO+YjoxNZi7K0X8+08/TydWumnYtIBDLAISsUS1+s/M1tzIvN7fTWm7NnsxaeXq1U5F0Wqj0hmrsEIsqR2HbswynlZ9l9naSt1w11aedfvowpoWu+3KNN9NLqdd+IUNO4/JXgXJb283drQzJM1/Ov6OfHRpley3maW0UZrhN/Row48OnvvzuVzpp2dROlUp5mfo49HM09LPhptup6engdC2V5LUbs89+XTwep7B+Xm5nVpTrVdShLOXALOfs314clt9Pbs4G+RKstXX38qim3kv7J6loJ0KuhadFaV4XxaNyYseh6/Sczn2ANo5dfpGp53Obi9b1r48lnI6F2I+jmfRxM9fJbf0Oln5PGkl6Kpkclu9dzRlXV6R82BcTb6NvXFF/ns9+cWae1h5SBYAIZIC3Yx4XrXT6J+Nky7tPN6F3Wma7zme5q9ydvDzEhSQiCEiWvRlyp2PRjlDz3YSjD0PULU3JyZ9s6FfQw4amCsIZIJI1ZHI7c9GfP14ND387f6NK24cUjt6cuLFWwgVTAWJBSwc2rv91+JxWwjTp1+kFb8rlaI3oTkx4EcSqUV61LPCuPaycbs+ofk87E+OzenrAs4WZdevpzLk56NFR7MpdS5leXoReRf7hvO5zkLWH1gQ+dv6fD7t8y5uapCvW/Co3dJnFIstgDelt5vNTVi28zd6JTTyOmF1A5M3LBOvnBfN7fQNS4pZgWc93ZxeSd9eg6uohXgdCayDnw8wXCusWbNHNqiANCzOX6mGnW6V57vSkrh5vVtAavmcx2rVDJKqalZ7WYs9jtv5WjrZ6dPN9MzZ+DZs2GypebzZFVZK82VULWW2W2Sx3fvZ83ZZCLyyVo9VjUpg5alRWK82WlI1jXXNa7WX2d3n1954yqWBMx3ipMHIkQUVYquQNPKu29R7Xsta3oU9/JOq0WSQwii4JTg4rNSlFGTh4RozN1fWc+x2Y9B3vIeBIRISO7aq58PCsaqvNQnkq2z2H03oc2eyyG64wiRYAJCT7MiZudwrzUMmS/xQYPq9dfdzI5dnYk2GSKpVmPr4Jn5fA2dLjjHbz/ADKCW6PSdDJxmayyy612OO6YEt61sYn1whz8nyXP1Za8vNyaez0GB71HG7HWX0OowIa6QsFRtssJYQ5vN+RqqqSFbez0teqVU4On6XH1WUwGEiQ1paZIDMfg8yoJIWcXaRUzvrewvexcad8SnLbjJg9BGnK8opIWSCCSQwEwyGHZsrqhe/iQGe/LTi0nRZWiqADGEkkkkaRMACmXdfPL9aa2ZeFlfVbWqBZGMBIMkkgx1qBA2vraMWrJOo8HnabNVla1gNDAYbLAorBrooADRt2ndowLT2HCebS7S6JWCTIIDTHt0X1onKRZJNW5B0NSS9zm88l2l0rSFisEOZSpAMNQSGHR07rMGroQuMnBW7S6VpC5SCTG8DKCJSBJG0dTfcMelNBGDhm3VZWiQsVAi5S0imBsyyEvf0adGjYoug5XHe7TbWtYLQARc0MBkD45JGuv1i/dh3WWheLzbbNN1aIAWgBqoIIkEbIDIbtOu5t6pXuFXEwXWXuFUQNIGpzmSAiNlWGS7de1nQaCyUcHNbYUgMhMLGZlKmCBs6gyWdF13vqMsXLwqrWIiGQyFmszUkSSI+aCQ7tkmzm5HPqq8nEqucrAJDISXposQQQGpI+rL0rhoOLn5affri4qW2X7QqoVS1FByVMhgEu3ZdNzc1+sTjy86in3g53JW2zoWtVWGrquRBM1bIDFl+rL0JrzcT1BNHP5+DJ9FXmck3XdERahZMtyBRmRqzIs0Nm7FN1/l/Xx6MdGWn1acvmtbpvISmMi3LFShTWwgGo4ussu523pNMmTJT6urk8+1talUUGtrJFWsRCCp0PzeotdlvM7Di815uzn5GWxy6pUi2KzuEFZIIeuW2crpPnNma815XunqqOPUr03UINZRhDAKGYAkTZVzuulVcvxXLQpb2GTkyqpCg1anovNZZs9QiQETtYcXfpSqwcu+u3Ox9Pi59AxWVydG6ylpGda9N65efW8nYx4u9KktGLPJWW9Fmo5tVDJLdF5FdjQWHWGfnrbVm6WXn9pkqCVVFTSfSnFzMdkFVmjRValjrLK71usEcgc3n9orXUMxatknpNPG52J2idGBXpcszpHuFtsW2vl4e5QJUrVpSS3qpxObnaRthrNZNWilmD6EushtnNw9vNUwpdckht9hm5HHY1u7MzLopoDLGLszWRmHO6Geu0VKVga71GLh4rFDC1WesqGSI1sssCPY8zMiSSFWhnpc3ngYIsjStWqIjEC1A5gNhW0A2pGFjf/2gAIAQMQAAAAshLQmAxQAGICK0IghhkUASGSS1pLIBDDJAFhCKTIsLAACGENBI7GOYZBIJJFWGoMIGMUCBpJIZA7gsWgMEMkiwIFEIkkAkBkIkktMJZxJJBJIEIlcAMKgwEAySSS4EM7ARZDJBFkkggkEkBgAhEhtgjOc6wSAwGSESFViwwASCEiQ7BIznOoIkkMhDAVgCAwAyBZBIW6DVxy2VCCYISYKSkUmArIAYkghJ6ZRoWyqGAaQwGJUpMWSQgAQCQwt0ipV2yKZCI6BygrEUQwAgQrIIYX6DApZMyGSQgNAHzxRDAJBIDAJCX6UEjDOhBhKxosaus1wx2IhEZRJITsilpM9ZknfAMlnKxBFBA6+oQySFQYJMJEJOZBl0t3MCyDVViWUMVnV2ySQiSCSCnKAxOapYk7NFTS7ZnyrRUoL9PcFMBEJBiDHdQCTmrVsxzdaFu/lAu86iVXzp7KEAgkua2U1LbowKSc9eWx8/fxVWHt8Sm3rcSlLVnV00BQQY7XjOo5HpuakeYEW/BrexbB3fO2N1+MK2rnT1xAIIQ7BIuLqZEjTGux+Zp0860t2+Pn1dLma6qsc6Gi0QwEKqgmV2jNGfKuqysasdct6fJov6PN3U1Yjv1tJJICBADofGmc7nlugV2Usx05wLcWwV4+cbzII0EEKq3Xbn1ZX6G8sSTIRCAYTF81ldjIBCYRAEbp05HsykRiIYrLCkLEU1EiNWClhvposbsJdRmssypC1narIj8MKoYhTmsJAWsO7stdVvSssrzPtavJSzdauoW2cZVrLlZKCwFSmwXl1Ss9N7JjbdbXNHMq61OanRr4wrSCs3ymCU006N+XUbBWs323DDbrtCX4snY56pZ0OMgCV1U6NFZOVlNtwJcY01bdGmrDbruFGrBl7PKqezo8ZZXfkK4d4YjPozPpUuyc+aelqsqyPqvfNp5lXV51F7bg3KyX38+zn764ShDmR7KKo3ZtleVr9gqv4mvo0qSWHK5+jr+Z6HN6dEvzjM66Uteynkzf7tOZRis63UcPS1rCGpDRws78zrY9XMOitas+qMJbVzatnafSvNv6EpMKkgsok5o2ZHJxNqXi3WpoYi2rBk29d7reZp2LnkkMMAJVKDXm1tnlycnoJgrt61jDnZtPVulmTRoXNDGgIjRCiNTzulM4fGjW1c9+1Yy4sz9jXjrs06K88LQySQLAgfh9K3MFpSonBPQtZTzbG7N/ON12ujPGcb7OcsKCDBsMz25ZZqbNk4pX0FllXE1z0KYmtu2585ZrdHQwYxEWVU3sKLsq2vo4+PDpnbd6PPdfd1MNFll+/JnazUtvTOLlqsRXaQJkNt85nETpatJYK7tRLLNG3JTdqonQ6VHHpVYSIoAroMTJgXZtuhFWmICz7NeVxdnOvNm0yOYtIUBevy8eNH587NlcIcxCrt0NOaqbMxLsbrJERUSuuvsUecklS7qnkW8hSHO3Xlps25Y911lrNXXWqKmevqpwi2ZY6gOtgLEOde7NnfdRZdZffZFVM1YqFdHRHE128ZGkhVgJcys2zfjz3dOizd2darsnN4ucVrWmXZdw9DcwwyCQiWFWs2dDFm09XNZ1PT2SrW3E8TsFRrurFVUlZjsIwIHKKtZu6OHNo62TVs9rJVVZ5/x2q+ow1Z0SBYC7OypBgAazo9DDRp6NGu328kGHyWbDqisEWJTWoBIMkExwG7odVKdWi2zV3ZJM/l8OjqqipVWqKunGuhmxLFA4ghs6fo+ilj3azVy8kWYrN+DnTkUVyCPpJketKlIEhb0PpXd2CsmHHlwrdd0MHB1YEBEMVWALRDAZJp9hoMaAqkledrFC5QgVFAOXEGsvXaIDw4lfU9UqAkkRwYRIAZDJJhw2PJWvZAg8atS9XsY8dDlokKmQGCESLLdG15DKeQpURVobr6qctDwmQAkFRCJCH6zEwlc/IVkyWaKa27F1eamSwSAspCkQEybNV0hMXJzEFVA2USzrX05aiSIwgjC3cUWiqWWdAyMVqw5RWtMtol/UvpyVhishBMPUkBkhNkaGCrl5xYiSus6t+jPmrViADGIs6qCSSF7JCStXHpEImePp6sz5kR2CyRpNHRVTAQ7WGERaeNAoApL7eklWWmGwLFLSatsgEMZ7JGETPyCqOozy3obqkz0MHEVWMm7UCsMjNaZDKsfM1Z6YZmNnT1VDNWSGigkDZqjKGEY3Myg1c/G9/OkOeXdPRWFshhEMSuTTZADFsNlkEC85IVwCUNf0rqwCSTDJKq5ovCxhHNjSFcNEXTvtoTy1tnUepWjAtIQESaLhA0hZ2CZ+nxazX09Nzt4k29NqllsJAhR5JZYFDyQ120VDrZcCnp2aHbxJv6RrEupuaLDC0EYqGIMFuM1bNnDWvf0LnbxJ09JELurMEW5STIYA0JWy7nMB3PMSnfvtsbxrbNig3SEyAwQwwGQwrddz4ydTm5FTp6rH8c23VVY7wixQwEkMIIMhFl+EkXauWRTZZp8y+60tpVmJRSIIYwAMhi334Q4fdz4+iVTy79Brbbw8NaSQQFraZDBJXqt57Mz3V1Ne8Hkbd1lmtwStSWVwhRoszsIZJj328q1mW7TQ9V5XzFmvRbrkjpSliwBWsmIvoMBw77uVLDXdtrhcL5t792m5S0FRRgoZWyiJoZGfNs0c5HctZYGVx5ka925Fa2LU9brWSjVvTU5QQ7NWBTNAuWMGXzSdHfsVC9cIDACCQ5iiQ1vvu51jLYYzwxfLt0upasMRXhgdSCaqmpSRJuv5tzGOrWiFPKX9TpiQgER63sEMVEVQoivsyWFI71kMtfndXY3VPCVZYwaQkxakBVTFskYB1R64J57V32SEkNFYlgZFEEUGQBWWKawUZF//2gAIAQEAAQIA0EPA8EFPGw7tve127dt73vsHb8A/3sf5aAHkedeNII+NLWvGtaXVDwB/Ota8a0j5C140np3je+2ydre+wcDve+wOyd78b8dg7xvyPAR8aQWloLWv415A1rwPIWvGvAC0j/J8aatIIgp6cAd9trsXb3va327B2973vYPna3vYQ8DwP8gh/YC14CC1rX8a8j/PQGiPBRDk8kh3bsD2BB7B3YODt7Dg8O3tbB7b2tg72DtbCB8j+R4P+OkB/OvOtIfxrWta8DwER4KKcpF2a/uH9+/YO7du3YP7B3bt2BD+2wtgggrYIcgVvbUP62AP8dLfjfgeNfwP8N+Qm+B40UUU5SKU9xJ7BJ3Dw/v37+z2B4f37h3cO7b7h/cOB7B3bfYOBBQQP9j+x/iB/wCMIfwEfBTlKpx27du4d27du3fv379u/fuHh4f3Dw8ODg4PDgQ7e2uDtgghwPne+wIIP+J8b3/W/wCgfG9+R4Hg+CnJ6mTiHA7B7B3ftsHtsEODu3YO7B/cODw/uHBweHhwcDsODgt7B7bW972HAg73vxtb343vfbtve973vtvfbfbt4A/lwcnicSDYeH9/Z7O4cHd+4k79w4HsHdthwcDsEODmuDg8ODu/cOD+4IIIcHdg4EHew7YdsO3vYO1vfne1tFb2tre97HhvgI+CnJ4kE4ennv7PZ7Pb7faJRKJRIJfZ7PZ7BL7RKJfb7RL7faJhL7BIJRKJPaJBMJhL7BIJBJ37iQSB/f2ewSd+/s9gk9ns7iT2ez2ez2ez2ez2ez2GT2+32+32+32hab/JT05SCYSKZOk9gm94m9vt9ncPD/Z3Dw7sCHdg7fbsH9xJ3Egk9ns9olEwm9wnE4m9/v8Af7/d7vcJvcJhN7vf7/ke/wB/v9/v+R7/AH+/5Hv+R8j5HyPkfI+R8j5HyPke/wB48NKCCKKenqRTqVTq9dPIPsP2H7EOQjkX2Ich+xDkI5EOQ/YvsX2Mck+yfZByX7L9mHJvs/2cco+0faPtP2kcqHK/tR5V9s+2Hln2wctHLft324ctHLRy37b9tHLftg5X9s+2fbDy08v+4fcPuH3A8v8AuB5j9x+4fcPuA5h9vPL/ALh9w+4fcPuH2/7f9vPLgtBaHkp6cpVOpFYXJUGhoAGtAa69evXr1116669Q3rrr1Deob1Deob19fT1+sMEfr9fr9fr9frEfr9YjEPp9Hp9Pq9Pq9Xq9Xq9Pp9Pp9Pp9HpMPp9Hp9HoEI8FD+CpE5SqYSKyuSBoDQNBAa6ga0h41oedeNABrW6A6hvQN116BnTr16BnXp06dOnTr10tIDQAaG9enXqR1A6lvXWtdevXr1HjqBry9OUymUitDkiaNAABBaAQ86DQANALWtAaA11DQPDQBrWuvTr1WtAdevXp16BvXrrXVa8AaA6669da66LeuuvXoE3x186eHCZTCRtociTRoNDdALS0AG6C1rXXrrXXr1DeoHUAAN6669Q3Wlot69evjWlrWtEdQ3XXXTroDXXrrQHXXXr11rroLSIC0ngiVTJ6tLkYYNNatIDrrWtddAdda1rrrXXWg0NDdaDQ0DQAQAaBrWvBAAGg3WgNAa116611661169da0ta1rxoeAANJ6KlUykFkchTQEB40ABrQWgNeNaA6gLWuvUDSDdAdddQ0N1rS1rXXqAEG6A111rxrQAH968a86TVrwPJT0VKJVIrK5EmLQ8AALSAAA8Aa11150ABoAINDQPGta/grr18Bo/oIDxrxpa/vX8a8M8la8uBUqkEisjkYYAh4DdABAa1paXVBa1oeANaWkFrQAGvGta1oIDSH8a1/OvA/yP9tA8g+XoqRSCVWVyNrPAQQCAA1rwAB40EBrWgPGgNAIAIIfzrXnWv51/G/6P+W9+WpqIWvLk5SKVSKwuRBvgIIDTQB51rr4AQGtIedeQgB50B41rwP7H/sAH8Hy4FSqUSKwuRJqKagggh4HkDzoedLWgNIIeAAB4H8lbWvAA/x3/gf8d+B4CHkeNIpyep1IplyNN8NCAQ8aCAACHkedeQNIeR4B2h40PJIQR/y343/W/wCN+Nlb8t8OATUf4enqdTKdcjTfAQQ/oLYWwt72CFtbW/4BBCZHhciD/IQQUFP9d+uGM/V/q/1X6r9V+qOK/U/qv1P6n9UcV+p/U/qf1X6r9V+q/U/qv1X6r9T+p/Vfqf1f6oBFBA+SpA5TqdTnkJagmoIIIed9jIJxP8j3ix7/AHif3+/3iYTCQIHYOwYzVyPje9oeAr+cPO288ZzkczHNmczbyQcgdyF3KTzL7r92+7feDzr7z95+9fejzn7sOb/dvu33Y83+8/evvf3z74OdDyAPBW1InGdTmZ3IS1BNQQPgIoulmfY+SLQs/J+T8htkWflC0Lfzm2q8zXA732D2PzS4xkN7BDq1jaab1f4oqGt8J9COgB19Jrfrxjv1wxzscKXw/gGh8E0jS+GaJx5x5oimKfwhVNY1x5AHgjw8PU6mMzuQOaQmoFAhbTzO6suJR+oRCD0+r0+j4/xvjfF5lXiMZad7JL2zZ9vGMjxuwVtV42WQml1L0RUhQdQloxUH4z9aKJovxjKP674gpfr/ANcaJqim+pJRdTdUkriA0zUbSNP4gx367wSh4cj4cpFOplMeQJhCCae1zlNLlcM5LzYNFvEkCD2BW9oLRXNHNMTgd7blZJGzcqgqji1hmVa6jYzuW/Hh2DWZ0rxMhLCBGW9GNdE2Exel0bI44/X65YRGYez1qRRtcgA31+lsRigmTf4cNJ6erCmMjuQJqBs35eWQZ98Hq4s97w+yscuJOarogmThG/v0dHjg9c1JdG9rzJ25hP8ALMlkTx4GzXtcmzPAW8xt/j6JbxrCKzWM9bG9XsMYlL2tLewDfAj0V09Zh6OErCxgYtevp0EfGuV07gP8Hw9SKyp053IUC12Yj10xNRvGM5ZbPRsST453EXMN+85rZZJ2GZQ2vfi53O5m+SWKUS+z280bxy73u3eVinZkx2TtVIamM4rTQWCY1Uh37lNEjXuAao2sc0BvZFb7PcHFxLk4eyNwaBGpGhrVej4BnneNIlFPUqsGye2fTSFyK+wQ4alSyye2ljZMAYoMxwPOsdyY4+7bpS5aDIyNlhGYpZ77VybIy12RIvM2Xjwtl6p0spPWnszYiNzaHHLzthcfa1tI+uOB9cxSVn1fhsqRwmNjDE2IQGB1YRSQCH0vje4va2KD1xxQQ+l8UlfCTYOXHXP5KepVYV1OfnnMM0ix1Aw3cph8nkKDn18zk3vNabjeb5QWZKvLlFTdx3JS2p5YuOjjDuOjjTuOHjknHr2HdLlqVO3h5p60FnjzmXuKYm5lvDVhnaooRtT2timHreoxENesscyOJtd1Z0b3M8Ss9Ho9cDDB0jZHH6H1+J4LM1uDXx/JUilU6vmQ5xzHFMwFZsYyuLx+NrPtVrr/AHCIt/Fb81aus47keQ0HZPEPvvDqYzHKKvMshzYc3g5fV5rydW315rlWhO6pK7KChHZrAghBYp267GsgYI2R9GxOZGGAxuh9Z8Qox9ZI2ouCeZnMLIn1QzrE0hqurDP/ABzk/Gz4cnqRTrImc5pzXNe52QyYlZm5bOOyLbcwiWCNLg+DwfJX3X4C3j5rL8TYyAYKRbJbq86OLu8QmwdTk4yIikvxUbgsYmvnbHDo5bSampqoSOkiayCEtIcWNb1EYYGJomBEQJZGWFycXRTNHghkbmtY9pGYlxWWbNSd4CKKenqdZU2DmiFE+vkLyiletuYydrZVh1gJmzcrdYNSTjFzm1QvoXyqJfPZy2Nx0kTco6hyYZVsToHzx7wac9zrsgTU1MFeL0VpA+GUvjmkJvMs/JN5lx1yGzNP74rTr0VuSb5BuNsSWJgyxHdNuG8L/wCwdf8AmTTsGfl4bbQCKJenqwMwbb8oshZgWMiyVchjJcUK08dEyCeHh3IoeQcomdLSmwdvk0FS9g7RVJWZq7qeU5NjWr8e3uSDMKIwuzkYfWuQP4w9iagGppx7QIbcWUgyrsnFknXG3X3vlskbNJJ8h8omc5pFiW0ZXTNlleXGSKx8mtYafYJAom8Igztf8X5BDwFt6kU6zYvOvvkIGPjr1YuD43BVIrRe3jDOX4yRU7TlJdaKsVVYq3JHSkY+mMgIbDZ8RkeTce4RFyVZsxGjVfwyv+Mx+Lh+J8N+P7PHWpgAChyvVzQgZHRziUy/J+bHlDlzmBmhmnZtuaObdlPnm865843DcEwm+U28MkzNNzX7ypT4bFYg/G1nsitp6lUqzTb8l+WeCrV74NQtbF05bhXxcEw/5EbjoZ+NKBokhdC7jd/MRQz4+Wsc5xTI1IpKdzCScWqcmOeUTuLvga1jG11VVdV00AK3KWOPdxc1iaeri5Mc94dtr3PDiAnF5IDQ0lNRXRxCYXOylTiChjxMrW/w9Sp6ywyDsi4h7+3HFXEbHsga3iNsfkdYhR47Fcf5Qdw2a8lCTkFMVsa2msjyBvNpse+tWfx7LcnOfUa4kISwsdEqhgdXDUArdb9BJx+TEfrjQFBtA1H1hXfTdSNcVfiGo6D1OjQrit6unqDQxtcQ+stbH15QuFyezksOLteCgnmRPWVGUN+Rr+xdxx9R0ZIgaHXnfkg4x/HE9/MnSCUVrUEmRm9mMVVZ7E2aLBw/J2I8Te5Qc6Y3cTkrPa4KI1i18KCHjLQ/onY5r48r+9ZyR3Jzy481bzZ3M/uw5mOZu5qebN5qebHm32/7x91HNBzP7meZN5m3m33n70ebfcxynlS4dZhl/IC4RPqGbxIpE9ZZuUN5zD23h5qVmOVru4ku2fyPLRPGTMhQOIOGGFZhrGPs4meOF2XjqYexx2XAX3YKbkzsyozxF8UjZWSRyVZJJYHN82YhH0khbC2HoWGN0HxfiupNoGkaPwGUZKJx5qip8YQen0NhFYVHUv1wxrsUMZyhUZIc7ye5+Lrar5PCWtyKRPWZWVN1wd3MjZ6mdh5RHyscpHJ/3nKslUdxoOjghMfqERiljuKy5vJjyj7QOT/Z3cofyXP5vMuY/juRjzreQM5FHnaWby+WhfH4CoxGSNGp8JtMYv8AQfWBw53Dm8PdxA8T+rnjP1xvFDxJnD/pn0s8R+pniw4oOIjiJ4g3iB4h9Rfxd3HgwP75GP8AEVlUxx1ODxKnrmha+Kb3tsvse4z99611a9zhF6zF0ETWesxa7dQEHlwJLT7vk+32d+zpCmkucMV4wgksNtC0yE03Y04Ucc+qN4ieHHijONx8cdhDiThjgPrT+NuwIwroJLXrFWPG/om8XPHfrgwn6w3/ANm7L1bn4wlaah48nB4e2RctgbbZkDlf24ywy/7b9z+4/a/s/wBj89t0WvmOti0LbrXyvk/Ldc+X8oWzZ+T7GkAMEQgFMY4Yr9R+lOD/AEH1utgQuP41/GW8YbxlvFzxk8YPGBxp3Ghxn64OOHjP1n639bdxv6v9WdxR3GXcck479f8A0P12Pj314YBmFbhX4gYr5pvG3xOxwuZorDjqenJ6mWRGYxdqY3fnfN+cL4vC780Xfm/ObfF/9j+xGTGT/Zfsf2Hz/m/LbbF4Xxkhk25VuXbmG5hmbZnGZyPOszsWbZm2ZpmUymTXDHUn9679rRQIcWuW5D3aF1c1gc+eV1izK2fCTmxBLvfbsHF3ni0mLkcoFxxPDg5TK0rw5A30iIRiNsYjETYhD6vV6vX6/UIvV6/WI/WImwCD0ej4/pEAg9Ag9Ag9AgFb4oqtqVKzSVw4UT7Kbo2vlfl32a9zq5OLnSR3cbShlsxy3nMke67I+ad7DhHGalJWU96NrQRI33/LbbwNzIMjdXXHFIXJ6mVlZJZ5BAAABABNAO3SPu/P/YfPGQ/Yfsf2P7A5FmQjtMd169daAA11DWsADQxrGMYG+OIGo72Y18c8sMOLtNFAIWZlIz5JD0ySu26yvO52QkmkmLX4J7pcU+LEWUyxPZbIXnjh45aqY2TPRYOaJcbUiL3OnU4y7s3I0hNQQTUEFtynfHF+o/UjEjE/qf1H6l2KOIfjC2qteAEAEPATUA0Na1rAE3xxEVj3xDpI/YnSMe5vx5HqSmchYlx+Xgudq+LlZk5J3zuaePoyYN1iZpcBBvua5gz7aa5BHxB7FxtSJ6KnUjbdfkGAa4OYUEEAPDlZWMaAGdCwM9ZGgMsnqktddAdddQNBBMADGsAQIQPEREmrBmaWFzy5RudJ8qVsmV/ZVbLMpI+hOZK7jJlHWX2S08fRfgHSQthGKjMkAkIYzkgqLOHgjguOKUOTlOt0W5ypJ+Or3Exx1yBaQgtvVlYljGOm99i9DY9zbrZ6MmWa9UUBrqtsDsiBoIJiampqCathcPTU04JSRsIc6QG5JVbNdNJ2XLKONp08HWyMzq7YMo60+0Wnjq7ccMwDrd6rcmnADQM+KSzJ/HjguOqVPDxYRTZLxifnhaTPxryPhViKN7Vt6srEMYJGyOzKw+SdlcfkKE1EZlsraBb5CIlv021eVuQQTEwtTUCPPD12YsAgpYgxtZqmpVldtCfISY26yCnXswVYI3TrKq2biaeOIO4yp8c5WsVCH03wtRGbdROTP40JHHVKnp4sByLcgIDyQ5U11yheixXeQXmycOGKREW29OLSPZxe5RWYU6oOaQtBayWDr1J8VPdaCffjJo0EPB8cQT1GsCp7Aexk9qadmVgnAxOTNiaStb7S3sgWTSvyjryulq4ygeMJosnu0Nc6KlN1zBpK+fxg6RccTxInq0JFrJCI8kWTbUXJ0VkHWLFpj3WDhg0ZO1VtsWXp8aOWio2Kiy6tCgWILey5rnVLteOODKUGvvjPcvzuHht0h54cpjGsALTGC1PUyDrdyhVsZKvRwFfCYWsyWATuw2NuPkGUdfN9A8YQXFl37Fsgkihk4tIBlDTN8/iwzLjieHhytqVMbbTFyc5M028nQWVXEbObaXTHDhq5XNXyLsvyapxx/KBNJXWYVxUU078FF2ZuPcbNG43I2+TXslk8f+NMrXeWeOICdRrj6636GQbFisHbmjq5S5mb1+vkb2BOLrRSXbj213y5M5BZBBcZTDxY5WevJ8yeR80EuIrg5I1jmovxYrK46pE4MVkSqMWEHcnWTdTl5MWnKN/Hlzm0HsccKGLMYp2K9+Nu8fr8yVQ1TmBcVFNO97nndyS/kWgMdV3x/H0bVS5i62IrzjS4kp1GsAXpxv5LIYTC0rEUF6DE3sTXtWeQ4S11EJc6SdZM5FZJBcZUZ4mJ2zWK+SrWYZ2DjzFkHY6DmrfxUrQ48pQqytCZVxlBMOVLJGBcnQOUfwexzKJkgOHTFyASXpnVbns5y+vJXWZdeVJzHBxd365mx1FSTA5JYyx+mu0vxle5RhsRDez2tcTU6iXH01sjpWuvMbTnEBs5G7JPFHXiuUFBOTMskckskVxpRnjShuchoRmCDqJeLSuN9/C6/Mnfi1t1cdEyjVFWROqruSGy7lasms/kycckqFrJiURnDGM8quycrr8xv47B2uauqGFZl2QNF8b+7nmSUzV7U4yFCebjmCzeYyOJt1MNyaTF2Q64FxVWFGuPp1mKf5t6jayrZsTFkKrop8tFWqYeuz5E8TLdhZMZSTIuA42cfPx1WpZVQrmOzaoWuMNldfPBocsfxk2+uPCyYBjVaU6qu5IJWctTFTl5It3gViX5J8DsKYXc0UroGcTvNbzWvXiifmzkDSqR1XQTSMvXrk2RbM/IUDUZmZK3EsNi+J5ee3nstxkvfbq8UNlRLAprfdNE95bexeLwD60GOoYl8zLEVyxLAazJzeh/IOKls6wjuB08PDPioZ54fiVqDIKDZzedjxYZ+N25BceV1QrEm2rCgWeRPLxAcOeQu75BFcFtcno1Vg3RuzONn4HFwutxa9hb9Ti/H6js6/IvxlSGMNyCyj7lz2mnk6uNlEp45xjKYSTiqr53F3eR4uvHSh4mbKiUDX40Yg4Z2EOBbgH4H9G3CDj7uPHAHjruPs499eOOI/JHJqaChfhuRYDJS4h+NhxbeOnj36j0zvsR8snnX48Zkjx43VEsGrisqJ+XeHcyNZ2EfyNwfdlK4ZY5dDVXHyxwpiqK7qvxfjOrevNyZF1OaJxkyEmSkuGgmGwqdipkMldxc0N/g9nHDIcZ4pQN2TJcWbaUSxQmfE+zE2O5BVo5GyLOL45frVpoJYuRSV7GLwly2zpzXG3qqx0c3G+JQzWpcFWxcORx0Zx45m/l+Ji5VcuR8FblVx9XhEsErisptmxPNZ5o9tjH3ORye2acrD28sxjMfkm87+9/e/vp5797+9nncvN7vK77sfmIuQScgvZuzcBgYxza+SDpK7JJZOI5DlVFVHRQEPbxdW1EsOGF4vUYE6k9liiyGi3M5aXDcfkyF6KduSjZNGBaGZZrAMgZihm4fW5lS4zLXcb+oGFixU+Ez0XEIsqsCr6iOFVtZFzD7mZS/Wbhq1m084l+L+o/UbFIcV+uN423j36E4L9B9f8A0IwH15/H3cXHF28d+tv4s7jL+M57DUm1GzxUa/wcg0ciyuMx+fymQ/HOFx8zxxlWVEsGnufJHZhiiklf+ztw35p6bHGJ0NmtVdC+UKwM4uvH2wtoNsRY3J4bIiWPD1Le9aEfI3YSLLnAqSIUo6dtZYUJ2LUbenqaz1iFsfT1dA1revXbj1IDOq0zwU5zi90zczha01uvRp4K7ynLRNzturLAsdnWZV54yrSiWC8ZGtWrRtkqugtZXASXlYowtfJLmIZ5XRInczc6Wrj6gOOLOSTWMti8VYigpZgRer1YuvmCGZo4Pw4zq0p2zY3OUvkNsCwJBJ37B/bYPje/AXXQQPbYf3Dw8S5fkvFRlcTxloe8ZKODlT7GdscNwsFp0zlxlWlEMIolckr2bs1fO5PJUcMc5XjvP90UoaK7lAA32XZM25pwJhnw0DjyN2Mz+Nx9GvkaYb168ZjxrJTnxg0A5Tq0XmwM+AAwNA00AAdQ0BaXXqGgdeulrxoAK5UfwjjtfIyY/KYuxPNm+S5PFmtQrvM03YnjCtqNYJWLjk1+QtX8Plq+CzT1aum9kLH7aN4ssEtphmkvS5ohYEibAzfG5JguLZr0YJmbyGiNcVZwOILkYwZT1YVpPNsZ5rAAGtboANa0ADQAaG9daA140BoN0EEB175XEU6XFcfl62J4/KbXKKp8bJ4yLbWDCuv08dDVx+fqZ6fCYLF42vQdR5Xd/dS4uWn8ajyi9eryTuvHNIHCFruMqyp5uNYm23K8kc9rXDXHW/iWFq5KsI5PU6sp6tjNqMBAAANAaAgOutAa1rxpABaHnTRrmGQ4/mII4IC2U4LJO4jBHWmARPGFaEaxDO9a1G7LZPPRx5utjnzV3nFYVuS5BYymarcXz9EVG2BcWZ8YRBYVV8lNQws8Oer8cfmAHN6zSfi2k1cmWGJUisTzukNxZlRgAAABjdIANCA0G9NaWlofwEAFrefxGBw92kyqFG2lVjx+Jgb5K4wrSjWGbEctmWVMZfzUn7CrYc3HmWtNHcxGU4+eX8ex5lpSTm2s14wqasa6Slh4M7xirx/G5LKvIXXmA4VA0ZDjVfAOqTY/1vUitLNKNMQAQA8BBoAXUNA0RrSA0PAGggGhaYNxxuAWooWPklaUE4cZVpMWILIbzLdpl+bkTctjII6+avYbkvIs6KkPKeeVoFWxmKZKrQzRAxCCwk0GRxtyzFkLtatJM4aji5vLg6o8HxMpE9SG0M0Y0xNQDQEEEAEEP5IWtha0PI8gNGjNE0gCsx9qryiEHFhOXGVZTBhVchzkcFjITzcjsZOw3A5PkF7HYaXDVr+T4m5+F41JRxSlFoZpAYoAYuJl+82W66duDdlSCeLQ46EuHhyKmUqkTzaWaUYagm+AAh4amrSA0R41rwAABpBBAANWOxOTYgHM5NjOP4p03Hczyas5caVlMWLfnMbW4/xnjlDFXcla4pDgOMtfSyNDJ5GxXvZPF4KQR5jHOkbYGZ8YzxcsULEGR+Xg87lOT0pNrEL8VVWtHhyKmUilTzaWaUaaGpoQCCCCCfJPFHj6kjkfOkBoIIeAAAgHZedCNqAC1GNUJ5cUDxsWExuKZj7+Z4hxfEzxYulUyH0u7ZgoXJeucflsazJ4TL81yeGe9WBmW6x41lRl+O4jBYbAc2v8XtZDj+Hqgcql4BQHly3KnKRPNhZtRhqACCHgIAILkDo5OOX8pV0QVrxrQA8AADwDlsbinkIeWx4zJsqWprtnjgspixaErJczHxzNY3j2EsMOZggp8lx1vjTbgs42vXqTWsMXiZZhBUARh6/5JyPBsXBDawkn49w/Ma2WwMGUjo1PBTvEycpU9TrNqNNTfAQ8ANAUk3IL3HL+SGV5XRz0ZILeuh4CACAQQAUcu2N0B4eyjjsRJHhbcXHhMGDGCvifW7PUqORylqvkvybwXM4/l9y7LQbyKs+pjY8fxRlEPErcugKA1Det5Xi4xWYr5ANmxUmKxdjglWOMeXgqdOU6cZzm1GmpvkIBviazLJVxfIXstwQnGUZrEhYtaQQDQB4yWQz8LqbYwANa0GqpK++RgBOGtxrZlbr27GHx9mtlcXPwXMfjelxKOfKz4mrxyjfwmS4jxfh1IEPblkBSHS5VyzZcHxvjcFYp81aSWbiGLQ8uRUyerKeZlmRGmpnhqCaAJ8hBThjajPVx09SpDYwnHpL2OfH11pNA/jkOMmaUGhvXrrqteHLAiZobRM0NCQ8RYpFPi2Q8mo2uStgx1Z2U4Dl83TOTwluqHNkZk2gVFrFzxVspx6jjHxtUtKTAcR4xG0AeXIqZPFpOUqy4amIIJhCmszz16CC5LaxNeCpbgqPpPt0v1uMc5vXQHgKzFNH1guRVw3Q8686cMEJA0U45oMqxkuHtM5Obwnt2susrlWcZsV8RlM7zHFXoYKfiQZIdazXCOFtyPLV7ATnqPi0EIQHlycpU9tolTLKhpagWq1YOWxrq8ATQBzN+LFCDJxxqnNHkeL4/P/jorWteA10UbPjBgXXrpaDeutacsJLIWiqpMyc4/OyZP6dHUjp8joZ6TiNS1yTK8Z/GVTI0WQ8XzFROEjcgutYFuHj5VVw9ytO2KxVgrsQ8D+HJykT1aJVhZBMQTGukt3KqqY9BMQHNWYkY+S9BguG4/wDF1DDXr3JuYP8AGkGNjDAwRhuuoaBrroDQbrRZjuf8eyjYoRk8VVwbuOUcpyKrxvl+eVXNZ25xxxrT5HiuLgrtLW1Q9rm3R1iHXDpxirNbM5qZWAb4CCPh6cpA9Wk9WVdUYYJsiyOlUpVnIIJiauXVsM/BU8H+Puk9nL/kPI5Pu5dRE2IRhgYGButLX+IFaTj/ACLEciDnxz3MxxmvTF+fHyXbsWaaLmKfmGYltK5ourJwe26OsYIxClJl92OvpzAWoLQHhy3IpFZTlaFh3tktVoYmxLHMeAgmpq9H4w/GtGjkeUZP8i3siXlACIQthEQjDenTr1111rwf6aK81MFl69bv5PE5K7dw+Dx+LmkdkYOQxQVrKsVMjkKvI4s7YZTTg8WgAxEY1bcmur0pGgjwEECUU5FSKZTpwsqVtyCviw4KBYcOQQTU0NdjeT284x5k2GthbC2ERiP19NdepbrWi3rrX9AV3QNnNpQOuVYbte7bvYzIi1kaXLJbJw8EEWMwtiO0w5aqC14sDq0arV7SjpJ7o3umTfA8lPRMimUoe2yLjYvDQ1V1gAUEE1BNQQIc0MiZCyIRiMM69epHTr169Ohata69QNIIJjrrclLaZhXl2Qxj48VmKRxsb3ctYytxzGsjjkAFf9fWRD1KNNRT5LVmOp6zO176xTSEEPBTvEilUrZBZV9QoJqaIFgU4AhN8BNLWsjZEyJsbYw3r1DPX6zH06FmiC0gt8uGtebkuZdnHZlnDx+us5PI/lriOfo8rx+LdRt8Yk4jQxdvEYrFytdGyGCIp6lWnLVJro9yMFaKDvpqCHkk+JBK2VsotK6oS1NLVAsAHIeGkJrWMYxjGMY1rQ1rGxtj69S3q5uupBBRRRHnfgILlLMgGvy7+EPc3JumfAapxMTmkOj66DXMLCz1gyFy6yLfT1+sMDOvXbEEPJTkU9TCRsqtK4q5CYmKBYN0q2ExrGsbG1rWBqYWhjGtDevkpyPlyPgoo+SiR4A/Iqa3iCvTcMIflzKq7aLKiksutuum6bxvm8b7sh+xOSjvDxlJv2DbwvNu/MFsWvklNQQ/hycXqVSCZWlaVfw1NVdYUzoJoaGpqa72tsMnjkjewtIkB7bJLi5x2S4klFFHy7wEC1fkabHz8MGQZxdTHKveyBuPjppyKPgkogtLTGYHVol7JGiIN0FvtvsmoIeNFOREimUgnFtWjX8NQUCwimDU1MIPcOwuYjLHtka8PDqWYF39i7JOyjcoy/3Li7aKKKPkne2kO5wuPWeJvvVuOvnfko3Mqx0YYnPuuyTsq7LHLnMnNuzpzhzZzhzZzgzozv779+M8M+M+M9+9/fJngeSiiJFIJBO26LirLbE1V1hlMmiNMW3O4quDOjTU1Bbc/FP9j7L7TruNl5e/FZTtvZJJW3EneyS8Tus8qtcek41khNxOfvyIzXa2WxmQgHp9Irmt8L4XwfgHHnG/qzi/1P6n9b8AU/i/FFb43xzXTUEPJTvEgeJBOLyuGuQWJigWKUxTCEX2p+Cu4pxpqEjZfkNn9tfixxH6eTFDH1K3NXU7FS6H9+2y4ucXFFxXHojA6r+vOPihZYblTyAZ8Zz9/wDvzyIci+x/ZPsn2P7GeRnkX2L7H9jPIhyH7B9gHIPsAz/7/wDffv8A99++TUP4cHLT09SKdXlbNchNLFXONUyCagnHJy8GawxTGQShRMZQdWfUbAYDCX81DXUbME4f2Lt72SXEuNS/NzBnNPup5m3mX3M8xHMBzA8xbzE8vHLvtv2z7Z9rHKxyr7X9r+1favtP2n7V9p+0/aftP2n7R9o+0/Z/syatDxpyPhykEisK8rRhTS1zTXNBTIJpaZFkn8PnD4bDLElv5WKnRkipX4ez33bXMHAxOpWGSdtl3YuJ7EuLmlj6ph6dOnr9YYGBoaGdOnTrrr0DevToG9OvTr06dOnTr1Cagh5ciinKUyKwrysGMtc1zHV3UFMQWlpmfkH8WfHcF8Xv2Bvi78s2/lm38yW7681QZhZ4KksEjX9iSd72XFx8bLfT6/X0DOvXr1AHkfxvfkIEnYPbf8BNQQQ8FO8OT1IrSvGy6Nwe1zX15MepXhzHB077j+MOY/tvbnCcyOb7veXYHK5rGO41Up4SnneOy45sgf2Ly/sT2J3vfbt279u3fv37+z2+73+/3e4Te0SiUSB4f37d+/f2d/Z7PYmoIIeHI+HJ4lVlXzbka9rxI2aC3jny5NuVgsl1iSw/iztjw4+10zUHvd2cyoZHSgrjQ5bbxmWlaH9y8vMns79y8v7l/s9ns9nt9vuMxnM5sfJ+T8o2/lfKFltltgTCb3e73Cf3+/3+/wB/v+QA3wE3wU7w5PEqtLKG7YYJk0MEcmKsTYf40UTr95s8nFaIoDHfq/1Zxv6sYh2LOMdi/wBO2q90qKwEmdFVthwk9rpfYXdzKZnS+3v7C/v7O5fsnsFi6FjB/Wfq44vJxwcb+t/XHcePGsvamiDxJ3Du20PGgxNQTfJRCcpFILKzUt18ktWzWNfHMwgiw0lXKYy3ZrNw1zhNKgIRCK4rGp8P4bqnxH0m0LjHSlz1hzM2jiPi/C+CaAxoxYw/6H639YHFBxFvD28Nbwr6T9I+kjhX0gcHdwTk2Hr8lqfmNv5jH5gd+W5eVfYvsP2KPleSzWH4sOCng/0ZvCPpZ4WOFDho4gOJHiSCameSiSnKRSq2c1abjZMJLw6LjkOHZjhxODjVXARcZo4SOERMjEYYyq3Gtw82NjrnFSY+aoMLzOvFlGXXWcPk4pWBroasdaOlHi6fKq+Xjvx2o5mOYI4RRbUbUbRGP/X/AK9uPkqWsZc/FM/4R/4T/wAJP4GH4G/4N/wYfghv4Kj/AAfjsAI/X6vUIvQIfT6PR8cEIJv8ElFSp6z2QZW+P6hCIWRsY2JsYY2MQNiDGMZFV5JU5lUzbY5qc3AHcW19rHNsfyzLcYtfiz/lFDgMeK/WwYn4rYvVy3HcfVOCOvHXjgjibHbp/wDMsNimBq1101OYWaLWLp06dOhaWuGtBBa1rp1661ppQ8lFOIUqzmTZB6vSImsEbWCNrAxoa3QAAa9ZDi0kNTN1MnW5nV5dFaEbY7uVHK3cuucgfyaNdQs+XsDQ3IwSS1+fM/JbPyePyoPyy38sn8tf9bb+Xh+YR+ZD+ZP+yn8yu/M4/NfH+Zk+IZfOiHyGwb1W2ggAOv8AGk1D+CnFyac1lIwC5di4vZKJGuCADWtCCAateo0slgpuEWKkWfq2f2k+Ka2xywcqNmrxLGY/sH5qHEZRkL6wq2+IP/FrPxYPxc38Yj8Zt/Gf/Mx+Of8Anf8Azz/nX/O/+dn8ffQGcFo4MSdi91mpk/D5LFye3Zy13O8StFzXgg/2FsFbJc5ynsvqfB+N8X4hq/F+MKwrCBtZtX44gFcVhVFUVRWFd1OTFXONH8XQ8IyXHIOCwYvoIunr9LY3wXvxwfxofxmz8Y/8zH4wP4wP4uH4t/5Y38Vj8Vt/E/8AyX/kv/Ih+If+QH8P/wDIR+H/APkH/If+Sj8Vf8nw3G35d2dfkbuanzvubJxVHJfsxmP3gzw5B9gPIvsn2VNRTUfDiUT+TLbY/jejp6g0sIDfV6vR8b1dCNODSZPb7fkGdtr3ulbO6f5Ht7ldWhdWt1ojr1dGGekw9BEYfQYRD6+nrdD1xuJq/jWDi37mxzB3L5eVPz09w2rMgNGP8jsZWFIUjU+P8cR9AgB53tEon8lSV3BddLtsP7ddkdXLTo3NLg0sI6+sR9l19bgGhxIXXeup8AlBdAmu6611KetNTvGnOxvFr3OpeRy5JhMrHdxIHlzHxLFQ8yljhbGYfj+n1+oQOj9KJb/D05OPO3fvhy1nNBzB3MPu/wB2HNBzY8yHNPuf3P7j9wPLTylvLXcnPKPtLuU/aByg8n+znko5F9k+yDko5R9obyf7V9rbykcqHLRy77eOY/cPucnLzzH7l9xPMfuP3M80PNPubuZfdcDVz+bkkiTWhbK1CQSg2rBhGt5m3mbebfeBzc82+5nmP2/7f9xTk1Anw9ONl+fOWbK6rXeC1oCAWtaDQNa1pa111oDrrrrS0taA11660G66ka0tBFvlo/H3FM1lpZWNjDSS9rF0TGxoNqRZq42MMDA0NayR78rHluzLi0gfDi5ZaXJLKUhj44SiNBN/1H960P40G6R8a0teNLXgEhsdTA8X4ll8jasFAiRj5VqFAOCYIxjIvyhMGtAZ10Tas+NrbUEEUCU48ilvidpUocCEEEAAQPGh415C0ta141/Guuta1rXXWtBqK1oBrKONghuNyNuR7w0mRrWRhRlpbG4Ruascz8wWpZH5allWs6ZudV6DsfJjo8egh4egiZFyeW8pw5SNeCiggh/WvAQQGtLQ/gIABDxrWuobrr169eunLWgCsHXrs49TyN2acOeHAeGNAiikTI2RU2sbjmfkK5mQtxy43I8gbTgE1lNQCamBOKImPJ5LasJyen+D/A8BBa150B/IK15CCAAA6gdC3WtaI6ub16lj246LjWEzV6zK58bWtKc2NaYCmxqRYwxswR+RcqTQeI5MioHTRxPrMc8JqatFbVo8ifZVhOUgf4Pgfxpa/sLX868BNDRg+K0Pw1B+JpPxDP8AhV/4Sk/DD/xDJ+J8hwYksLepLa9Krj6krr921JImpiDnhoY1zZDEFfWLbCzN3Yw0vitVfGBs2qpcH1pLUyaNkuWyrj80+yrIcpE5FPQQHkILX9geda0ih4auEcW/cvzLMpHmoM7HnHZiLPVc3Wy9ivkfxXJ+D3fhbCYODKUrXJMlftzWXh7SSogE1jV1kDHFtxYMV2fk62xwTXTw2sao35aVTzySyu8uQWnrIOybrCsp6lBBDyPIQ8aQ/wANIfwf4c/j1SS697ZmzMnE3tZdr2m3X5tmdl5Vezvy481Y5EMhPLM6XxprIhGC7caanhizk8FWq38sXGoLfYPsY6WP2MkefZ4J2fLzkHW3zK0nCbwVKB5CCH+AGkVsfyPPCMDO9z+pjYwrr0jELxKnP+U4yuE3JHVp5ZHly017S4xNKYwNa1rWusNlfi6/Pb8bPa7IRzBMGQpkfy5BaIKkOSe906spylKcpk3yEP4P+OvG/wCKVO8+xG9EFmumuvrenHQJeHl7m8lkrySSSN7xtbB6+kccacngN32xYa7DStkt2fDH1b3VZSn/AA5FNR8OMzstIDOrAkT0E9TlvgIIIfztb/nX9cGimNpgUcbw90TBE93cPCdJ3cWgvki5Wyg0D2lElrgSXNZKAPY2O1LhYYhyK3YP81bUWWa/IQ+MVi3eGI+Hmw7NyBTqwpU/w9ToeAggh/kEP8eCwyuyilUUTinysZv3OkL3v9jxJGVZXKjRTZSBE6NzXRRNIYinhy1kVhFWb+S7TTNRtU/4Dq1i5P8AHqw28q7wxbcXGy7PvCnM6lT/ABIp0FseB4H+Wx/GvPDW2HZNwEIlRTjG98ZLy93V4LZE0Su5VHUDHOa1oDmxlgAZHE1gc3eQmx1ek38o3G+Cn4s4h+JIQTXseZTIEAwFPUitO5A9TKdSKREvUvkEHa0PAW968jxv+WrjUUgyykcXNTmubDP2EYaGlbYhIGk8sdVaB0jZEGN6wnYUSicV2yYnOLZzG4P4aSblCWL+SmhqcnmU3XZ94UpsJ6kTjIpEPA/gfwCP4H+PbGhX3BSqF7XSquvZpzer2uPsDpVIeZqvKxRJ6jcyJ4gZHCxAtTix1Ryp2ozsHYM95+YrZSSOxiugZ4AABKkMquuzDypVYTlIHp6lQ8bHjY8DwP8AQFSJzGx24Zm945JJ3soyTiMxtD5nu8bao1zA1XNYGOTV2etsj6Mc5jVJLhY2u5TaJ7C0HNM0i3RvgWmnxQotBDQ5PUxuPyDnKU2C9PT1KrIHgIeNeN+NIf5aignMLbJnErIDYLjWfMHDoHSMEhDGOIXMljXMeH9GtCY3szwwPDhfOIUT/wAkWiS5lcNgmsw+aORiytirUx2YsBaTzKpXXX2XOUynL09PEqsuCHjY/geN+B/Glr+MGnvrG0ZXuha1ycoWljk2YCc9oQXSs3zRUXQOaYwQ4scWMXV0bYyL8mNhgH5CtlxTHiNwmZJTPjqmm5YhgWk8ymZ197yVIpVInlSCyB42gtoLa2D/ADoDXjawz5XU3WI5R6ntIrurGwnKV07ZHh3QtsuYebKimANcnua579h7XPexBZtthUo85f2iobLoBbdkXO3tMVmxSyg8OTlIbLsm7ZUhlT1ItSKPGtwf6T9H+iGCGBGCGA/Q/oBgBx/9CMCMB+g/QDAfoP0A4/8AoHcf+vQYGxLRfOHv7PcAVVVg9Yg1WGtkETG2AG8zVJQPic0hvaNOcE0dmkxwLvPOzCjDHC/pHYS5Vs1D/g3w4yKRWzmXFEvMqkT05TmmwM6iMMEYZ6xF6REIvX6/X6/X6xGGdPWW9evruS4a9bQka2d24G02Wk6N47TsieoxKo4uZmq1gayMJx9jUXxujTE1Y1oXIrJidGY+nrzaoyZaL/J5lNs5t5RT1IpU8ONdsZA0BoBo0G9Qzp166ADQ3rotLeutdQqDboDnvkmaqqgFsvJd2mMCeWm6+E8zDAC1z3OcGsQb0amOZHdNJPntWi5xKHjLGJxVjE2Mbr+AneHqZ1k5t5LjIpFInqYxshTlsIoeGoIeG/wEPAW0fOvGOVlPMqDwoWxCwPV3ldLZqR2DA7cDObvgbE4IQhtcMYmBrGSBZB8smQvFFOJILTLIx1dkdtsrqxxb+NHjDOLpyKcZjM7MOKcpFKnp6ZG5Rhy2mrsmlp8BA+QttftHxsILeMVlpDlIBJXEJnbHE0+x09V9gxunTWc5ZXVUsPrY+JbIDHB8nsktWbDi5FEk9pJIQ1QqORleKtanbYsW/kpyJerBnOUKKeZU9PEUblGXnsDtA7Cb4BB350tb2POliRYTmzp74msUCsnpI4P7QvmMABjk5uI21FE4hgYxzmns2W9mH8mpl4eXIp6Pi9eYogBXNcNfHWdebCKm3FylNk2TecU8yGUuTGODkxzpOwcJOzXhwIcHg9uwPbfbsH9u299i5oxLbSnUrg9kcDKotMfJM56kVcWHh4mqjnAikqIPLo3+/wBxtOuOkysGPlxMl+NznFxcXGw9jWIIJkclhjZYRBG97U5OUzrLrptOKlL1KSo4p3unnvDNfu/3pzwzwz4zzc+M99g+wfYRyE8gHIPsB5IOT/YxyMck+xnkQ5EeRt5JxDKWpJRKS4CNU2zAueZnlVVaY+V4YOdr5Lc/BnbGVHIvsH2GTkP2P7D9jrux8vJrP705z9y/K/tH34y1d2sYhEyz8Ft2sPnlFOUptHImZylLxMIo1be9ZB7QgPDVtn8tQTEF2jC3/G2u4ELMkqkLXiSE49SqRxcHF1RSpxsNhHNSDO3HMy0bSAfDm7PjHy2YEfG/DHRktcwvbFCxk3plnq+NuUhsLJukc4vT04eucvL3PegnFvkoracYmBwMI21dmvTQtlbJ4C2y6QykOY+uIkU5dmh8VUyKY2BvmyKtLFtzbCg7ald7A9zsdNiZ83T2gSgWoqCeExyOc6rXVYPqQHZL1Ip1lnOTyVIYY2q7I9ZKTXUgMDnBAeCiEPDVJ4A0XeAStBcAFhSvmc1zDXFdz2Tp7mhV/EglEbOaJysjGjOiQxpvhzSxFUZMXLzaqf5CagGNCrZL9hWs1JazWw+JDMZTmHkSuWnNnZZlersv8dAgmoIAoh72zNTRKPDE5oLgj54ALJne8tbGolXdI2QSDqHsVdSsmEbedBysrGDNNkaUwOaBKwt1E6hNmoSt+CtsdGfDQYq8UbY5oJSipFOZjl3OTlIqsLW3JZFZlaEfA8BFBvVqAKkayMeJRohqCHkg+OCK0pFI0JghNd0rOpWiWKmx4lVZczaxWRiRlQ8PUbtBOaWlnSlLRfbrlAlBOEaKjTwGNDa9aZjGxuJUhsGycq6QlObp7Lskhybw1rURoBoCIcgNdSzr16yjTvDW9EEQtcIFxOXqc50cSrNmUycNSOY2uxzJnxt5oFbWIWRTk5vWNOaE4OaRUfi5+WVi0BaIaY3AxPcWKN7SA2VxJeZzbOSdK1yrROFqZwkL360QB16tYxpDh1IACALer00a0GMWgEUFwdWFogvDIWRGZ/Xrp7oxXjmVlV1zFj1dGIVoASN03x1e0KN7ljpOQQFrh4antbJG4uid1DfYyQNKcnmc3XXyU5V2NWRLlk5Gta0pwa0ADTRrqWluuoaW9XBg0WpjdaDdAcLE7wHNLmtgbELClaTrULawmfZMQ5j4unDvnDUWgAAJzTG6KVmOmqMMboTGY/V6nw6ZOyVk7bLZBJ8gpxkUxvvtucq8U6sSTFyvyOHUtLdAAENbpjdODY+oHUt69Q1w00aIaiGLhZcGRlNTVEWKdFvffWNRGRERHmga+4sWpBrt3TVoteCnMrDEy5iv19Ah9Ya6t8WSi6mS2y22y/8AKciZFKb7pk9U4oHXpJFZkjZoqR8ZWg3oW9Ws6liLGt6yIAh4A0FrWgAOKmds4sqB9E1p4nSOkZIXu3A2spAVWHLh0yDcSmt9YY9mmjTGgBvS0ylPmGdA0sLGxwx/G+OarqTsecUMM3COJUplOQc9RR3GzqxM9ZaQMDHtlqww9GtaxrXMI6lr0WgNGp1rq9pDWdWAAiNAcedddabK+tJUVZNIeyJwlXaJsCcHugHLXBZFYdRJg6yNcGphYSyRgbajqzaDehbtiYmx9XMLXRiJsLWPJUpmOQLljoI1blcnAvatPOtBBrhGwrQlBcnM00NEzEEU4eG+WojANui20yxuKamiw5wjc09YQxSunZE7l7t31hzXTHElEAa32aGp7XNxM08WntBaIxVdJH169epPV5cZFYdkXMbZE7chKVlJWjREsnXr1Acmhej0iWGYKzDFXpshj6TtuJsMTGJ8Eo9r2GPjwmEssjpUHRve5we6UzPc+gcc6FzhAOf3JbVo4pVQyaCw6/FYbaktSObNBZ72rGRixkluH4bGGrMLtewHZB6fY9z3SWzfenmV1s5N2PhBmmenq/J1LSYowAA1jXl7hG2SxPK6aSGaF0LaTrLpYin1o4Yk0PrWqj5p1HX4y9yc+d0hqugcxNExkTlK6EwGMtAfz0ST2RiBRXdkkUlR8D4jO6eaJ0BiaytjXyPeFFFFjxTJFk0oxJVfBZXZ5kMiuOuByIyRkViaFjWvUqAamDq1vrfYOQ/ZMs1paskc0t61JcumzUkpyx2quTiyvSaWaV8TrVd8l2py+PMC02aGOG/Eq6mdMWPeVKrTrDXLnckFgHDjFixNLahv1Zq9mCeJ8Vju62606SVY+epLDm5pJcjLas2PhQtL2VHPqzTSPUhebjo4ZxJI9z1l5EAfHR7evSVSC4w27b3q/BJFPDcRZFFjK9SvUr160lS3DaqTVDBE2pFXF6SnWMXQQPTcrQyAcA8hoUrpxaFgVlzSXUTcOcY6wySAQzRWIZ2QtjgEcUcL5K96hj57VdjakVWo2vSp0oDC/HPxs9F2ElquLzIbDfS0XXvLwZGtPiIENYWtUbbMjm79dqF9R8T6/pp14DHI9XI7dXJY6y3tVa2WiynFCLKqqFMk3Kx0FDMR5Fskoc6FNDHEOOPdzRs9N1fEOxzntrOgUgdNM+0pHum7NaJ57tGUCGGO9HXy5nmtuuvivRyOkqiCg4vLlWr5MXW2pXrJzRsY1ylMLdRN11gErgyIwCB0jGKOWkys/WRiyDZqd51tPY8QKAVXwKV8j68ENWBgMhmUqwWTsUpqLY5bDs3hczGoH45vNGz15KuLbjTO6uenx4nMhqRU4nNZCarqLcfBiqdeSKQsibJA3HQY2kYoY2V6tkyuMiArwMbkZXpyyMjQFI1rGhrY2BpIFqOWraUckVWqqEQikfNNbF1ZC7YbcVmvHDUdjWVpqlbEyxNw1RkVOCKnEx0dh9gyss3Z7rjJLKJW4/kcPIZeT5XImOWPFKg/JxXDYZNJkYZHzRuZFWp1IIMdCV8kUMvLmMkbl6OxAA6CSB9ay/cbXmQ04cgb4zcz1PLGGDewg5ha3qWTNY0CV2XVx1nLWJp5W2pLFoOfDLPLHeis46TEvisVbePfWljdVfSdXdEIyJTPNbns2nRrtCyCWN9Y0mRRY9VbEc2IVRXp6V+GTcBdZv3ci0STuuyzXII6cjLEb6eVxj8Zfp5KrY+RiosZMyetehsvKpRNFyeyHLMShrW2BAx4sWqeTY7rCywoa8tD4NmHI2bk8ldjKjcS+KGjcqqiyqsfRq0YacGOZjG1cdFjoomwsax7GOEojfHYE1qOQzBVJq8zBC+rLRMDK82LFdWZqDYhjIKceJryWIL0TvldbCsvvTXZpbOSimmyBsGwLUGRr3hLLkJ7+Re6rDadbfnX2TIpHsbpzYI5FYgoY/ruJZGX9r+0x81O6zIY/J1ZMS6llMZPQnoRYtsdyvkqORr5GIULLLPem2hebdxbGwRSw33MjQjmuQvDw6F8cjWySSyTPsqwbljHuYM2Ldi7ZmfLcszsEBgnju0Y3qnFjq9KKlWw5pO9ePpUTUbBjK0eOyFS/WuuVCJpe+6+c5Ww1QNcNJzWQxNmDm25rVi4y9L6X1JqcsDKfpD7UQqmi6COrG6Fs12OzWqxtZC6u6tWgoqo39VWbJAa9aGEwOgUQjHYNkbYjnisyPFhtENfmprUsisRSvyMlx9iHM3MlPfvy28hduZCNMmc4T5Ka2+/FbfO/L0JmXYIHwNnfrKPtGd2Vl9bGuUqKa1rGtDY1kI2VZat+lPjCJsfkaeQxmRpZBl/HXBex1ihYgsVsrFaoZKnk6NmMQspQ0cY+nQr4+OtXxsVaKCrFVqMDa9WIQOreqQTSSskleZDjnMN2lbgoQluLjfj5U52Ojhx0FeLFx46SuaEmInlrvfPHNaq7NeWaGwGRY/GwuMivT3TZlrpjAipRXjYA2ZwbGjN+pxZo4Y0ROLViWWzdnlsXnZI5STK17Iy1PIY3Jw5Y5PHvoTY+THU6NTB1cfi4aVWjUrU4aVKlTqsc0RJrHV5WWo56slaatUxkVLFOBnZiqWHxeHZiasEdStFVr4rG0sfDWrNMNmmcRiX4ujVrTUxVr2qlBdKOMiqWMeoRZlmV12dmjawPJLY1XDfDlJFWqz16yxMmMyGPWNFKHDBtqpHVo1KEwtS2r16zYNqxlrGbOTrZF99CzUs1nY+OhYrMrSXbtR0U8D65iseqeW3JcM8U9lppwROpvYclYgxVWrXhsK9FcfmMZbht08ni34i3Vt0p5Msbit2so7LRWbHu9z7Qr4h8SsGyMlNYN82JGsAM3QxdWtcmtka+JzoosjBXsyVMPFRgo4bFuxVLG18Tj2VX0nsttyEL6+RjyFbLsvVsqZKUUeLNGHDHF2saaBxDa8kUdGnj4LVWxjb8F7H/rfgsxkdc0WPwskZy8E1XJY56zUWVqZOa0WYrA4Wpizja1HEYrHYbAYyjJWpQYnHsxlJr2VbWMODlwT8bAnzFWBnrFarFXdEyB8TKzIfW9nrjYFHfZYyTrzrck01hPbiqcE2ItUKtatFi69GvWfRowS1Wx5VZWTMoNp0atfGTY01242SBUpMSq0cNGvQykOWizlb48UFZtWnTpR4tuGdjJ6lzCXMbcwxpWsVRrZSDD46ljMHIaWNs9Rkqd6+sxkshZyMs+Xt2ZMaIZMTHSoVa/HLDsm8qws8Y64iczoyv1bEI3QOi9bIqsePoR0b1DKVsjFfqHC1MTHUZWqLDig2tQq0YcdXp3IYaeYx+YpZapk8d8GjiaeGbj6uBpYpvH6GJFcYWXBXsXkq1+o91aOvXxtt7JamQpX8W7F0qXxamNpV8ZiMPRx1moq9Ky2zhc3xrI8dyHHoMVcqx4Yg4enisTVxRw1ixXySfa+TkcC50j3KyYRFH6y0gM6FrmMb684fkfLrV6+HkxU7bpszZQtkmxeTotsx4/DwY6th5KlnHzVbN3IZGpadkqWToW2UW4RuPix8eOqV6nS8223IU8vWu0HUaWNxtdqja5ZGGxTYyhHhsdh8VHUGOdibBOFnpZ7E28bi56VOGvx+LAcR4vxvEY/GyuqYpzaGVgzmI+He4+3j2OwlixbcE5Z97GdCiGJiZ4emtLeRvgv5iO7PSZXZrCWMy7OT3bE8GQu3rlp+PmiuU3YYUKdZ7607sqr9TM38keOWIThWWcZbNSHLvgVuDIV7LcpXqwQ0adWA2o8jBbjko4Otxmk2nDUzmMy1HNNmXxOS4LMcYwXHsK3H5HAZbGtsy3aeXxmbbyGm7AWG1sbWlbkIc/Qy/HJqVf8A/9oACAECEQECAFkXdMs3zbC2s92TMnfDDr88YxjGMMGUKZGs5znKznNs3dM6Zvrh2YdEzassumTWNOts7bbZZ9ts5tnKZ2+WGbLN4wnbXCZNY0SZ85vnZZ2ztlM7Wzn3qzYWc5vnOUyFOiReM5zlbZznOc5F985Wc58b5222zlvOEKdEnvjzjFs522Y99+Tl5eZpufm5ubm5+fn5+bm5ubm5+dkyGxJ7NfOLZWMecprZTf4WsNnRJ0Kys3dvpjFs5vjFs5znOcobYJP4wsp3chfbNs5+Wb4x8WTJ0Sfw982ZOmu/rCzm2PnlrDYk/vKx8x/yNYbEnRXd7vbKazP62Z/8TWZMnRIvWcrKZZtm0o2G2MJy3Z/GMYxjXDXaxOTeMY06fU6nT6UlLA6a0rOxENpH5eZ5d+Tm5uXl5eXk5OXlaUXZMhsSe2HpyAxZBZr7VSp06hFUxaSM6zOn+OPOE1hsSe1I/I8onKfAT5ZiXNUzQnyhLUiBkp5+VTomWuNdGBw1dr411lVOSFOiT2ppZ53RrVjkRNGyhi6PS6hRKBVQTjFCp1oEemrDrrqQOJC7MzCI6SRxWGxIkyYQDSWDJIbA5jSJhC0iFSRyKoja06ZCe/LvyPIJvI57k4vsJ78uyZZdOoFUFDMVXAZCQcKdGqVjtudo5b5mdkx8vNy8vNy8jybOmTGx7mbqIrOnUbmZ2jmpiOWSzpjhQC4J1KmZR3MNNddNcYxqyxhYdlqypXa2XQjrONqNVAwycjmLwPCTPoynZM8TlaR3W2222+++2+++2++0f6AVMXiolD9T+pJ+j23qqb9Cb9Nv0P6Hf74Vn9H+j/RGvl/Uer7Udd/Qp5XtrhaOGmmuuNdNdONqE6MUSwSnjH8z+X/L/mv+d0Oj0un0+n1Op1uv1ng4eLjYIIghai6RUXS6T0jUxUnV6fUGm6nV6vWaOWME9jsBOe22dtdNOPR2wmbCw9hBRW3VGxTkfGNQD7M4p3cQRColGjRJ05RomWVEtvBX2s9mZlmO0tVyFPLI9TvTT7uhQ2FEwODwIANGymUckkucZiUbuTCICjvgUYOzeIVgoAlmNU88jRjSxGwoUzi4HMwKmQp0TO0lyUloWp06gUamEvEU/XeF43vDaSWSrkrQnjUDm8FQ6FCmRKRxbNHY09pECJGjRhGFMmQCp0dxGOktrUFCswplOBRU9HHOuRwaI0CG07NIyZUiBEjtIgRqRSKsWtMoQNAqlEisKZHKdp5CrKGqhsVScgzjJKVNHrIZqMgdk48XYZRrU1JY2BSo1Mq0Yyp1BJI/LPIIzyhLTABVKpWnUoVipVDZw4npeBqfUlhydAw2IGgVO+8ilT2jaUTU7ShQlGye8IzxBFTRSoo3pgmqamjl6sNhjkn4dGQVQBOy1BGxKdG3O1RSKRSRm1QfN2ew9R/QCs7XZ7PZ7Q1j1zVveoa4TrKiCnJRJlChUjuNadOutOdLKEdgaRFUPVxy6EFExWlUjMLhx8fHxcXFxcXFxcXCMQrjcYxUQM0KZSyVbxzx0xyOopJgdZBzJ6PgORGqMStMiTLKz8443m2JCqJMobRDUw058ZmIC0xkheNEUtUajgtQIoXMyO7+c3ymsBHYnhqkyiTKSEhqBpDpp6qOJQzEgQIrTqODJKlFEiRuPh3zss5ym8EgRPKfJIESZ6mN0SeQFvHHHKSZAxNpOUYEtWZGiTobvZ1UPSyeG8HIDImP9WnqI1iAkERqOJQyiSZAxqRAhtAKdEnToblYBkjCn5MWZPaQwO0gS/n0ccVo44lPLHF1jDDhYWJcvCY8lNEnRKROhuywZEZTudHP4klMRDObMok6JTTDUTCC4hlipyTIVKpKmMZnipbOiUqdDYBmK1cmKCmg/FmTNnJsz5zm8U5p5JmjhGeKWYYogp7CxjN+dxHH4NT2ZCEhSFY46T8uStkmW++22cpllMjKKqrTllhjegOGGaWSm/RsyJTG0uWTpmRqoTsCIyR+ikeVz32yxM9mTJlUqNEBqmkVUJowOIU1qi05gaw4olMxIU6dH4cjkcnLLOzsWWfLWZM9ao1CNRKEgxlGUDQ8V3ZoipwhQtYlKjQ2dHbLmRlJycmUz7C7O5C+WdVyFUqrWpgG+LD5wyezsSlUjjbJE5EU0v6UbkowapaaikIRTOyZM6YqsRalVW1Os7bbZznOc7bC2ESJSI3C5J3d61qn9Hn7ENfz835hyxoXzZm3eUJ+73O53e933ru/3+93+/3+/wB8FlExqRGgT2NOnKvZ3TvqmGiW0wMhezOJZys5WMYx4whYfBtKjUadlIJiq8NdWj1YaZ4pYqaUXQrNmdrZ8YwtddddWFha7IlMpXgU8p/pz1o/r/oy1n6jstdcRqJQHUVRVnaaqapaoGVpGfXXSpQx8JLYKmJacfHxcLXZG0yqp2m/qSfoF+p/Sml0pqSL8gfxP47/AI8P5fQkhOCgoW/MjpIvzG/O6b0vX4uPjOk6vW63WKmCJhYNNdW8G/6FSacXF4+Hh4Xp6dR10czTDUFOU5rj/NTNLEFR2Obk32zss5s7OmHF2WcKqOV3i4uDr8HBwddoOEqeJdnn3E+QJ/6H9H+j/SH9P+r/AFf6/wDW/qx1onzvVFWlVc7fr/1/6/8AX/r4azqvT0b0TUPR6PR6PS6XT6fT6fT6nU6nU6nU6nU6fT6fT6fThpuZzd8plUxdDo9LpdLLWdVq3kkp3d85znObY8sywzeHLlz5iY7xR9brJrOqt7QJ/ri2c5uTrbyyp21KGSnjd5yqU1nU7taFPd7t6zkY+vwPC8btnEjH7FqRiOKZGhF47mpE1ok9n+eefn7PcCs5ikGsqKnPumYkzx1LjrGF5XJMmUSdOn+QqQ/8DoENK9KYU01ms6nckKZRJ06f5Z+T+zTkEqdHTi8hsydVLuhtCnTp/kXykRegEVImQ1MdQtdLOqp0KZQp7Yf4n8j9xKnTomgieHaOR7kqp01ok9n8N5ZpX+Je2VKmW8ZM5gEcdzVTZkyiJ5N3PObZzeT5F7J6dbbghG2LSPUJkKa7vfKzmzJxMfi/okA2xHOz3dSPNYU31ZMpviSf1FEnTI1M+7VX9K0rnYb4+OWcVL8iuMcVNXhCadQCakRIvEzlZrRA4cemLZ3W++/JK/wBVEVNYbfpB+W+mmpoyIjcrzE7pkzQMns6dZxbDrGJvjGv0C/ORCK1qI/zZLm0sMsMicnTqd7Cma7p3yKkIXWXT2l+MS/QX5xEsgeZ0NmRokTuiJEp3yLMolvtttnOzkD5y7onP4wKuVA7ERi7PXx0M+UTGJIkQspHqHTX23cnLZi3Io32y7uTuXxiVcvz0DEttyVGfLzNUdjjKnKlUjzXBnONEbmRkbE75F2Jnctlt8AVWqJ2MndAUMk47iUhOYy9vuEpFM7MttnW2y4ODj4eLiYHBotA+MMFWqCPq8JR8TRVgg6JuNg4uIlI53lIXctsxQijW2q11K4RcTh6p1+iP5LEjLxAnK215E4ksofAiIbCSOwnuqlMNpI/NOX6K/KWdcsnUYSDKhIi2jLZ3xMLqR/ETCisS2jQy8mzo35zk3BSU/VCCSn4YlXl+YXIJ7OXNyHPGiW/IJkxOA1NiIQFpI0BCmIAvqjRGYrZagyO8ir1+bZzMlqiQo7arRk6nI3ewGZ4jQrYlsSNbFEhR+NtttnQsI1q/OQrVblHYlsSAlrG0rzKYvAOuQENgPkEhQFuM0k3NyvLyFLzcjSqrGjIpN90aztKntrGtmUhTk763CxESJEZSnILAYuEgnYi3yt4i2aSrjo1y7Lk5DPVONhZSOT1B3wyF0IgJkViPZbghRWFFYEC1XNzcooi2+JDK8jk/rfdacvKZyS8vKEolIRrZbiW++0RLfbcjvvbW/8A/9oACAEDEQECALNZlm+c664WE9nTvlMmvlP9MYwzLCxbXXFsrKxrq7NbBMmf5Os5vjHwe+crGMeddWs7fPCx9Gs3nFs3wmWPGVhZy7/LOc5s12+Wc5cs5xjXH3xj21mtnbdz33332333cts522znNsYxjGMJ1m2VnLp0yymsVsecrGPDMzJ32cnfO2c52znKb092s1jT+cfDLlttnOfWb5zlP7wNj+TeHLN8XzmzthP4x6ZYZDY/gzLKZZdnthZz8X9tZrNbI2P4Zzd0/jPlvq1ms1mTWL4Z9PZ/Lvm2fL+2s9nZrFZ/ONcYxrZ/bDppx8XFx8fHxcXFxcfHx6NZ0ydNY7P4gXZ7PZ7PZjnqmtjzTjpppx8fHx8fHpx6acemlnQ2axJ7HILpk62znNMqtYTokKwNqX5Z85Jk6azWNEmJxEhEKknZZdDBBFVRcHEjQIihZU1nfOXLbbbbObu+35qmB01msadMyqBiMkBC5LJy956/u8pKRCmG1MskWc5znLOzs7J07us05zs92sViIFIMIEBCnQKpRnIo1EiRolFemTs8enHppq46MDAyJnDRxpkKdYvUOKeGOBpIU78iFCqm4jEnXGUJDaBZ0eN4+Lj4+Pj01WddHCCCnc28TAABaWk4ypwFCsTolqo1EiTo07axLOc58ZWVhM+RUKnZ01mY1mNYxIwox42i46lTxtaNQomcTYkLQWxi2MeMY1016XWqE7Wp4C/N/mx/n9Lpy0AUT/ntQdHpHS/z/wCf/O6gfm9TqHQfzKmCO2c7b7b7bbbbbb7b9jmqLsqeXtdns9rsc/Nzc/Pz8/O87T9jn5uXk5KyVjefn7HZ7HY7XY7XZep5+x2uz2HEFNdkzkQu57MW2c522222333Y2Pk5ME9mu7sOULunWUyZNLUKSzMgGQbYTIi5OXl5LunTOm8Es5WXclkCJCnZ3sSZEqlbJrU6kEYiixapschSOUSd8u5Ozpll3szpiJ2cy1FhQo09mTWdVaFOmdQI7BaWNlVJnqEShKJP5GSSUZXTXcikdyOIYCTOKN3s7O+RVWhs1oUVo0NmVYpE5qBQ2dll3ToxgTeJAiWUKZaiiTrJE0jIXqU9htEjUaBAqdCqxTFanUSfxGClKctoCsxGhJGo7OQI0SJbhFuIzIrBaN5ECFRKmImq1NGIaQxgo4HhlbaiOrenKa0N2bGuog6xrYkSYcMPDUokKCwKRRuKjQFUtMHDw8PCQgiU7kVNMQ6GuMbuLvq8ekcwqRk6JMpSG2rx1NhcXpA4hg4Gh6ZU3Hppx8ZQDSvSvR1dFJTHEKOOnoqgLjGRESFM+E6JApnGaMuUZal2ToFC8svPz9jn7HY7PY7HY5+fsPUEZk9Rz80ZEVmUhHIMZoiF3QsSJYqBErRqoK0ajU3vHjFiIwGIAjJruwhKOgDM+BLliRM6NpQFRkoWqFvqLRqb5tbKIdGaaIBs6dEQlKok0sjEME8SNEpLSxBT4gGUnQpkKm8useX8OmT3ZPaculNCEfAzTADQo0SleGZjA2Q2dCmtNfFqaOoitjzHOmsMzJ7FGLxBLGMW24SxIkaNpQgFYlWUKa012sEUZujpnGz2dHJFKzJxjp0VheE3HkknQQPACJE8qIKcWAIZjsKC098DG504aYqoybxx664s7PeIXeqInFxnhdrEicWZCpJ7igTqZMgDVyxRJxlnlr74xi2LnTpkNRymmFRxRwsnRJkcbPnwKiYlKgi3lvTyz1o02qaPj00IdceIhkg2mhjhkhaMVGZpk6JNZ/ORUKzITmKlvnZaMGurssO2rg4J1SI2kW3LkY2hZGecu7P4wmYVE6msKnuwsDCwsHHo4Yw7OydOJNQKRTgFMVHqsIrumW2dmT2ZMorT2FTrVgYRBoxjcU6wQuna2CZfmI1UKmU5EmtlZ85w9mTKJM09gaYcM1PFAOuunR6P6EDE6JmRWJl+e8iqFTlM7trjGMYWuuuqezJmiQtOmQtPYBoFHScPA8Oc/sqKXL2dsMzhqQcHBwvDw8XB1+v1ut1ut1+vh7MmUbMqhMhU9hb81Zy61YCf9F9Ii8kxBosWyssW/Jvvts5J7MhUSFp0IsEqAXb8x/DqqCVjnGz+3Z7O3lnznO2WuyFRIGKCOk6Y0zUEFJSUG+/JvvMUoyjBRfz+i9F03pXpes8HDw8MdKUeox8XVKHj43DTVZTIVCqeHj6I0nT64reWoKvf9Hv/ANEv0u4JjNV1XdOc6163ttUc/K8rSBV9vt9vttWFK5ubls7snawqhgFbMbS8vLy8sjnTnCUUkQxDCMe1cyil4uLj0111wsYysMnf4U4RLk5OXl5eXl5eTdpDXW4dHDQouj0P5/8AP/m/zf5f8v8Al/y5KQh4+BqYYGg/l/y/5f8AL/mWd80SaXsPVdvt9vtdrtdrs9rs9ns9ns9ns9ns9rtdrtdrt9uap4tFjDqml7nc7vc7ie9MgOQjfKa2bZzZ0yzfLprPYYxg9SIru+2yKzKnZEpEyzt6dNfOU3jKjFa+pbZYjflaRE6FRJ07S/4XWc2xTsPwqHT2mQsnWUCjTp1JfCe2WWX8RBx8fFwlBw8PXih9uql7aphASuDDYlL6zZvMYf4Zn22YiuTtYENieS7fKJvi3wZH4zZ3QtE2ESkTWb5QN/gJHfXFtcIVCydEpE30gb4t7NTWw7+gUDJ06kTfDCyqZn+eMLKdVTrUxu9xUNiTox49HDTTTTj49NdIPD+W+NUtGY/TIWhs6ezesWdnZMQP7H29pLxKWldrgzKJkV2f4nZ1F8h8YUk14mAdCpf5zJkKCzrL2ZN7d3vF8huUhVMKlCzqNDZrCzIENndEmDVh0004+PTi4+LiFrt6piqG100pCrAsKFCmu1o2az2ZkL3dv8BKiasTPamOrB7xuJMXiJmTpk7gyxckLfclRqrZlh2Gx2NQOPllCyJ1i2POPvSKqTiLJ1TnURa6xkBMhsyFoWuDLCxrbH+ClVUidljEL1Qa6lFwtUDVjUplEzuzJhNM2NXT3xjFyH40yqmwmTplnGBTM4PB12QqOwqMb4WznbOVnLKb4kdMqp+Riyz5gKQbCTHvuyFCmTIB8O5Jlrd7ZFTrbPqRUj1rshZDaFTrXHkUJCwCs+CK42xhU6mKwl5lVGq1Y2GzJ5SQIrkya0domdZs/o1riwIgAESY+Qj32IaRVa0xYY9RjtrdlmBMhYjJwO+C9DZnWr2ymuCpVVW0YcXJN7haNlghEUTLFwWubD4xYRZZcqZVTOmtgfGqxZ3FRqIb4thYRLXGurBoAaaa6sGuCBQKZa66obi/grA0IsnfNifzpjxr4wtStrTyTLW2pe85FmVOGHbCxcn9a+CtprpjXQYtba3x52FgaNs/LVa+WT2xi2pNfGqIb7bX/9oACAEBAgM/Av8A/ACDLU3PghgepDmnivd6/ovd6/ovd6/ovd6/ovd/N9F7vX9F7vX9F7vWhzTxQ5p6kOaeKHNPFDmnihzTxQ5pQ5pQ5p6kOaeKHNPFDmnihzTxQ5p4oc08UOaeKHNPFe6eK9w8UOaeIQ5p6l7p4r3TxXuHivcPFe6eK9zr+i908V7p4hDmniEOaepDB3Um4O8b03B3D6puDuH1Tfe4fVM97gmZ8EzPgmZ8EzPgm58E33uCbg7h9U3B3D6puDvG9DB3V80MHdSHNd1Ic13UhzXdSHNPUhzT1Ic09SHNPUhzT1L3T1L3TxXuniF7p4r3TxQ5p4hDmnqQ5rupDmu6kMD6/k7/APxzk7//ABzk7+7/AMcm3Yf/ABybdh/8cm3Z/wCOTbs7/wDxybdn/jnJ3/8AjnJ393/jnJ393/jnJ393/jnJ3/7DGWMuKD25t1XbR8/VRRyRyRyRyRyRyRyRyRy4o5I5I5I5I5I4hHJHJHJHEI5I5I5I4hHJHJHEI5I4hHEI4hHEI5I5ev5O/u/2LyX2h/NLiDv9U2iAiYRiqPndqo+d2qj5460znBUfPCo+eE3FDFDHtTecEznjiqP7wKj+8aqP7wKj+8Co/vB1qi+8HWqP7wdfyVH94Ov5Kj+8HX8lR/eDrVH94FR/eBUf3gVH941Uf3jVR/eBUf3gVH94OtUX3g6/kqL7wdfyVFzx1/JUfPHX6/k7+71kUEEEMUMUMUMUMUMUMQhiOKbiOKBsPX6n0j9qr0bThqnd9PNrRwBhth9fMjV3oaMUPAQwHBDLgjzjxKPOPEr3j1rM9aCCGCGHUh4CHgIeAh4CGXDSMkMkMkMBwQy4IZIZcEMkP2Lk7+71kyvRjf54wHBDAcEMBwQwHBDAcEBUML1P1EKQqrXFzmdYWtSg3VeAEB5kIAXIEuA9mR26Y0dbB9XjoCCGgaRkhPchJBBBBDSEENAQ80aAgh6/k7/OcTq6oTva1uooOAIsPmTO5eibv9ZyNqn5ormjvhEZ6Zg+JKROUOMlFwPPYWnpM+ijSOo8Gg/PRWL3c30Y7XFeSYXC2xu3HctWk6Tew6f8O/8AiD/Yq0xP13J36WstPeULm9aY+LTqxBGShI3KS1D0u5QtltUbDHRM7l6Ju/t05IFQ0DTPRyNq1t3mltIxwth2FVhEXz0eUrsvEHDdaqrGDnRdwkO9Q3a4HRt/L2Kr9oiTyjbiH/3Xk2y5TuoYo1CMX9y8o+qJto5bcStSlPvtHUdP+Gpen8tEvN7vMs/Z4GLd7bnfVB7Q5th9byd+nXdt0ilZrWiUckK0KxsjYvJMa1hxjio2mMFVmFERCt3L0Td/bog4jZphO0XqKI0627RyNqnu83knaFqw5vfoc2mEMt8V6SHNEOCqkOuB6r+pRdV+7dCPuW9XejTPsiXGQ7EPsNFAn0rrb6sbhniqwrY2blVoB+8pHO3N1R1x0/4el2nsGizzR+1wg9u9Tq3O/Vdx9byd/dpBMALL9BIrWNjCKqiATpVbYOG63Qw2CIAmcSfkqPPim0YkqtyY9oYDriOr8tGu7cpwUTFGjMHywdcvJTPINvuRvHu9mlotjwTAYz4KjxPwlCkq1YyygjFHzK7SN/BQd26K1LRHA/pmiXHM2oc2akDe+jDIZtdV7Ah9lkIeVPKfzcm/NeVfV2nCSryAAJTZNZyGAMbmBfvOn/D0u13YNEh52fnz/Y46pvXk31T4H0KrtBvsO0es5O/u0SOw6C8wH9kG9GxwyxTnX2S4I1mgmIj2qs6k92H1ULFceK6tBExIiwry1GH32O6QWud3YqjwdxUVa2EcsVa1ple02t+ihqO3fL5aJneqY+y34lS80fEqXmj4lS80fEqXmj4lS80fEqXmD4lSNiS0QGeiBrCw2qsM1rDeht3oQkFKufZLqu8DsVYxItyjuQIrG+YyAVzdhOWAy8z/AAtL0vlo1Rs9SNA80IevkaQi41fmotZS8e9Vm7bekz5th6zk79LM0BIS0FhslcoNrm4thxXlJc9xceiFAkKdkFEKM9EqUYFnXFelpG7OwLX2hRA2Ks2sDBzbFHliDxY4d3yXlBA+M/pot3qQ2BNohFwdCMJCKo3kNFaJERKRhvVHRuquD4wjZG3eqPB/D6pjmueA6DbZfVUb3BorRdi36r0T+jpqEEX9S1gcUIrcvJsazj2nrQJAgQSVUa0Y93m/4Wk6fy0ao2D1/f6rt8+DXdEquxzDhWHeqpLDd20fzZ6zk7/MqyCJxToQjELVM5GQ+XyVWN2zsCDowFXLRJcraFRUjGu1mk4HuKbQNIbExMSSvT0n4ewKYVV0FFVHOo3TAMo4XTRY8G6w4j5qK71IbAm0od7TYlruKdQOLeaazD2cRaq4oqZvtCG/DtVy1qVh9pse49qLPtNG3B3dJeif0VLRWaeKkRfyhutUXOwjHPWsVakaN/Cai/GHHFAuLzZRgkxVZrDi2txPm/4Y/wAT5aJDZ+2d3mQY7YVUpGbYHYZLyFNHCfw29Slsl8uqHq5N36Q4wCmdqhZI6NS6PaFCCnFVtEjtXo2bNHp6T8PYNGsuVtUw7GRULDLs+irNGjk7kWPe5hqms7frG1CnADhVpBLJ4yzGCFJQ1MTDZSNs+NsN6qleTcyk5pnmDag+koaVtxtxaV6N+xS01HHKxVXA3Fa7jg0qJmN6Pk20Y5VO6ey5TlYNUfh83/Df+1BOMJqkxVJj1Kky4KkyVJ4Cf4Cf4Cfkn4BOwCfgE/AJ+AT8k7AJ+ATsk/JPyTsAnZIopydgE7AJ2ATsAnYDrTsAnc3rRcJkmFiGZUfJ0uIaTvk5Ro25CHwS7IerkFw0axgoHboinwgGv2VFBufYjLOzTgdyNG4MdyTLolUZNUPBPjcvTUm0dg0TUIZ95VejdC1hjw0QiLrRo5O5azuk79RQdLxuVWMZxk6HtC7Y8WtO5eUBeJkAGI9tvO2ix4uVxUHGiu5Te9ejfsWrvGmw7lEbLFAOzqrAqvSOpLqMQb2D5+d/hH9P5aILPQEMUMUPMsQXd5sPVDztRzr4w3KtRcRxs61EEdE8RA9Y9XIb9MAc0HyKPPENk02jstxPd5npGSjOxNoyKtjoywhoxn26DSGubTbulphPmwUWbVVcRmoFSXJ3LWf0nfqOjj+oYFeTmLL/AHc+52IV44dvzCEQ6+TO09i9E/YtXeNDnclpKpHiBqt2n5RRvpRuaT2wQ+9/J/2Q++/J/wBk6jbVDmmcbx3KkZMsliNYdXmwoqnOLu71GaKOKOKOKcnIo4ooo4oo6TijoKKIRxTsU5ORcHe6Jr0Z6S1HDKPBVaQt6Te8erkPM1vMqkvHJdPok6P9U2WNzzUPJ/i7lWB2pzKPyhhAwA36JaZOUoKD3aNRuxSGwJtJEjUdjcdoRozVcIHt2aIZqLXUd7IFmw2cDJQe2FgpSdwbDtK9E/YtXeNHoxv86R2Hs82D6PYe3/Ygyhc1ogtQ9Jda8nTbC08DD1chtUd2nWPm0JdHyfbV4aJUe138qkdq8r9nDMWy2hOpH1IQ52QQFM9osEANzR5kHwxUZ6NRuxWblTNe6FI6TnStFqZSCrTM3j5WhUR/y6YdF4LeuEE6jgXtgDY60HeJKq5j7hXB2W9qcaWiFWq1zp3kxxK9E/YtXeNGoNp86R2HsUvML6agaPaB6inJyKKOk6Sj+wnzfRnctV3S0VafbHrmqzWnEA9XqtXf5mtu8+VH+LuUjtXo2bNHp39LzNcFaujUbsVm5VokWiO9RWKqk0TpspLs0W+iM4PjtbAJ5pqKIhrL0T9i1d40am8+dqu6LuwqzzI0tD0XdqCIsLviKpRZSP8AiKp/vHb4HuX2jnj4Aqf3D+H6qm5tHwd81S/ds4lP+6HxfRH7r830R+6/Mv3R+IL90fiC/dHiF+6PxBfuj8QX7p3EIfdO4hN+7f1fNN+7f1fNfuXcQv3J+IL9yfiC/cn4gv3J+IL9z+YfJfuT8QQ+6dxCb92/qTOY/q+ao+a/4fqqLB/wqiPO+Fej3hTeNh0QdRu2dUlGiblWbwPqJaJb/Mg4ef8A5YyJ61Ir0bNmhp9hp2tiqP7tnwqj+7Z8Ko/u2fCqP7tnwpnMbwTOY3goWSVm5UkH1WOiY3YlOLYFjhD3VSfdv+FUo/03xExqlGvX8m86oHJNqpjTUcaMtbW5vevRP2LV3jRI7fO1H9B3Z5vpqHoO7fUhDQENIQQQQ0jQEEEEEEEEFFkpzFicx8apwMlkeC8pRA4EjvUWPGDgfiGh0aSdlI4cIJziYm7zdU6Jb/NCCahihjo8o+VgkpL0bNnqbVRfeDr+SovvO35Ki+8/V8lRfedvyVF94Ov5Ki+8H5vkqL7wfm+So3McA8GS1d40Qih5rfIuhaRDj5rfKMLoyY6wRvVH7/w/VUR9p3wKi+8/IVRfe/lKovvB1qj+9ZxTD/qM+IL3m8Qj4Kenp6fgn4FPwKfgeCfgn4J+CenLMcQveHELMcQjiOITsuKen4J+Cenp+CfhoKzUaJ20KbhiwHgdGtS/xXdjVrHo9/m+hf8Ah7dGazW1bVtW1bVt8wrb6javEfN8R9Xt4HzNqmej8tDNUujYRIRvVDi74VRDnncqLB/AKhPtkbWqi+8CovvQqP71qbz2LNvEI4jineCqTw5Umfx/VUmJ+P6qmxd8f1VNi74vqqbF3xKkz+L6p/hyOI+Je8z4gmXvo+KoR/qs7VQH/UHwlUH3reCoT/qs4qj+8ZxQNjm/EnY/mT/Dk/PiqX3viPzVL73xFNzTc03Pgg9tIPdjwUKUDGuO/RrU38U9jVrHo+aXUTwMuooYpuKbj1JmPUmY9SZj1JvO6k3HqTcepNx6k3HqTfATcU3FNx6kMUMUMShigghkhj1JuKbim4pqbimoILNZ6CjgnYdidh1p/N61SYfmCpOb1hUnM6wqTmdYT6OLnCAhC0WmGgvYCMXBOwT+an4J+Cdgn4J+CdzU7mp3NTuaU7Ap2BTsCnYFOwKdgfG9OwKdzU7mp3MTuanYFOTsE7mlO5vUjzepHm9SdzSnYFP95UnveZFxGLXDqVWmb/E7Ro16b+J/K1ax6PmyKrZORbIyP+yBBBBNQxCrnIWfPR6L8TlL9j1x0T3adU9HRrbj6z0jNqq0mxzDwKtXpKf+J/KFrHo+fqb/ANgCHmhD9ihp9EOk5SPmjioKfnE2OgiBMxUFFGto9I3ou7tOqej3aNbdpz0R0TUfM12dIKFJSb+pyiNy9JT/AMQfoC1j0fP1fxDv/Yx+0+iHScpHRPRFAbtA0Th50VDQIL0jeg7tC7VJah6Hdo1t2iazQaQSgbFDS/Lin5cUWmBWtvXpnZ1vmo0VGfcb2L0lP/EH6AtY9Hz9XePWv5jvhT+Y74U/mO+FP5jvhT+Y74U/mO+FP5jvhT+Y74U7mO+FOHsHh+zeiHSctU79E/VTU4Q3qSAECq2gWr0jeg7tCnvUitQ9Du0ax2aNZQQcgFHzfSHcpr0rc+9q9BR9Fel+0fxG/oWsej5xeXQxInknhlxncfWa7do9VqnYVL9l9CNrlqnfo1vUwM9GKbYmNigRLRVio0jf4bv1NU95UjsWoegOzRrHo6Nbiq1quWac04hRUNEl6V2idEeh2L0DfxdpXpvtHTZ+ha/4T53K/iUnaq/k2xhWfCO4prraQ/CEGPc2sdUjrEUOcfU+kZ0hoOKOKgIl0ET7UUcVG+KOKidy1XbD2KXnx7E2NW05et9CNr+1art+jW3aIKPmQKnBAzTYwwUUycZlBogqowtWE1XChSNH7t36mqZ2lSOxah6A7Bo1js79Gtx01VWUEDp9I/xdo1aH/wBfavQ/if2r032jpUf6Fr7j50PKHCkpO1Tof4o/S5ThlFelpdrf0hQa7Jp7FQmGtSTAPKF4jzVR0dWq50+dA9wVW3zvSM6XmajtiLDthHNNpWUkoVbuxFuJEzCyPi9Vmg4qa1XbD2KXDz20dvtbymNFYSGKiZtgMvWehbtf2rVO/RrbvMATslG3QFgVqFaojbocHEmxCkVQ2x0elHQd+pq1j0itU7FqHoDsGjWOzv0ayiQcNEdEbVCzT6Sk2lTXo6LYz9S9Ef4jl6b7R0qP9C19x87/ADv4lJ4mv8j+Mzscp/hXpqT8H6Vq0nQd2KVHsb+gL0jR+6j+coeUpRAapZCVmqmlp1W8PN9IzpeZqu2Y1etePElGtsHyUJWmzx8uKhq4+OtTWq7YexavDzy90YwsCL3VC6Qj43qhYdY7iUBa4DfpAtjuEUKSk8kDB/s1gRW8Zrd53oW7X9q1Xb9Gtu0R0AX6AZKrGCbAxU8kCqzgIwAQu0VSJSKjJAL0o6B/U1ax2lap2LUPRHYNGsej36NY7NBu8wqOjXpNrlNeho9g/UvRv/iFemp9tH+krXGw+dP7R/Ef2Zr/ACf41H3qYldavTUnRo/0rVf0Hdi1aPYz9AXpWfwT/wDYvS0+1n6V6J/R7wq9HkQDxVUkafSM6WirDMoO26CxxjCZuh4G9Qccx2L0r95O+B8YqDmGQmLc7ePXdJTWq7YexavD1EGvAlE1th8BUd7nViI4z0Ob70bQ6fBUlW0EESMdYcOxUlGariYeLCnFtGQXGkaQQTPVBvN0D1JnKNaJhUjB1trIAxlaCmUoe7ygYGWxjI/IosMDb1HMZeZ6Fu1/atR2w6NbdpgIpqCvgn4KkJ5KJGBUAqtI4u3DSL1B1aKjYvSt/hn9TVM7StU7FqO6I7Bo1nbO/RrbvMMUbtBNaJvG7RN/4lNego9n8y1H/wATuXp6fbR/pK9INh87W+0fxHfpUqL+LRLWbsK9M/oUX6Vqv6DuxatF0WfoC9Kz+E79a9LT7aP9K9FSdH5KtRN2Obws6lrbdPpWdLQQGkc6cVfeJpsSMADxTdV0sI2fms+Ja+4+Id12xel2tb42YqPVt/8A6x4LWK1XbD2LV4eoqNjjIINdz+pCcrepAW4pzCahOt1oUbqhaHAC206wEck1hj9n9lzhOcWnIzhbGOK8r6VrZPMxZVdgBzcOCbQk0RtpCDE2SFhyTSaVs4Ub3XewTCI2G3zPQs/H2rUdsOjW3aDGIKNVANinPMrE7JThVQan1gbkfqg+1AiCggsFBRpW/wAM/qapnpFap2LUdsHdo1nbO/RrHYpIDQaw0hoAGjl/i0VaCj6PetWk/idy9PT7aP8ASV6QbD52t9o/iO/StRnToe0IRznBemf0KLsWq/oOyuWpR5tYPyhekZ/Cd+sL0tP/AOv9K9E/oqThzXB3GRUDv0+lbt0ClEMDEJ1FbCHEQ2WwzCLYXXc5uPKE+IXsG/KMY9RVWlq3treBuXpG9BRLZwERPxeplajthWrw84NESiSIgQE6uKr+yB5gIbI2zwVGQ8Q16jql8wO29HCMlrRLCABZAmA3pgrVwHNq3OgRHk23Fapqs8nU1pGsHMPyPUp6fQs/F2rUdsOjW3KeirAYoUtqNG6XJNqwQJTi7JRRBnYFcNI0+lHQ/mCmekVqu2LUdsGibtnfo1js79DTJOEsFGYUdErIT0cveqzgMVqN6J7VqP8A4n8q9PTf+v8ASV6Ru/TIeL9Ov9o/idrVCi2Gi/U1aw/GvTO6FF2LVd0D2LUodlH+lekZ/Cf+tq9LT/8Ar/SvRP6KhSw5wI7+5RbtGiYXpW7dEm9LxtTZGvAiyJrCGYcBLegDkc7O/YtoHjgY3qNLRymWunZWEL/eaVrs6OCsN4IgtYrUdsK1eHnRTR6MAWiO1QRZHDLO5CUzMj6qEo22wTnmyIvhKS8m5r2GFQgwN81/8QktGpScltad/YvKF79YRaAa07DdkhXpW1TBrtSz2vY72r/41ZxjFg5GQhOF8im13hrSBGVbVtyQIDhYYjMEaPQs/F+pajth0ax2eZCSKigLApwQanOMKpQEnICxVrzDDRHR6UdD+YLWPSK1TsWo7YNE3bO/RytigYG9CRzQB2rWy0xEZW3aJO3qNIPdmosGx36lqUnT/lXpqb/19hXpG/i7NOqN/bp9L9o6Y7F6F21n62rXG169KehR96FUw5h7FqUOyj/SvSM/hv8A1tXpaf8A9f6V6N/RVRzXYEHgotO3tUCVML0rduioGnVjWlWFbqsVJz3HLw2CdHWAcMEKvlaKwWjD6YqL24gOHSEL8x1hHymVQKYleMO2xaxWq7YVq8POJEjDNFph4K8k0NPKGzaq7TL5IxiLIQnnan60BIRMcfqvJB8BEkCHH5LUYWuql4Bhf9Jpj/K+Vm5wi10zVqzPFqpHg/8AxqUUVUBrfarN5Vs4GeCpHGFIQ5wM/Eonci+ieHTDGVmutqwtbHNFwrEW4zsPctVsrCRxno9Cz8X6itR2w6NY7FhoEYXqS8jyr0KSLQ6rmi0QLq2aJIMbEK0SgIoU8yCAqtjj26d2j0v4P5gpnaVqnYtV2waJu2BVxJQrbNDnQiEIlBQVd2xSG3RqlQDnYwCjRDMH9a1H/wAT+UL09L/6+xy9I3f2aJhag2u/UdPp/tG1i9C/8P6gtbYSvS/gZ3qR2FejodlH+la7P4b/ANTV6Wm/9f6VqO2aK9H+DrbJTUxtXpW7dGo3p92mq6HOlBeRpwPZu2O+ShVd+HfcqxAFroDxBaxWo7YVq8EIDXAimfetTfvAm88IFVQg8TjHFSgL7V5PVaIggR236aBpNGaM2xLm3E7VFzh5QShGEzNMonUlSIMBrONxt7EG0hoxRkNI8o12PO67FA1nDVjWeIGyKBpWPoXRoaoY6ryZk1oi6RiFZRke1bbC6Ow3qJDLHBxaY4otJBkQvQs/F+orUdsOiZ2IIIFDFN2przGMNibRx1yYqIhW3qXL3oNtdW2pqAvQxWDoL3o7kBehWrR9mHXFRJ2lOFHTPgYGKi3cNEK2xF9HQkZx4lW3SUf9TqQF6jY+ClNyh7cUBeoaNUrydDHInivQUWwdbl6N/wDEPYF/iKXZR/zL0jd/YrFMLUG136jp9P8AaPwL0VJs71M7SvSj+GO0qW4r0dF0Gdi9JR9B/wCpq9LTf+vsC1HbDolDA/q/sqpUxtXpWbdHlG1bJxWD49SeOZ8SpA5pMIAi9F9LWsaGgbVXa5sAYi/FVNZw1rslNajthWrwTQ1shYLkMBwTcE3BTUdi1dW3K1awsmIoskZFRtUA4i0DrVM7WO2Z1uC8i4PgCIGsIwJj9U6mY57r3NFkBIfKCiCMU+jc1zGVg8GtPmyh1KqPtOrR0RpWxDYlsapuJyjJFrjb6SBEDGEbRLAquWUjp8utBsY+TFu+S8tQ+9QttxbgvQ0e/wDUVqO2HSMepyGPUUMe1DHtQx6im49RQx6nJnO6nJnP/Um87qcm879Sbzupybj1OTed1FNx6k3HtTIwrRNsL4YrvQomNYW1g5utrVZZYnJShokUfs32ejIhGsRrRhacJpv2hgpBIOEYG514TcVR84fEmGxwOwhBBM535kNERDFVWBov7AvRUP4P1Fei/G9f4il6NH3r0jd/YrFMLU/E/wDVp9PT/gXoqTonR6Rv8P8Am0ejoug1a9H0H/qavS0uxnYFqO2HRBxGI7JqIUxtXpWbToCCCCCCCgtR2wqSkNg7NMlPRCeCD3E9SGtPjiqpg6RGikl5LeV5WkApWyhVg1obwlCJKcyk1ZVDCF0lEB1UtiIwNyix0Lnk7nfVf6jmggVZ1oieIRY4mEsc06AA1YRslGNqJbUN1hvGWxeio9/6itR2w6Jo6I6ASi2wqlMYJ9hkUZk3otbqmxAhC5B7iJjaLVXE1qyKjq4Yr/EO/hM/Wrd6ZTOqvFarDx1qA0RimuZUhEYYprdQCAq2bFMw3qs7Wk0plEINkqriYlGrNAbU/BvBPPst61Fw4qs5QFAP4feV6FuZefzFf4il6FH3r0jN/YrNGp+Ok/Vp9PTbGomjpY813YnatURsjsgvSM/hn9SsnciKGiqsrmoJWLWo+i/tavTUnRb/ACrUdsOio9pzWpskoO3qo4OhGC/d/mX7v8y/d/mX7v8AMv3f5l+7/Mv3f5l+7/Mv3f5lWBFS3NSViCCCiVjogUXIk2xkEbIo4ninMIYIix0RaYXry0aSjMAX1as4xN6LG+SbbVqueDZKEBnmrRG4SxDVqvONHYZVub+ZVqMyg9hJheR7Udmn0VHv/UVqO2HRPTgiomOGi8KU1ATmmjVMop8JE1cFSBsQ2IQgpJuKpfKF4bLBend/DZ+o6Nel39ykdHK2aPTfEtbUtvVJSOgn4Rgm3thtQjBV3Kj5vaqPm9qoxYOsqjPs9ZXpKMZjqYoUNF0e1f4ik6FH3r0jN/YrFNap/iP7dEGuOAJ4LW8pGBcJokEVpEQsF6d4C8qQTGQhLagOcnNAaLGiFiL4RujZK1CJdec8EDjxVFn8Sos+KiIVnQVH73H6JvvcU33uKb73xJmfxJmfxJmfEpmfEpmfFMz+JM974lR5/EqPA8VRYHiqLmniVRc0/EVRc08VRYHiqPPigwAiyzNROCdC3ZiFVkmvyO21MHsfmKjKqWPMwCISAXkQ0tpNSDNWtWeC4xcTC8ZoBzhVaKpNyIY4yrNMMLfoqana00kIMJGrnMSGxClDqUzdYJckjPejrNc0AtGdoMNHomb/ANRWo7YdGtogqyIUVCxQkZKKeHNgZe0E10I3IFVBKcFGZUQhcOqGj0zugz9R0a9Lt71qnRytg0en4oORY+kiJK17zbZkmvGKbRGtGxBwiPN9MMq54CChR0YwY3sX+JpOhR9pXpGb+xRQQbIYx3nRqP6LuxSGwadv7ZGRmFzRuUBNVkG5pgcK8hdhFeVpIjWDWwj2qJlev8t0Y+UomOjmBVPWETqCEzHaU1tC4kxfSPAkTq+Tidl6dR/5dJU1q29eVpHvgAXNnDGWj0TNh/UVqO2HRPQXSuvUNGElVTasUXNi6WSEYYJtIJqCfW91UgfNmpjf5npX9Gj7XLvWtS7e9artujlbtHpnbCoOq1SomxRkhRvQpRG5VTUbOHmRe0e8FGmd0XdblDcv8VSfw2dpWuzb3Hzm80cEA0kSP1TsUcSjiUcUcUcUcUcUUdGaOKOKOPqCiijijijioRJMmiKdSiEINT60ByfavARJLoxLQOE0QHQN6dj2IuvzuuVLVMJxzAllJOooB7HBwGQ7kfI/Z4G52tAa1h6jJP8AJmBtlYPFijBgNSsA5sr4G2OITsez5I46PRUew/qK1HbDonu0EKIinv5OoOsoC0qsIRtRgJI0ToFpgq2tCCDJ6IWoO0STr4L0r+jRfzLvXKPOPetU7dHK3aNdzsk0lGwFMLZmy1UTnVkC8tZyRbDFCjmPM9IzjwVen2mjHExVq/xT/wCG39S12be4+fqO3dv7aHtLTehzzwTmvbqutg5NZBxsOq7fZwT2k1XCcoww2qs0EwjfAjjJVREp06uq2ENu1NpCIiw7LU2jYSyuWyFW0xvuxvVeDqRoDrWt5o+avjMX7FWJdiY8dPoqPYe0rUdsOie5QIwUULFPJNNqBEkHCFhCBQYIlOiHmwyDdqqoXoaZwXpaTZRfzrvXaFqnb36JP3d+i3Yg5Cha5zd6ayTxI2FCm1WyXkW1YLykjI+ZrOPNY49SrfaP/Z+huj/Ev6A7Qtdm3u8/Ud4v/wBgFKKsYTjFakfeqxxXtwskMynOa6q8jV5Fzpp7S0vDSLYEzVm2aZGqAW1RcJcFF1I4ThVAOWe0qsyHNJdtj/bzPRUezvK1HbDot2IvEBfeoNANwmg2xPnKITpHBeUYK0k1sReoZIG2aDA02kOCdSOGrK5XqEwq96PJInjigHBxUaWk6ND/ADrvXaO1ap29+iT/ABjot2JwGrPJO+0Mc06uSY9kCJtkdoQoHB0JGRTGlsJxwUXcg2Ww8yDKU5AcStat7tI74jDR/iXdDvC12bfP1H7P28iq1pINq8oLNYW4bUC1rXQA5GAiJS7VVAaLBokYCJunBGlfaWS5Fzp3YSTq0iKttutBH0oq1fJu2Egn2s4oAOxPmeio9neVqO2HRagwKtMaCOQ2uU4t5pwVM5zGVasb0Gb7Vgoq0QRDiC2ywp0SISxTqRwaJN60RRmFsF5NsHzOK8rrBq9LSbKL+Zd6s2jtWqdvfok/xjo1XwwQAESq0xavJVq2MU2liE1pBTB7Q8yp9mccXH8rfqoMd0aNv82j/EHod4WuzpaRj5mo/Z+3upagEJRmc15IOzPUFFwOBDu5yDYwkCSYXDZlosVXXZGtXeBbl81S0RDyNaqb9beO1V2/aXkVS4MOUWzl5voqPo95Wo7YdFqd5WFsl5OQC8pMu3Ko4tUUQQQIqkfS68m4JsFgr1JFETiiG1XJroPPJQAjco0lIcRRfzaLNre1ap29+jVf4uOg1XwwHag5qpATWmEKTIo0Qgi0TmvKTqEZw8yFDQs50Pzu+QUKLpPceEhoD3Vr0GzWZO9BQ8zUfs/2GJG/s+nmy1f8wRbhV9JLbFPaKRpMnQrCyDr4eb6Kj6PeVqO2HRar1OsmmySaEDKqeCMYQXlCS91liEE6jk2SjJ0F5MYkqs2aawQpLRLamvqQR/yxYjZOXBazujRdjtFnSb2rVO3v0ar/ABdogHRyUWqtYntdGMWqNiEFDTGWK9O1tzP/ANbYdqq0dG3Bg65+q1H7P9hgc5SvUjE36ohyRO09mmabRV3hrmv8qasRyhbfn2ofanmIq6ksRVn1qs2EtURB7dqdECU7JyOUcctPoqPo95Wodh01hDFeRc1sYgi9RKqXRJVIwBzqGqMVXmnOsVI62wK8yghSN1vkhVT+T1ouBEd6LvRm1skyj1oxJURELXfsouw6LOk3tWrv0atJ4u0Ra4dFNY5rLym0UX2YquyIsKbBEOrBx2XIxgWyx0xpWxsbrH8M0ab7Qcy1nxGsfV6j9n+wiiib3WuKEQWGsxzQWnxn5jnwdEmEc15IHnuEDeAFh42JrI121mnK0g2zVGfSUbo1jMYHR6Kj6PeVqHRCOxGmYC1xYbQnUrnF5MW42pjo1nFxGcEaN7ncoQliqN9HaCHXJ5Oo2G2xBk4zvRcKxEMEK+vZdtVbYnUb6NoMWukgBFQYXKuKxEzNGlPk2yhavItAfcovpP8A19h0WdJvapb9GpSeLtFWhpD0e1FzvKVptTaSjjEQITWsgNgRbSVKRpqusdch9njEyURWN401KOlpMqvG3qUTXyc/e+Q9XqP2eshNO3ExGMkHNjWOfz3IkTtGq7aP2FtarbibgrYeIyUPN6pfLq0VmMaZ+TLqwvqOsdxRgSz0jReLRtGj0VH0e8rUOmZbCyxeUJcHlpPBeTbVcNYRnioCSdR0tajZXAtuhFV5EFu1NrVnOc6cbZIMR+0TLoBplBSgVR4xgnPEKxT2ga5IwTTRywXk6YRsdIprQ32p2KLnn+H+nRZ0m9qlv0aj/F2j0FJfyO1OoaGvjbvQNHGtAYRQQoqOPBMp6OLoTRPtSwVVg46IUVHRC19v4/8Ar2qrRx57vyskOv1eo/Z6wtLHXWb1XZBQMCqjgbnap6Q5B3tlu/YYGsLHYXFEgR5NaIJlITPX50xwPd1rnMGW1NLm1CYRxnEWjYvIPBozVMJi5ViXQqxuC9FR9HvK1DpbaoqR16ua8qyN4kUWOe6udc8m4IurE2tcRLJF2Sc6AkhRe1biq7DOCZRNrg2BOpGtdCCrOxVuCFI4nBCjOKm/8H6dHJ6Te1S36NR/i7RFp3L0dXFUZZOZ2p7napg1vWmUsqQRghRRdRki9OdSFrmwAFuaLffb1hCmcADI25Yo0tKXDnCjb0nW8GwG9BoAFjQGj8P19XqP2erDREmATi0Aiq11kbTDs0CjdG4prhVgSCIHtBGYKDrZG+9Rsn6/C63JRLoxMRAg2TwGxdXm2wlaquZF10NqjsETKw/3Xlary6BpJwhGG+KAMjWGNi9FRdH5rUOmFKCBKBioJgeW0ksCRIoM5NhmhRiLtnFMow53JvKawQag+jdSUj4msYxuAuVGWkOBmTC9OdIuNXBBwmZYKPowLEyy9GJwTaO2UU0UpLpicFrUvSH6dE29Jvapb9Go/wAXaPJ0bnbEx9tqDKSJsKbFyZS0spkYaAZq9hqnqK/+PR0lMRB7tRotjiokH7uw40r+Ud3cFD1eo/Z6qGZuAtRcdXWeMOQz5lQNZxrvxNg2BeTpDD24O42outnoipwdEe+LR80aOHlLDyaQcl3y9YKNtYzwGJRZVq3zzGScx18YxjcvG31AquaXFsXB0pxhctQUYFVo3xOj0VH0R3rVOi1U7aVsA1zL7iETYZplIYUtJB3JqhPohCtXbCWI3qMDgq9+5Me+BbAYqiq6gqnbamtbNUc1CME2joq52r/5VLWEmstOJwR8oA11WInuRPKfHCUEazq1gszWtS9Ifp0Tb0m9qlv0aj/F2itREYlqYRUaIu7EKs7UCYunkmtsAGzR1qM0ftDwG2Ns2oNbkJDPE+s1H7PU4GA53yxROLWm3nv2m5QkJDR5Vxdj2XaIaKy/0aX/AC3X804p32V/k38n2Th9PV1w2HsmzbfuUReSyTujcVEwuFvcPWeio+iFq6Yo3qj8oaSEzwjiobNAcQYmWBQVJM0bvwpzxUhAqFytrIh8HchODnVKP0br7Jp5e2kjJlyD2zltQdGFy1qXpD9OibekFLfo1HaABrSmEBcmUvKCaywQ8ykOoJN7VcPxO7gur1mo/Z54bb9Si6UI+5d+M9yvM3dQ2DTCjPvEN84OCH2ugqO5bEZtdymdnqHHkkCd6Nb3ZWW9eiB1Zn8ux3yUPWeio+iFq6bMk4jVkcU5gJcYp7ol4hhsTa9WKCD815IwuNid5WtcVAyT6UVowTGW2ovFVghBObqNEXXry+qRBBti1qXpfyjRNvSClv0ajtALDWEYEHepRsW/JR8wHlOc7KxACAkPW6j9h82qCVSEyN0QALUaSN2LvaOQQbIeZ/ljM92iKgp6BZacBNUzXVhRkD3jVinOeaRrmty9SXVsZuwWJ4SHz9d6Oj6IWrpa3lSQgM0yMCVF4aCLCSmGkNIZ2SuVTkzyVIXVgas5heUAhaCqkimvjqxIRoiW2Ku2uDNVQ+OITnUr3MnFxgqaqHVS3PBFzGxBJ52OanS9P+UaJs6QUt+jVOiRVK4VaNohiTDctbkEESIVZXqsoDH1+q/YfMgq0BDYLz9EWwhEOFYRwuhtn1qrfExjlZCzzf8AK/F3aZTT6WwS5xkme24uyEh80yjkxobsTaMRcYBGl1Rqs63ftDmCoGt9Gas9g+aNNR1jbFwllpbStg5VWhsbL01us5xO2S+z0dJqCbpVgFKsLdtq9iktjJFuu3YQsU6lIiIBeTcYXqvSPc8I+xYjSkitVaLYXoNsEIaZ0nT/AJRomzpBS0ah8ydbq8wDf6/Vf0TphYK3Yi++PveyNgvKDbN5vK1Dfy4xjx86NHHmkHu0OpJUba2JuG9NbOk13flG7QGzJgM0BKjFbMyH1TqQxcYn9p9NTfxG9bU+jcaISiHOsva6B6lqmuY3+N6GhsQwmbrkHN1ZG6duSiK43i8FESMZKtDV1rzzctqJ1ajoWDMp4cA4Va19ydRQvinMIIXlZPTWarLF5J9cTlCG1ONrYaf8zp/yt0TZ0hp1T51ef7DqO6JUBEqt7rVXs1WdZUJYaNR2yk86tEG+SNKK9IYUd2L4dyawVWiAFwVHR2u3CZRPIbDN3yTnzcS7b+1+n+0DNvYoU1H73lW9QcrMw/8AlPciXU4J5DxwLGlQaDsQdSUVLzY9ahtuUyfYdPei5xcfZMsz9FXfEckRA3cp28yGgOaQUQYIxEU2sNFSBCpTCNFUlaSncm3Yoia/zOn/ACt0Tb0tOr5tyq7P2HUd0Sr7VGb/AIbtM1qP6NL59JRtqtdACyQknv5T3Hf+3f4qn3dyg+hOFL+thCm3pEcWOXpKb3m0TvylqrCjvFQLm/I7iq8WnWHCkaRi2/aFKcD2GOCOq1vtAz2qEQ3IAmyAT4wVewwKMgRBEBAsjCac4wF6bRgC04m0qKbRmvDgmG9f5nSP6W6NZu3Tq6IjCf7Lqu6J82YWrSdCm/2b/GUuY7grDCEKSid1w71PY+jPEwXp9tC38j16Kj2QQI2pruVFjhyaVogVSUYLnQcLXObY4Ykey7qKFK90yajWtAF5MzDcqvK5R9kTq5fVTjOamgW5qNqg1NYY2IGxRjHRkuX0j2N0Tbt0y0OA1cU+EQBFRmf2OTth82YWo/8Ah03+zQ+27R2hHydJkIjcQVKkPug8CvTUWynHY5Ro9jnII0ZESL53HAOwOdiFCBWoxOyq4QI+l4TBXqOaC8ucXOMqGjjdi7JMpHVKMuFFfA+kpXGzcVAXiUIaGPtJ4pmLuKqSBO9BwgSUKOQjvUdEEdaN5j1DRrN26Zed4iof3/YJO2HzvRv/AIdN2j/Zqv2ujONVSpBiw9hVej6dD3Kf2c40n66Nar+l2jT4gshwHrtZu3TL9nkdh82YXonfw6XtH+zQpKJ2zqKi4cOKrUVD0Kvd3KFFQu5r6HvYp0g2LLzjzCncxyd927qT/undSf8AdP6vmn/dP6vmn/dP6vmn/dP6vmn/AHL+r5p/3T+pP+6f1Jxc30bgI2y0kMMBE4Kk+6dxCpfuXcW/NUv3LuLVS/cu4t+apfuT8TfmqX7k/E35ql+6/M35ql+7/M319uw+bNeid/DpP1D1OR4LxBZHgsll+0zGTnDsKk05BQo2jmvpB+cr0Dvdn8FKvSPzB7dE/wBhhoj+z27/ADZr0Lv4b/1Dz8Jqu8gXN7x59YvHMcR5mSjcp1TI2/sM35UnaF6NhyUqTKld+YNKjR04/i9zlrjNvcDon5kEEMUMUMU3FNxTcU3FNxQxQxQxQxQxTcU3FNxTcU3EJvOCbiE3EJuI9fbv870Dugf1jz4l+4L0lJ0f5h5/pqbpu7dGSOQ3rNazdoUKRvR71W2/sDy6kaBqxwUaINMuq9R8trATo/0/RMc55rNlWFvPo03ylG6sIuawQ2N0OuZHYU8f6dJwinfdU3/Gnn/SpN4De1SQQwQwHBDAcE3AcE3mjgm80cE3mjgm80cE3mjgm80cE3mjgmc0cE3AcE3AcE3AcEMBwQwHBDAcEMBwQwCGA4IYD19u/wA7/Du6P848/UpD7x7E+jc8mGs3HMFHRsWY46aQUj3asHOJ5WJR934iujxRwbxTvdTg5sxaL16RvQ71BR9ZWcmpuCZzQmcxvBN5rfhCA9hnwhQ9lvBOy4J2XBHAcE7AJ2AT8k/Lgn5J+Sfkn5J+XBPy4J+SflwT8uCfkn5cE/Lgn5cFSZcE/Lgn5cE/Lgn5cFSZcFSZcFSeAn+B+y/4c9H/APY3z/Q0hzd5oUbE7Ap2BTuaU7mlOwKdgVAjatdnR79EPWVDFQ9kr3T1L3T1L3T1L3T1L3T1L3T1L3SvdPFe6eK908V7p4r3TxXunivd6/ovc617vWjzete71r3ete71r3ete71r3ete71r3ete71r3ete71r3ete71r3ev6L3ev6L3ete71r3ev9l/w52D/AOxvn+gdtfo8QXiC8QK8QXK26TAIgaSKWhzMDxWs3o9//gM/O/w52D/7Gq3zvRjpORx60fBTsetHEo5o4o4rMrNZrMrNP97rHanuIlYOc35p/N62nvTm2tI2g/2/3+fnf4c7B/8AY3z9TefWeTjK28coLyhj5U/ib8j3I89nB3yVX22/C5R/1Hbmw7T3IeU1XMaICT3wMbyn0c3CRvE28RL/AH2fnf4d+xv/ANjUMU3FA3+ZqDpHzcu/RhpGiXmxpXZQCLLLDa25wzUDC67YZjq/3yZ0R0FOXonthc2cffCfhHZNFDPq/uvJ37kdDqjdUzJKfzCn8zqT+YVSc0qk5hTuYU7mlP5pVJzCn8wp3MKLRMQ8yCJeSijHgPhAHcjgjgjgiijoKKOgooo4I4I4I4Io4I4IOIjySIWwg7A7RYmRNRocLpxR+56ij9z1FfuuoqFtGBughzB43ocweN6HNCyCfEaoqk8rBNDzUafJ9e1OEDaDYRYU5OTk5OTk5OTk5O9dJVicFDQDaAmH2esqjwPFAVhd8kGmIaN8fmq9rKP4AjVpugVFRTXe6qZrWgOEhC36Kn5/5voqfn/m+ipuf+b6Km5/5voqbnfm+ipud+b6Km54+L6Km54+L6Km5w4/9VTc4fF9FTc7830ThyjHfHzJK4UUXc4ug3giJkxPrM1msysyhiUMShiUMSm4lNxKbi5P+zmu0qjdOpnqmr1L3Y5x+iHMHxfRN5n5v+qYbWD4v+q+zH/SA2H6L7NzOv6L7NzOsfJfZ+Z1j5KiFkRv+ioaW0QOIIEepMLfag+4lUeB4qjw61R4dao8OtUeHWqPm9ZVHzetM5qZzUzmpnN9d5SQs7dANyFxIThY8b2/JUnOo+DlSfu/iKpI2s4lUnOouDinD/VA6NH/AFFCcX0h3hnYms5Lavbx844FOwRQbNzoAJnPB3rD+pHmg7NXtQzbtCddNOYA6ocDJAoYoIYFZaBGGUVl5lKb2/CqTEfCE/H8oT8eoJ2PUE7HqCOPYijnw8waAgoJrxAiIVA+47l9nhIvBxrKj+8dxTPvHcUz7xyZ945Uf3j1R/ePVH94/iqLnv4qh5zzvQZeTt/aI6rd57ll+wPbfFc4d6Y6/RFWltO9sZwg0jhBfaRZSUT9rCzrC+2Mh6MO6FJ/WqVnLoaUf+uuPyFUUZgMO11EfzCCrQqkmMpgOE/eaqKk/wA37P8AiZ9IHqKY/wDyaeB5r9b5OX2nnUe6fbBFnKLnHOQ01adhucHN7/Mi0qO6Xnh4LTYdybEny1LO7BeTbVrvfm8xP+11dUcr9P1/YSqSJLaWEfZc2XUqZnKo62dGY9VqY72p4GR605tjj2pwtEUx2XV9EDfpY3lPYNpCoRY6PQaT2BC6jedsG98U5/8ApM/E6t/L3qlYYAgSJhbl7RKde4u2w7tMKrua5p8ySFA81rNw7VQj/wDuj/qVBn8dH/UqDP46P+tUGB+Oj/rX2fA/HRf1r7Pgfjov61QYH/kov61QYf8A5KL+tUGH56L+tUHh9F/WqDw+j/rVD4fR/wBaofD6P+tUPiko/wCtUOH/AOSj/qVDh+dn9S/+RyaM1efWaR1GPra1n7LU6Rs+fm5LJZLLzR5wQTKTlsDtonxtVX/LpH0eR12qnZawUmbDPgUywmqcHCqiLDDZ4gtVppKV4rWQMB1BN9qfScT2lUbOaNgVEPbUeTRvd+Er7Q7k0VXpEBfaC4PdSsEiIQrW8AnME6R1J0gOqFmmsxwyTaRog4EwEZziijgjgqN9tHFfZ/uB1/NfZ/uB1/NfZ/uB1r7P9w3rX2f7hvWvs/3DeBX2f7hvBfZ/uGcF9n+4ZwX2f7hnBfZ/uGcF9n+4ZwX2f7hnBfZ/uGcF9n+4Yvs/3FHwVHR8hjW7F4ivEV4ihiOITSYBwOwx86Fu7NRhn1bUS5+79kqiPAYouMTafVlFFFFFHBHDTkslkq8iK3SEVewuotkxwKpYQ8ubIatGB2xTKR2tWDoeyatYYlUQ/wBOPSi5BvJYBsaiskcEcEUVkqCkMTRmOLSWqi/ff8jlRfvf+Ryof3v/ACOVD+9/5XKh/e/8jlQ4Uv8AyuVD+9/5XKhwpf8AlcqHCl/5XKhwpf8AlcqHCl/5X/NUGFJ/yu+aoMKT/ld81QYUn/K75r7Pg/8A5X/NfZ8H/wDK/wCa+zc1/wDyP+a+zc13/I/5r7NzHf8AI75r7LzHf8jvmvsvMPxu+a+y8w/G75r7LzD8bvmvsnM//Ifmvsn3f5j819n+zmNHRhpsiENEUBIy2Gt1CaPswbm63c35q28nG1WZKqHEkCMMkznN+IfNM57fiHzVHz2fEFR/eM+IKi+8Z8QVF96z4gqL71nxhUX3rPjCovvaP4wqL71nxD1XpKIe67tHrPEV4ijnxW1ZlHHrKPglHPiUc+KOLuJ+aOLuJR5zuJXvHiV7x4lZniVmeJRx/MUeceJXvHiVmetZnrW3iszxKzPErM9azPFbeK28dO312S2cF4gnUsmMrdnGxX0jwMmiJ4lfZWf6dc+8Y9VnUmMsDGQuk1NHtR2ArJx3gI4AbyfknH2uAAUbYu2mKIskoqxTU6JvNYT8R+iyQwWQWzh5mXrPSt2EetH7F4ih6k+bms9GxHScNGWjxFBor08hcy87fkoarQGtHBON54pzrSfVTVampJ2Qb8I+ejxFDzsvVxeDm5BsoFNHsu6lR813Umc13Umc13UqPB3UqPB3UqPmu6lR813UqPmu6kzB3UqPB/UqPB/UqPB3UqPB3UqPB3AfNM97gPmm+9wHzVHgeH1TMHeN6Z73D6pufD6pufjem5+N6Z73BM97gme9w+qZ73D6pmfD6qjwPD6qj97h9Uz3uH1VH73D6qj974fqqP3uAVH7/AfNUfv8PqqL3vh+qo/e+H6qj974fqqP3+H1VH73AfNUeDuA+ao+a7gPmqLmv4D5pmD+pMwfwHzVHg7gPmmYO4D5pnNdwHzTcHeN6bg7qTeaepM5rupN5rupM5rupCjaKV7YOM2tPs5nNFxmo+rioGJunwmgYkstJNuO5D7v830X7v8AN9F+7/N9F7n5vov3f5l+7HxFfux8S/djiUfu28SjzBxPqZKPE9a1ipKP+6j/AD6UajeQ0+27HYFHWJUfW+ToKd4tDIDa6Xf54Fsk0ZpuYQxHFN53qZFSUZrNQ/3KKxQecGtm45fMqNkmiQGACioebb6iH2drefSdTB8yPPrGPrdUqX+6wVwESbBivItFGNrzi76L6+fb5s9OvQs5tHW30h+QChNG5A2yUdEBDHRFDFYFH1Mv91v0eTHlTyjJmzFcVcPUX+fX+00xwNT4BV7VZpgq8jb2qY2d6v0x9VZt/wB1gAvKGfIbyvlvUZ+tgCpO2j9IPfogYm7W+GarRPOJPFVtqIt0wVdkd/zUtERmNEPUzG//AGSl+0f5bK0L7G8Uf9Wla3oz6zLqX2cCbqQ51g2/BUHPpBvB7Qh7NP8AEyPYQsKfjR/9lTXPozvI7l9pwYfx/Rfaea0/jC+0UfKoXbRrdkfOyPAqLvBRpHBjbShRtFG2xtp5xvKjsu+a8W6Jeq1epSdm93VLu0eT+z0zvdq/HLsjprSKq6fZVUw4Ktt7fqoKWZ9Vrbv9j8u6Lv8ALbbdWPNB7UAAGyaPZa1ZzG7kbsF9J1pGYjK5DG/A3jHJX2WG2OShfGAnKA1c9izxhMdISUdhvgfaEp7VG+2GXKHzF6j1fml2plJy2Nd0gL/7L7O/kg0R90x6jFYU+yLPqocqnxjBuCoaCTGQPOIrOJF8cCNgUb+sXpo5IArRiQIWYytTQZAV7C6/ZH1dvmTZt7F6NmcXfESdEKBjfvKSO5g+vmB1qIzGiCiGOxB46I7cVCXH1Wsf9j8lRMbOyuY84z+izjbcfa8QC23e1zbNxs2o5yj7QmfabsATszYLcJs4i1HPiJx7mlEQtlOJj7MidpuRFl2x1kxG+JCid+ECIjhJOA9oSHvWGzpI2VjeNYykQ6cO5WwzEGz5JjKOStugcQMxxCAsIH1sPGSccRfaBZzukjmY7ZkTq7BirOI1ZT5VuC8m1z4TqQFYmsDYL7DFEjdMr5+uhE82jd1yVUNbzQBwGj0lGzmUYO98/ODsioeumf8AYgB5Z8/uxs9v5cUYm3bI79y6XASj8jrLI7Ku6HHWXy5PKhs5xvXyjAiWWYdaViNoA+JolvisgTG6M3N7qqwgZylaRYfhksNgjGHObujaUMsb7HSceK7LrdWRgLojeuMvaw5A2uFqyAuBwjMQxnJH/rWHK5vehuFptlicSFbHY41pgeyd6Ow4CEjzN96Hk8IkQznOOy7zbPV1nQxexu609iioyxXlPtFMbQHVRsbLQMQm4oGzTX2jr/ZZn9qruaznEDxuU4CwQAGStunbbl/13rL8vxjuC2CdsLCL/hktguhCz3fwcorxC6/d7Wa2+N9rwoboC2yHItxsK8ZXX86QC90iyMLgbGywdaoxjO2M4itY4YytUNucbR3ubYFhKEp3Rm3abllCV1oabulGaxlddLB34rFuytgfabtXC+2w2bSDwWNuMDyh7fcvR7Xi6Exbot9dF7P/AGP/AJRoq6xsYC74VGeMTxmo7PMBtlpvG/1lvqJn9q9LHmtJ3mWjZwjlwWzfl8vaWXVdhhytY5LI34Tx3m3YvEplt+xoX9+w7cPdW7K0CPyNp3LMTnZxcdhsWMMcLeV+I2hcRK2M7gM3NtWBhCF8Yc05m5DYP0g39IOXGO2B9puZcFDZssYeTvC3HdI3b3BQyAn0Wvt/FFb7nDnD2RtvWqL4vETzpGfqsvNkSpuyaxvHWOip9npjiAwfjKkfOIsWMtEDprTNnb6iR9RM/tUqQ9Fvfo8TG2ezrUvrL+xEnZrL6mFm0jV2TWzI9/4eSt1kow6A/qXvZxv27jqjJdUobfYs3rae+F5yu2rbjPqcdolBZkYZR5P4oyW7dZG0S9oGaP0HWMybVnCF8pYP2mxZQhOEIwjym9K9d2cAeQc3RULoQif/APYMzgoZ1d5geTvxUBRjMkQshD1EFn52rDnGC1XO5z3H4dXRCiomc95duYPmdAOSLfOgq0MUcEPajDJCqQAcpeol6iZ/avRbXnq0TllfKPsrwRZhHfNy8T3cDM+6rp7JT93fyltnfDG/8dgR39jrJ5DtQzhDfVjP8UbFsjGBwjaBZdavnbeLTsvavEbAfa33Ldv5Mf61+HD3W3HbGSy3Ye7/ADL+5hI3PPSW4WzwPKO42LZGOPtXD8QtUL5CdkdQ99ZQ8kMK0sLPX2e6C7gFVYwX1R1z0RpWN5lGOLp9kPMCOSdh+zzP7V6FmcTxOgRuvuNnt/RccuzHWEltN0QfpfySvnZZjvBkMlx3wj7Q2ATGaGXG2tYPxWnBHGN8Y3j2t3JW3tkbN5sXbDk3+zubYV4hfjsY5dcbr/aJ7WrrsBEJ31ttqshPCPtQjGtusQ6QNlmsP+hXG3CuRblVgs98vwu38lRshGcNt7dgX+TCycOrQPW1ogX1WfEVPRXp6U++R8Or3efWst7VD1s/9ihR0fRCnwWZ+UL916leJZSH/XvX9tvsXcq1X1r7YylKO7krxrSaLN4dasz/AH5XxWNVse8bBsxzWe+PxGfUt28auW+9W7L5wEosjirZRxAvh7G0BHbEw6RFnALO2+yODt9itO+RsPM2YqHGz3h7AyIUNkrhMO5PwFdsz7w9vfYpslCRlh6izz40jek5/wAA+eipF3MBdwEfODUcAo2yUZFYaKpMbo8fVa3qJn9qkBgB2KY2hR//AJ4/FcuJhOF924WFZwHCDbzO8GzJccI32w4a21WTj45XCbs1ZZhv+V+1fPcbZc4rtbsOWwYrfbOHxE7uSrD2/qMOcLFustNguPSdYUBlKeQuaIYG1QjHfDDmDYZrOfiJ/ELFtFn4R7NvtXFYStlzQeWNt66hha25p22qdF0T2qzYNA80edBax91gG95ieoaKtBSe9BnxH5R0jTHTcdHtC1vZplWdYOv1Gt6if7TWIGJA0TG0LZ2WWH8KH0tleNrrVPExFxgXQkOjVtUcb+At3xsyRz6pfV1u2SyOzH3R+oqdsb42bXDuXgGzJHswIj/S02r5x/m/CbFthMnv3m1q2jux3uas4WTNwN5zcJLd3C4uzaV3n+r5hYW2jpc520LCftNnGt36pWu2/V71Zv0x9VLqXLPOeeDNX56IMom4uLvhkO0+ZCzRA+Zim49SAeRGVvehaVY3D1E/UT/afSUfSGjWG0LacoD4d9pWf4ux+GSyNlkrOZtjNZRMcLSP6OtcJwtsvdO+tMLsnMx2jN16Md9kZVub0YLAnbAH8XcssBCzY3eLVstxNt34RYc1gcIRdwcf0obBaNnOPRKn8z8Ue1q64md9zq2eAXcYm/muMOCllftNlnNKtnrRx9vm9ErWo+ie1H1Gfm8nIk8AoMZ0Qfi1u/RGlhzGNHGff5tWaij5sVU7kXH9gn+0+kZ0ho1m7QvEeHE9SyFp2RvGzmqE87cPe6VxWWUI/l6R7EdsYbzdDo34rDcYbYu7oLgbLRq3DbFbOPiQtK2w4yOeJOtsRsxltN4GQ5StvjG62HK3DlBbTHdWdzdhE1kXcNci78Ctvn8TrnbMVtxlebwMhaFslERuzHSIVwjZLom8+8Frs6NuM/Vx0xlfAN30hhp8pSPdi4+ZBVrM+Fug7POrGKLLIefL1NZHFZrNZhZrxFZ9a8RXiK8RXiK8R+i8R+i8R+i8VvovFb6LxW+i8VvovFb6LxW+i8VvovFb6LxH6I4jiiCDESOjWbtXjb/VcsxYOGP4blnfthG+y16hD+5aP6wuu4fpHSvwUc79sL/w2Zq235xtO1eIeOVYtoxuhGwbTyV/aPJFw2nklC353ckbrHK7aDunI5XFRjO4Th7OO+wq6yFuTTYN5WMpQMLhzR7ylshsafZdtW4xlGPLxORuWuzod5Ux62Lx0if+MfMhRVRrjgD8tGfWvEV4ivEVUEc1WFYbYZevl6/JZLJZLJZLJZLJZaclkslkslkslkoKL2bV24C3/rcr45/Wy114uXfmMXbfdK3X3RA53TW7gYVsM3e1gtm73f6fzLKHVb33lbDh38FssjGYi0wrP24K6XGwc7aWrZK6ONg/GLVvs/Ebr/YWw32yJvPRUBdef6vm1boWGAMPe/EoCQAwiLG3742Ibtp5GJ95ekb0OMyrNvnQ8+ccGj85rdw0SDcZlBBBBBDV2lQ3rWP7NH1HiK8RXiK8RXiK8RXiK8R0eIrxFeIrxFeIrxFeI+brN2rZhb1buUsz28qw7X9SGEco3D2fwWkrZjH/APZsWUIbJR/r6lHDZL2bvwXrb47zfgFt3Xwu4o4ztuhW/phIL5zA3OPRwUzdDEC0zrb7ALkJxkIbw3+qPUrZgQhGAiG7OlYVyusZtu+QVth2Q1sTsBUrbxE+9c7Yv1S6eJOBWuzod5Ul8/Ux0S2y4qUecY7rB1BQVYxPmeIrxFRdBQVbO1T1U5t37JD9s1gvEI7LPzLvEo/iDf5cl4ujl7vOK7ZYR/o5q2wtzhzrOVgriMI37Pm9RPiP9z2L+8IwxPcjZCF0IWQnwaJhZ+9H+c+6cFt42YxzvaoRnZOJFhPtnbZBYf253H2Vsys5VzuEtq4ShZw6JNqlLGAldewK4C2WEG4dILWYfd7/AD4ed42yUNyrbPPrE5rqULMViL0BZwQvEbZf0pniMEMSMYzh9M1cHTzlwxTsW7Lx1f7XrDevlLO4T9q8r5Sy5s7rHL5Qun7A904qOd0MYexb7K2WxjmP9TYLILZsjC32fxWqP18cFPrt4E9kFCGqdhdOAsjsNq68TaTj7mCwvsxMLYy9n2VhC+ESZx5Uf5UNu210PaPRUdmV4wAwBmreDoYYNyjOKlAxE6pIuN1Xbeo27TCdXMYk3rWZjAx46JD1ftKPnyOiGa61KYy2JpslLsRES2+w5otbGrHuOaLRETJlHDapQIs4BZWW4z7vPn/smsN67xK/JuzFf3A4Vf5l/TCd9rBttit90ozh7IzF6+cgYbegPaXiGP8AV7OS8eMLF4IjxzwUOJjjGOOVpKjnGXT93Jt4U7YxlhXIsAwq3qPvR/PD+hZ/9nfI2FbPFg6IMiv6f/8An2zWcIX81v8AUCowuvEuTH296nR7DLepLtPmnzGsm48EX2SHWoj1FwXWsFuRCDsrFyqpjPhmiA2BxheVa6EQZOCB1RPv/so2ThfccR58/wDZJ7l4HdsvXyyFb2Rk7Ff07Pct5Wa27uxs+UPaXi6P9GOa/ue/bYxbF42454LbKXZqb7yoxvFm2B/yxsxUSeBhf7rfexVvWcNmeKhdDK5sfZjnarLzs5Rx2Zb18s4XhuYN66pysE4Vj3hWX5H2jn7vNX+Vfyp42aPG71NZjhv4aYHzpHzMVmjEVhKw7kMIAWqYFboomfxDBTqgWjfBFsBddC/b58/UwCOSOARwCOARwCdg3r+adg3r+adg3r+adg3r+adg3r+adg3r+adg3r+adg3r+afg3r+afg3r+afgzr+afg3r+afg3r+afg3r+afg3r+afgzr+afgzr+afgzr+afgzgfmn4M6/mn4M4H5pz3zhybo5Zrdn8srioXQhLox9i32upfL/qPfzXgXdH3uctguskI+wMay2eO5osOK8WLxHxbYF8rdkG773IHhDZhDMGRKhG6An7uzF2ahgCODc/xKzqB662fNUc4w2uzGC8W7h7xFua6pw32nPELrxlGE6uQFylR7+wI5KFycbgnARknYN4fVO93h9U/3eH1T8uCdl43p2Sdg3RYi1ocNidknZI5I5Io6QigZZq9Hxgm2lFxJ4rD8X0RbqjkuNv7Bd+167uj3rP5nPZcV8tkfZG3nL5f9B73vLdmPZzGL8VuhhOrfL3jaDuV2yUMbBv8AaUvE1mN4691yyhdAW5t2+0s8o7cPdItK3VQM6mzGKuh+GMsw49ijiY4+1DnYQuW/dyoW7BBTtyi2yy7OyBWXvQ/m24hb60BP/UGeElqUZtmZ7tEzo1N49V5RjhiJbvU5LA2zWSBsvRAheL9i1gTMHrQEZSz+ariO4qAhaLvW9WmP7XrP6I7V17q23AELsA/6fVdctvuCd3OX94SBy9/HFbocWfN0brl4GeGMfawVvjwEc/GPcF2bDnWPOsWdsrIRnyIXDNWZCyUWjBuLgsZ2bDhH54qMfajHIuhC3CHWtpibcb4bIWrqjuyGYFi7Q7Z75yN4UzsnC0zu9xajI21pw2aNY6NQ7R6uo9wz9TjJQJgo+zD6KIyU6tuF00RMwMLlbfG5ER/N9PWXrrnolt/bJ0mxuy+1XY3WE7Tdkt8WwjZWGGW1W8DswPu5rthPshjzFtlxGz95isuG/k/zLxduyWWHjbgpHsMYXyd76nfO3nTNj8Auy7+TLnIZHsP/AEF4Uc99uEcsF4sjkMrlPo9UP5oWLtln0vdKMR4gcOgvR0fS+ejWOj0Z3er5LsZcPVkeIqPiCbGWrLrU9WZuuitbCCjlDP1cArvEFHRE7P2z/M/DsUj19s+4K3YIytGWGYXbcIw2Y7Lll4wj/NuXi/Zk83HBeB3fzq3x4Cy8Yn3sF2SjOLTfDGa8Rsn7ZvC75fLAdqjfGM8K0L8gLxeth2ybv903BeDbPDJdgtsEBf701232v2+6ULxYJ4t90YzXo24191h0a2j0Z3errUR93W8bvU7tE5yU8VGOjNOx9XE7FLbLcNEAf22VJ+FW5ZzE/GxdxjOUfaE78F1YRMIi7M3rZ1QhP8mS29cZ9U/ZNwWfgdwvx0ZXjOcetyjvvFrrQauErQt98IQG3Z7u9bXVs+XCFmEFvjD8UOyrfitm32RGWqLwsiI73XRGS3wh0RbPPNXxhMa38sMFZYMJyaNvOXom28rhbono9Gdnq4y8TVUkYeqjejZBblORWC8Y+qgFAQvKnkJaLt/7bJ+7sVu/MjIY5rdDCdWV2MVlCGE4S9nNdzv+3/VeNt8cLyLl3GOOB7gNFll0LuHzWO/G06n/AGVvEwltdHqgrL62Eq9lnNWcbJ7PlhevG24DO0YLbxtEbXKOe2y+Lfqr5yqa17OjisrbrnnE4L0f49kVNT4aPRu2eYfUa8ecI+rjJb4LJQUfVROztVpwkNumM/22T9oXfZaJTDcc1us2Nz24hboT6IgZnHLBeLTGFoxVvdO72MY+0u+zPDGXDR4xvgTcpbiMBL2XHCdq4XRkG/2uxW+Mpyr2SPNGavje3WNxhLV/mUPdtzcw5G9ZXzAuOavtzPJx3xW0QImbW2WDBQyxhOXZAm2Fi9COk3OFth0TGj0btnrKzAeae31WfmGGHnz0wEVAK7Dt0S2/t0n7t+S8DMewrPwn6xvdkvn2zOfurv7vy5XLwLpWNzzXgdgzjbolcf0/3UxnLWv1uS4XLu5XtZEYYFTI3Gt/PgMFZuETaZQq9HNd8rxH2T7sL14uFsJ3kFX8DDKUBxCgT7M4c51okcluhOEbOibzG5eh/EMurRYrFqO6PrK4LcR6yCjb6qKsG9cGz+WmJ2S/buXu27l3bujmrPFmPvKzOEMTb1nFcIkcbthvK+WQGGzEq3xLxyVJd3bLorrjb7UK3Kjh1ruGFbJ2GUF1cG+67FbrBPdJ2XNXDPVt9nEmFis7+4bOtcfzfRq8NnKMo44LYMrWW3HnL0OxwttFtuizRqnYfVwOiDncePqj6yAirTipQxme7RAE/t/K2dhVmVIVJ3Sipu6KnR9HuXI6TlIYwd+XRstbbtw71lGRkbbTfZVW+6POhdgCLip9XVyTnmtwBvsFsnc7JeOUR0jZsK8Z2crBeLMd5Uc79SUIm3ZisIdlGZ5+0vQ5Vmwv0WaNU7D6uw6I1Tu9YNA8+KsbirvEAoknRYN/mRUP2r9JX6/kv8xa20L/AC+CsypF/wDsCkp79phC/LJRgLRLozjycz2qO8TjhbrfRfKcpSlDA3FWTN4B38mHev7cqErDdZYV45XXYrevEWCMe4KOJs2WmbQo59+GQdG5eh/E2dnHPRYrFLd6uWiLSPPiPXxmpdLsGmJJx7P2/W/CVJ249Sm7MLkcOpdTly8iCpnp9rVLgv8A7FEv8QkuRnPomFwUjlKGOM7lPOGyM79i5OBhDvlcvG3ISX0jvMmjwFjlyjbK0Z+6uvGQMMvZM16IdIW2yjbolv0S9THTA6IHzoeugIYq4bFE7JDRLbL1mx1+HWmi0qrOyNhsVURM42K72s1gZ3o/W1OPiCN/CKkImGagNtgtKqoxhC5RMMlbIqWd0+1Sx2KQzRlIoxhBa56K5XRatYdFSGR71y1ys29i/k7FLeF/9hX+Z4uU27O5SO35KZyC5HRUmC4h0VIXREYXyztvWy3bGQ+Er5G/c/5hQbRjadkP7qCkpLv0EoqOjK3RxwUor2oWlVbcVCqY6IlufcjZ4grbZZIYyFq1Q4KqgPatQsU4YGCuhNGyrrbUasuVh3I3N70cD4v8+J2SXKduGmLtnq8ii38V+WFyjISyE4ovI7E50NWQutUboz2kKcbZ7Ci0E21kYQEo32KQa2PC1EmAEOKJeJbfBRrDVszRDnez1rlG042Bapv8XBGoBvM+1ANx3yRdVFxhkokQG+5a/wDZax6K/QFyNikdq5WxfoXYztVm5cnpu71Kk39i1hs7lL8XeuWoHYz5KQ/hk8VAjJnatRo51uwzUCfdZ2qdGMGqxSClogStac5q4qGS+SrNssnmsF1yit0fZEyo6pJhsRdI+zHqQIJ4bdGpsmhJwnG8xUDKM4maDaosD7d6qu1jWEL1PyZG/b8lWjI1my67F5RvJJcTCZ8b0JuvvnHqUg4Nh1QChrCY5RB7UWxcIQN0bFrQ54xmMckA7GLRuh51VqqtUIN5vbogI4erAM1fOeFyjbNTMGX7+KqhzsVViZBVWwGd8yi1sJWWjBRqizYpiIsh4gjWxh1Il1sBtUza4XC21TJMDVEFacUQ0jNauyz6rVdmuSICMgou6MuCAfZEqJdJFsxIqINYAQF0lWsHJVayxDnI2got5WU9i5O0dU1/l7HFapzJ7YLW3KTdq5fi5TPQ71I/wwOKhX2Adqm0YdwX+b+Edi9IOj/MVDzLN+iG+9FpgqpgrWq6PBQDheES2teOwqIjGy3YpjVESoOjIZw4qDjCzQTFplPsUQYmYRMCDdOAuCNWEgHW48VBk5zuPamcoGrlmhRuiYurZSVR1kKwkEJtJ29yto/zWW2IEGtwBsh800+wI3WoEQJEZGWPmxKidnapx5s9Ng38PVy2qC1YWz8ZqqA2I2qye+5CQjVytQ1dYzykhEH+yrPjZBCscr3IEmcp3wQ1sLMFKO6NiFQ59yAa2w4pgG3Bx7FVAEfpFDk2T8Fa2EJzywWtsFgKmYXeJK2/Q29WgIVbPqpCd0VV5NYJwwIzVZsRzT8lA9Fikzd81ylyFI5u71/mbAFy/wAAX+ZtHctfce1SP8QfqWu3o/zFCw9SEDpE8YlZ2KUVIHcVYRYe1Qn4ip+LUKxiLkZiG9AtMp4xsQInKF6bK2OdigAd2idaKZWEo1kA8jEWoN1TAxz8TQFZkzH2YoRLIH3ozIQLYOc4RsnDZcg7ULjEG29NcNW0SiZqNpvm4A8NirVXiwQiMkDrAEC3AIargLbZy82qIqAiVKGMzprEnxAeZPz7AGjExxUTDWnh3KLg0SusUSBYBbKxVoQLs9qFeQu60SSI2C7sUXdGEhiokkmw3ouBNsTgLtqg2PO2XLUE4xmvRjNNEG1t9vVBDVETtN4uktcTnsRrA3ZjuRrTw2qc7dii4zuMFbVMT2DFauiEYbFmoC9diluXcjRmQkbVWjG+CBhA2K3Ndi5M81bm4Lrf2KIPvP8AHYtfd3qIGdIO1TZfq/zFQt/uhHdipaOUM1HaUDKBsURYtW+MUZGENihNAVTepmdqgTAf2U7JI2InRFspm0JzhVFxyuXlZ21BMWSCFIKzBVqmMr17YnidikKW+M4G65WGIBssRa5rgfdjtvXkiZmBmJW/2VV3K5Y/uqpque+wVUWRnKwRvRDiATUwt8yKjAb1OHHcomOiA6uPq5yuXtEk4wkiBWEookmPykFE2gw6iqztYlxwCaTzdtu5AkwkN6td8+pNq3W2eMkIWC2QnehZb72AyCyuFniKgQNZRdaLdoWsI7gb/kiHCA4G1VnTmVMmyC5QgbLVEugLkZ5KWmSkpeYC2qZEQtVvSVuxAQTAqtkU18BYZ71yN57VN27qClR9KKlR7D2qIjGy1XqSsWtvKhG5AOV05qXVBTgRA2bM0YlpMLlGXAZoOFswq08LUJOzQiCLDaL5IB9suKZGcgYuE4SQY/lbDkcsVVeRGRnZVRa7VHgo1oAAS1gMr0WkB0/khRmqWyfnYhWhCLRKMZzQc2DqxgTYbIdqa+HKtgBjntTXCrNs4YwCa8HnAGBs8BOaCQYmURhFRGqSYShl5kAr8VInnS3aYuhze0+pkoBR327FEX5KrPlHqQaIkTdFODLnX4wRDcITgG9pRhENtvTgwmEN3cgGSBshsKk0VYRhIiXzRc4SBq7nDJa0NkjZDNRMGieXzVQ2XSnFVnNEJbe8IV2+3b4KaHgkQt3ptYkRs4qbqoMMbIoe0DElQLvdv8SQg/O+CZrGFl00NZ0LMbEJykpb90Nq1br/AOybAWLVtxUt3BbZraoWSWZQ0Wrii3law61RwtN9yoxeTVjcvKTukBkpGCkTgpKxTjYIwKhVOXYgdaMIrk61xU4xiCm1qxEYiwqqRMgGFomvSwjNQebCL6s9yZNla2UbNiZAsM3zJ2ixB9HVgA6MiUHMIDBEWwt4qLBq8k3YFSrButvj9FENMIkW44zVeB7Fq14zq1UdV3O8TTTPXNllnYqOIfB1WY2lNrNeDUBtFv0Ta9atK3egNaMIzhhFeTIMN90kxpjra3CO5CiJFzrLzG8aYq7FXYqLshIaITXX6m7RbCJjco8m7dBQhHYBaoQTmtFWsW5i1QbAtgcAIItaNgEV7Nd3couHiKm0CacHNlA7U4vAh1p1eB2wtG9Gtq2AQic0fKY3QyTa7iD3TU3Y5rVfD6IVO0qUYxcZblKzdjihOMjISEoKTrp4XKNnsiW+9Cq7apRVVs7CoNG9aoUvwqzdcuvetuCBxs03rHDQbr1I2IG29RFWNq1b9ikrFy9qMLtXvQqzsii5lxUWmw34TRIDjY3jNDVvhfDFcl8PFyDZi85yRAD9m9QLSbXQjhJeTdEiANkLJzKg6zlzt1vEVVeWxJAz70WkzcdspqoTdGMb0TES2GCMA2y3KWSjIyGeCmWujHDEXJpBo7cpoGXJLbJYKMNadsO9Tc2tEZ9iYKzY6uyWxRaQDNossmoyiS4ZSGOmAUTFQrO3DTYMZ7h5kfUCNkDlNVgYWmAhZ4zRcZyDbLka8K1a/FOrABpn1qYE7bITknufyTC9Or2DfdFFzjV1gBhGG9Ri6EA2/uVr3bhGEe9HXMBDASHFWnw7cjFxga0RABVq1bhBHWg0NzM5rlxnvhxRLbYAXDAp1Qr0Z29idUwjPcpGcMu9CqSXHcoMMpHitQ7dyFUbOtejFyi0W9yIaJ3G5WbLFGGxO79kFHervM71cpgSleVdZuUMfooGclB1uxS0Qe4ZnYnDVsQ5Jjfv2K4yU4VbutcpplLrRLSLI8MlXMISMv7I0gIgYAQlkgWmd1mxBw2cfBQLRGwOntXt7rcU0VZXzxlmp2xjOZwzUKpAqxtzVY14iCDSCPa6obUBZYUJOjDtgg2wxNm4qrrB4nI771Agh1u+xclzKv8AZQdXEIX3wKqO8o022wCg6QkcoT0ROiAVjeb26azid24efDbpkhhEotAq3WqUTuwahbCsRzu5AkmqSboXKbjYZQh1pxJMzwqqsa0/ruRbWcSYHK1Ridb3YckDNFxc8WbLZLUjCNac5koVTWbbHOG5ACfK2ICJMiTHZuR1jE7ALAmhpjf4gmhlaEzb8kyrhG61WmtdYPFyb5M68Mr1qcpx2SQLZmy75qLZEA3zuwQqxmbd6BYY2bbNqFQTz/sm1BONp+i1JuFsoLVjtUBbbgpC69RAn81ZNRWa2K2KmVNTKmZqJkbuxTBuXJMeFqlog+NygYiQPcjEGyVoWsLZiWxRfK5axtdBaxOrchWM4QMlVfGMjhIgoViIwDsscUGvIlAG6S1nVqsHT2JsS0wqlCq9pdx7UCyqYR9neq4Ity7EJyNUWxAMEGxD3CFgxhsgmgOZEiNkQhAtJihPFTLTYgWgZwaZxTgapq1RLahrC6yy5VSGV54D+yDpHlRnHGOmJ2Kceb26YDq4qqNnqoQAEUCYHWnNYbty9kC3goysiZHZ2KDLSI25qDLervVWjvl4gqrIh1xMUAzD3jeVCjBJMbhiFCjthvVRm7cnMZc0m62Sg2yIxsihUbH2vG5FtHdCMt18UWt7Ni1BGMxACHWixvJdGHtZqDdYdyIZMRv4ppbYbwqrNa0di1ICC1ZiEDJSMRfHbuQa3kgTvvUo86xaosnFaoijDdPYiA2xGG/ipcVK29GdiM7Le1FYqcjb3ImChBRq2fRWKwQzUtFo5pRq2xsKdVG2MlYYGE4zT5EC47U6AuHJOPFcgm6SgWuqz+XUoODg2rKUox3oCULYGM4wU2uqWi3NOrXQMNkkWvBLZDvzUHtpA0bTiqRriINmax5qeHOiIRMZdSeXRBhjGHgqq+tbmFNpjLioFsE5mtKahkVANnaZogxaRMiWCeDdA5p0azSImUr8U92uCDKBGUVFQCqhQEMZnTF0Ob2n1U1WNkhMlRJANl6jIWNt3oVoCtjGNykADA5hWQntxF6NUCEL537lqwmYSI2p9zcAJiSMGiRrGrDttUYQLbYQRwjrXdyPNdDxeg2BDZ4C2KdDk7RWTqvsgnfDYjVAAh+JaoaOAdGfyRq42RAOCNQQ1oic7Fq+yJTnHcjVg0ThaEakhOAG3NGqBLtTquEI70SI4CU7MSnOF0J2u61qR1YztmosAjmiWgyF2xasbbRanVRq4+CiQJWeIowEuT3LjGatCKM1MqBumrFZKS1b1ZJSE1KNwzxUtBLnwtBUazxIIPa6DgHWwhbDBVmwiZTxib0XNhGZTi0ivOSc5pvq2ytVZpM4MPGPyRIMHECE81XA1xERuv2qLDrazZw2IObygYDtTqknB09UQVajhEymBCM0PJWOiNaOeCc5oc10cbpJxDTGsAosMr4ouEhYi/D5KsIdarCGF6dZDetWqvKtcBRmGXzXJozq3mUZpzHOhYThcr1E7FEw3qsSdMZ4z9VarvoFVtfDOt9E20VjmBPeSgXOMxjcQi53Kss+qJdIyaLO7FF74GQG/ijqxdfd2kprntmNW/xFCLRN0DHaU4uDW4xJ2Yo1hEyiY3IarRGZjkMkCQAM7YQRhYJXRszK5IAifHUE6QiOOCcyF8ZQEUb6s8yZqTRG2XBasjjaYBPLIwaMI91ycGQlIa16c2jEXQwCdVJhWwjKWSeRENgTnCSpKsC3rRLZiwmJT5iAELyUYG6dttY/JGq6LYzxTqs22Xo6zTbgiBCHWjF2rFTdFTMrgjWst7kYx71CB+tqMtVOhZmnEIwPzRIunxToGAuUtGs6fKNgVs5WIRMxLHtRaeUB1oxAznsFygTOxxnenNeRWjdtintIBdaJxMI8E4mrSGqMAYlOo6SFaXs55pzXugQYGV0YoMpDGMp8U8P1RLM1VUpJUZBtmbsYp7XQcw8okEG5VXOiyqDZXNxshsRoy7XELoTiqko23o0ZIM08O5Mint9mCewkhonBUjTNifEGonkx1amZ7E+sXashI96pJEAHnEFQCgFBvS7NMoc7sHq9VEQrCrfH53INieVhqh0U6dbUu2dyGs4xgb4S22JsOVbioVzXBzgb0SS7lCzaplxAyrdwQiYgCcLLSiXRiAbvaTnOdMmAmeTuTnP1hXhdWimB2sAIXNNaag+Jo8gIzib1GkEQHGz3duaMefdbYAiA2MDOECIhQe0i0RvlOSDSLncT9FydXrPBRAn+H5lCrielLcESByiboWRWrNk4Yp7WNgZWShYnto5Am/HwUfJkzO212a1faMLgohzYGI2qRn/bBSIjaZfJGsPb7JZImNpJMSrYCOeCjHPqgplT+U0+MTKMk4OnG2CNsMrE4YzKMD1owJhBGAkpbOtOG7NW6IOIIwRaRGEDfGSqvqlv9k+jP+XE8VrckCHKzVVxsMdaHNUIGpItFt8EGzDboyci1opPJ2795XoxqVw2cYxgNiMA9jKsbYOxskn+TbVaA6MyXTRqg2Q5rsb0ao17O/uQLc2mAdGG9MIaS0mBhEGsJ8UINPk4SkBgrDVKAg5t1oRLb42yQpGiJhFOLYG6Sc4QAsUW2GWaGqPRi+B1jv7lVJo9XG8iOG5PhrANqmGqIg4zUTBXYqJ2aazjlIaYk5eorSUph0zZaV7rhwBWrAyEZj5lNhHypAOA8BUYAMY/JGBgQ0QlLgnOBbqj3jadgUnRvshlfFezZGMrXeCohzjCdrORCCMHQAl4tVUmMGmELbVVpQIRwUKQTBJNkZqYFp6gNyJcJt/CMNq9I2RWuLO5uabGOE57e1FzqsL7YyG1EgQ5PtQCaRqgnDfiVBsAAYVR9EC2MDHbDcq9HAthCQnNajYMdxAEk4hwLIzjb1KDaoFkScAU7XFWyZMavFHXiJ2f2RaXRiTnCQU3S3lTdO4RUC4VjZZ3qbkKzoFawMbZIgiExFG7HtWDjWCM5mPWqzc+tStKtib1b/ZAuVu3RZC0yUQx0I3b81yXiJFkjGdy1pNs5c+5Rqmo3cYyzRk+RsbsOzBPexhIFVhxTn0QPk2GButaU4sIgD2uHFCo46s7QIyF+SFWDRGJsJu2qjdFusx8AQDHs715RpGq7KEHprawcXEOGPJQYCC40hfqBFsQJ872YEImIytjdkqUOIcRbKYAgnxeDAF1hTp11Vd/lStUXwqXRUXg1attaJkmNLHhzSHYmW1VXVxU1TGWO1GNcGM4mJkCi4c2B2VleoRduGmq0nhvUPVTWtbCGCEZEb5qIgCRO5DkxjkJuO1WRllcgZBk8vqmwINZsbTJN8nrTwMOpejk9glYImG9FsZiNpv605wMWg+9YiWug0QjxXKeZ3btii5wrEGrOAuQL6seTPfuQDjrAwwEztQNJAWAb7Vr8sQhPHrUXk160MFF/KJaNZV3yOrbDEok8ps4XQgjq1THbjjBNsrn64rVFtkjioCHtC6XWtURjWPJnYMVbHEgDLFSfFxhGOeS5WtBsjOZioGkiZRA4rWdbDsXsgYuMe9EuJsl14Ba182xdPxatfOrMRsUHGYgRcZlFprS2RiU7AWgIhp64IwujmnObIJ0BISlOSNm8k5p0XTEpl0Yo1i2WJJKg6EBrdihNjr54KlENUGN8ZJ1SJmAbRBPqCFVwZN0LRgiW6tvtCM06lZ7D3W2wePmosrNESJmJ9nxciaNxqudlG7HFOfRkVI1YWShDJNLCL3TkTCNqfANNWBjExmI4f2Ra4t1iOTDYoUs/KBshygBDBPa8BwNYXiHJu1l5N1erbGVaMOCq0uoy1ta2AzjFNong1mzsa2LqqApJ1S108Dbfkha0iDDPyYAhnNNNRwPlY8msDLGKEbQIYe0coyTSxpBAJMIOiqojyYyv/mMOCJ5DwIGcn2cexeWbyqMkG2BVcAG1ptDZCN2xVgGktlGGrLtmqwLXuMocnVh2o68XmR1RKzOGixuGms4Nwn6uAJ8SVYF1oTKkaog24jvQjyINhyhIqbmzIviO02oOcJGV0UGwqVm4xmOCNUQg/8AKVATpAMhM7sU4NrEwjiEapieFg+a1C5xibY7EKus66OU02ry/nuQc3lCZjAy43oOriPJlIQ68EHOdCYGCAdDkGG1NL4RLo7k6vVhDO5GvVNYA23xTq4sEBxVSdaP1yUwbY2Zq4ER5O8+LUxreXPgtXlJ0OWJjinXubfmn2aurO1PJdMJ2QEZbcU6saxs61Axf/cqDoWRRrCBtlaiHCYlK1ckt1pw2ot5QkDcjCcNiBEYme3qT3iNSOCdCNWTScioRnGNwEbUYmIdZZZFGIgKov3otNYNT9WCdUhq45lOe2GqDci4EOhOWFnUnFpDHCM5EdUU7/LrNaSJSj1pwc5sQxwnjMdygXMMRbMWEosMOdK2RC8marmkRvrRt7UGVq7i8EasNXwU3VpNYulD3bkA6sC4xd/covILA/fZO+aFVrmvIsDpwj1oNa0tjRgA1yJ9SFIwVXOdAxLXHvXlWtdKDTjVIA2XIUrG61RzLNW2+22CpaVkPKDU/DLpJr2Va1d4m0iLbbk6kbKk8mW2anFOcw0dfyn8QARdlOxMbqOc9j4GtHXaCg2bqQa8rIR42JraQelgyfsdUVVdF1KA2Mje7fYiHas6NwtlCLbfF6Y5sRSsjabuqMU9prAyM3Y7lPYo6Yxdj6uAgg1ntOwaBepGux0OJirXGIjYcB800tJDaxPvTKDnQAqQxNnjFQeI0lmAieOaaXAT4dSq2Pq5Bg7ULjZ7VqLQG2ZYokYznrX7E7FtkmwsQa0WRIw7Aj5M2AmZME1oiSICJskm2w5XUgC7HOaIrznfmnVnEukL0XP9qrfmg8gi4zJkuSCY7oW4KDgeSGm24bE0gGFXMlRZKHeUKgEp74HElGq0SA94x6k/WAgfeuijF1YDId65ct2WKc6JNUbfkjXMxZGIK141hmeVwC1mQqoh4iIxMqqdLVEIizNWSsIARgdUbjOKi2EphGEgI5lOAnG2CIc4AXgotfhWmVWc0EGE1CBaLCiW2ViJiaJbY4R7MVESGzcjEtgIzjF2Km4GjvgATgtc8kb7Ea+u0HWJ+iPlHT94HI2BFtLIBwNm+2xVaWLaN0JETsxVJERY0gRIhZxQgItgL5mMUW0QqACrMzkd6dSM5TKzbIdlZPLXTbWHJEe9eVa5lVsYRvMTtVI5prCqOTPXKawuo3wc14tEo/2T6M1K1CW2wPtJ1G7VDWwMH13HqT6zqImicwW1Y35Klr8pkBK90rtipWuqGjAFrtbVgb8U4OJjRxu2dFPZ6RpoyNtXWu3pxAc0sjY6Htb1SkUfpWwPLBEfh3KIgC2Hsh01XbDVJDo8qH0CbCr5NgNxEARvVYubeLL+tau3Tqnh5s/PgjybpqrRBwti2a8m0wuEVWMDluioNxjOe1VHY1jfkovfdCcs+tVIQx7VOjkLVWpwwgVcENUwH9kZHG1RBk2WS1RmAoAyCLWAjxFVa8FGsUK1aFsOtQc7poExM6veqz2E4EqbJRnHeg6bhGAijBoxkqjJLVzJhG+EVFz2wEI9q13+6YJrYnJa7PetWtHAKq5q5Jv+agZXKADthUSRhDrK1XGfJUKL8IPFACrtUMceKi508lCkDcVUqkXyUQclGjc6dYC1VmzjZjigHDKt1ICk61rPygeKDXNhwuUHiEpB29azcmKPw7FFom6bg225A1NZ3tX4Jho618Ldqb5NwnKN+CqCWBTpz5IiE5zqpMRFQe8iVUgD8Squxg4NnmgXxgJXXTKaH1oTc2J3IQaYCJkc1WbRuGoTEGrKIzVG+oSwRHiaDi2QE6sQLimQcKghGENl+1QY4VRAIt+EmaeAwRth1qBe4NaC1zW2Wg4qv5S7WhJA+UMIEXhf/9oACAECEwM/Av8ADHnp47Hnq4kxs46cE9LKple1Jx6E7P79COlLtkyz77WTPv0ppm3Lsyq5+PyZW1/PTzdl2ZVUZ2uvTlmbcuzK7JkyRZl2ZW48U1sg8HgXFYPHS8WztMmazto2ud6x+tuX0dTQzvM14EzyPToRTU0M76SESTB9r22T7U1PyZtyvimfp14uyRZHQgmmp+TNcOmfoamV8GbIM0yr5Itk+TA0NMU9HSmGfkzXDp/0amV8Gl+VazAzHuf0/pP6lZxX+ojp4M/LM11MU1Mr4MGLsqs24PGBLSqEIQqq1CFXP1M11poamV8Uw+nJFMH9fifS3OlMiVMnHQYzQza6MfI+R8jHyMY+R8j5HyTr9TJxXKm2aTTAuhFc/BnZqKo9bZ9yFqM4FRdPUzs5IxY5/VPxZAmq4OejPizO3z0VoTSLU2qTrXG4T9yP1eHfxSdL4J68Hp1UL9SmvItCBUgi6SK59up/VgjoQTYoH8V16sipHUhbROsUl2/pVY6uFR/qI1exgjcyhLUjQnq5smyL29/lVd0Wz1ddn/prG4199npu9feyHXD8DGS+jhbvX3df2j/VWJ81/d2TX3df23/6cadk/Lr+3tMCIPAv0wJ/pwe1fY9vr0WMYxjGMX+4X+48nmjGMYx9F+54R4Q/4huk0VPAlRqiYuBToLgXAuBCsW6f6dDlfQ4dfAzzTO8npoj1ujpz6UVkdNj4HwPgfA+BjGMYxjHwMYxjGMYxjGPoYGMYx9snt2B9rnsCF3nHbtP7ggntcVj/AIKY+yx2lIxbj27RgxbDufYsGLYfaMGLsLs+LpNV2fF8O5j7Bg1ux2bBg1uk13X4pjp63w7vO/iDBrudLfxd+ejg17D+epgzb99tpZp1sbvUimldK6mtyrgzbG183aGlNTzbpTWnnsWhp7mt+uy//9oACAEDEwM/Av8ADHi/PZ/23ZM7qeri/I+1wrJXZcW4VmHucbHCsw+y4twrMPcY6uLcKzD307aNxG2naY7bp27Tt2mx13unRwYvw97p0cdDDujtGHRWrb4s06mHdJxuMdBcCuQhCpgaRBgnO/fRYyHSaR2qaQPtsme3Oe15sntU2R/aCW2kjZaVgb6/7d3ps8bvTZ4dZ3Gmz13elZtQiOjnd6VyRdjqKxbTSub8Psmlf3XY7PJD6M0QqIQhCEKj4HweDweBCEIQuirotdE6MY4GMdzHuZ7jPX80j12SEIQhCEIQhCEIQhCEIQhCELoZEIQhf4J0L+zp/wCFI/4v0/8An7//xAAuEAABAwMCBQUBAQEBAQADAAABABEhMUFRYXEQgZGh8CCxwdHh8TBAUGBwgJD/2gAIAQEAAz8h/wD5IMd//wBchOVSwYOXX832vO+V+AtfrttNhn0/S/EX7U/EX4i/EX4S/SF+kL9v2X4y/GX4y/GX4y/EX4y/H+kPzofi4M/Wg/IvL9Lw/S/h+l/L9LV0oPyfSHDGfpTzPlfgCfgJ+AmKXh++Dy668f2vH9rz/aw6H2vwE/AT8QT8yPM+V5HyvA+V+r7L9KfpT9KfpT9P2Q/VB+ZBYPzIfm4M/T9l5HyvI+V/H9/793w/+c8dv/xxvAuP/j5/18C//wA51vv/APOdb/8AOOs9/wD5ydnuH/6KJRv9v/ziN/tH/ggneBk6uMYgfb/IRcNGSyy6ll1LLqWfWsupZ9Sz6ln1LPy2WfUs+r8WfX+LPrWfX+L9qz6/xZ9az61+hZ9ay6ln1L9Cz61n1L9H4sur8X7Sv0FftK/SsupZ9X/oaRuE8MYDAKvIz/kwcoPowWHp9Fh6fRH+D4VcWZYdl+tfrWHv9L+B+kP4+iGot3HDv0r9n4v2n6X9v0vK+F4Xx6KUp5Xwv7fpf2/S/afpfs/F+z8X9v0v7fpeV8cAfgV+JX5vp/1Jk7b5QQTI3WXusvdfwK/mV4FYe6wrCv3ccQjAJwEt65G4T6hndPlfqD4svvkfRIKkDyCRpIcvQ8sD3BaOgQsw5BAiTtkOtCfm/SqADYB8IfO7rwnuv6/biOjosHRYkxCZBAuErg8AGnRCKdF/BOp0LDo4QNkfw4D+C0dEBjohp0W1f+tdhCmJNgN0MDoEMDoEMDoEMDoEMDoEMDoF+B9L8D6X4H0vxPpfmfSYAEhAay9n+GC+vl1hkM/MPR08sTEH+Qvxs7O7HDCvKEBAYAwCKDkwzQECW5NPF3E6D8MU7gDIkBhbKXyWD9J0hfgArFG9Ey1UMBDCc3xwQogncAFkOA8CyQe6hBReBQ/zn0Ts+HpAcmAHJ2ElGOwNXmUNAHwkfKITyDzPpXU93+nc9l2j0ukCGASHPMcWFEkGlrn5LZ9al8qf9kvvIIXDntnIEdDwAwgiD4JMck7J9YJ5HdlHrcV9D2+EBMvJW3dbU14aKVrhM3BlXhVBjxK0T8J5cAoUhB+EhDmqIACMNx/rKnb7hxpY0HsIap3Z7AoLicGXEMJRMgYwKYDEveY0R2YdDq4zk90AcAaF+Hi1T8Akwg9HRWh04BgLAIYHRDAXaeHc9k3I+fSQGASDuBAFIWc/rhFp7CHWC61WXZyhIiaL6wRu5DLAU2sIPuUZRRmkd1giEDlsb/W6ZrkSDu5p7AJvNi/HHoO3BHbjMkKKqqUlCVPBXhqghLKPxHRO30obTChbI6cuO3RRZBwIpRUogTTN0Md1TfgaQb3Q0wKKj0NDcHUf5VVVKnb7hxaFpnrI7Hga2QknWDWhgbFp2CarjCDwWIURAlxwXRXCNVYBJPREqbdxgoPDg9tFO/5cQBSPsEDITHbsj/Aa7IDB+uAUU/M+OE7nsu17n0v5F/kpyO5xt+vfgT0QMBAI5gsgCGgh6vlYYFgZJ0ZlwU0+6SXDqnQjSCZBSSDAADRGBSRgMC1hXaiLwOCYhYZUMw2iesx5X+46OL+U3ADbODqgbPCUXCEKsL2T3TypPLj0UhBb8KRx0ToKUHoqcdFlCxGzyoVQ+2LntOv+UKqn0AYB4nPTkgzvL00Q5EEkWliWwgIRjubqgcj80E2qdNgAio7M9g7qwBt93REps7uiRiXIubeYTMHBKpDu5X99OHSPoEH6AeqgEgkMdxQoERfRr3HuOicxNES+jWnqT6/ITSE4KEVFPxAMRWvLeyNIcXcrNU0QLAdHWCPFlrRv+HTTmCG2FMtFXOJj2CYwzmD80AYvZ1+uijh20vC7kR5prOIiJq/TBrNAWqQON0hnUgSWqmNLIMaCooGq+AnfIZPME+mgctBGIRcVC1K+ETd2WqZM8vCawunNOHYjMlF00uy1unUKKplpZaJ+BhURdPwiqda99lJMHZ8EYPQKcMg8o/f+MKCp4piCoIOQ4dUGwITAU8gbnArnkojFkIBofUp+AEz2INWqeAseUY+iJAkQRhEszPhwgYEkpag5qKS9XthkUGJDgggi4VqmAczqCDzRcx8CNkB5RoVBAuBF3Wc4TODHyPQ1zCLREB2vY6tp0RZWNRXbKcmqAeoH8sh8fsvL+F5/wvJ+F5vwvJ+EIKA5M46KV+BD9GyAJcB1H5dMbA9jfKEmJy9T3jdAyRpLP3qgWrA/c4bkjUuiZ+9w1m7QBMAF7GTQiwdygxiB3PYZGp29DbkcI5RDCkQtOyGG5KCGNrIYQwnssEH68DgrSyiim1VKlboJi/ZBhtZQs4QllTZVmyhe6p+KkPzCk8BgcDTwam5aeS2qAQRT2/dMPUG5Ad0uR/xhQVKjztwcEZBB2KDPRwgsAMBGrI55DKxHlk48OgVHZOxbNXGbcn4ThUEjogSIDQKUbumbbUhMLIBY80yOMQNwE9gEDgLSFu8E10Oi+pBDFxsnAFrIx5rjJQUD1IkOJFAuJupRESaiuqjUnmWV5AImbyECHJ0BcAG7RUREBAihihhwxtQ0J2jcUtuU7xhAOZTqvhM267oR8UahUbEJgiwINzLfiEpLgm7sXpqmdsFFaA4qPlIKhQgEGTpCYoAEbil/S2pwSKCHecJn3CqX/EM91FeLLZBUUwqJgve5V5J2jKA/iayA6IG1kIQFxwcVCBxRM1KqeFfrgGUAMDEIeGDdso1JIeVwj/GFClRu+HoNibnCNUidSShdKKtQRRjVTgpLjOxJi0ySgcuqamHQvKNDCjnjfKld6jV7RUeYuYjOA9mRCoQuYYUAhXGlJz8loD2qgBFWJHJV+FhylmSCC5wGgfZqgkFPEsEIggTYgQRY3HVOShqBJbQIKcIegS7YsV16IAE4EOoHwAi24Nw53RdV8KG44MsQ5V7I9ObV9gfksAjGgZIO6BZwAXPh/wAGRiAZEapNzKfAWjB/CiaDF4MTAdG9LDy3gyUewUFFjoygKOM8lPAcZpxqhVq8K8uHshVMqI5IpZHgw5+7jCcktScs+z1QJe3BVe6JQuG97Bzeo37gFXV/gjhK6nsHAF5DCpeAp1vYthdciYJEEggsRz4ChgO+XMZCLhEGRqmYjRMcJgy6P2Kbfe5Tpt5Ixv8AKrxCcic2TNnAdCiIuRmZ8uyfULT5hV5qNnsCNGrimAoVbPF7nknmZSLEumVt6oDcotGCD0N0QGg2AcwjY4c0At0K634Udx7HjGLE31XCbIYIuwNuVOSauqDqR8OjWyXIASHyEDtL2S3UXQeJM7AN6XcZAJ+YAVnugM0Jn0CCgToXe8Sib4LRnw60eN1CRKYFyK/oRj7EBz7r+lO+1OEd6/tV3RKx71It0FYFR4K/oUfgUL07o5QWHdO+xHs6of1XQZX6kJveKZR1JkMuF22CxJ0/Uxr2Aa6gLXOdy/xtFKfdPsnLCjuqmGDAi5dUlAZej+MpPB4OYSTQC6J4bnOUBAh6puwpCIuCCKRzQajIImHhWTHp/UaC+GG5QjE1U+1mmTgEh3VOG4TSpoHrDr9CfVANRV2V6oEEy5BuFB5qNnsHDwD61a8XNPbaymmctTgEujwjGim0fMUoH2ETk9E5YOb9l1/uF4MHjI7h3L89lDu+Sd4AepdOwuiD9qNjjs5/Xf6hzR78XVRBhyWVSsFU7ZR4V6BvdAitlCoXgpkJJUWWqHBVUirIBQnBlj+rXgyEF0ToVcqEHHNMGdQdigGkprsFOq5B6F+wvMfir/GildX2cXhqY6CiJabmNURnaEeiB3R4E8/8B5KcjNOZp3Uc+AIyAFpIOCCC/ZS8AJxeRou26urRDwxTGOWdEaV2HZID4PwDkrmC6FPEy4krSi6JgpxO6jZ8OBjQZ7NqDYowYNE0uan9CeHpu6XGOnoBMhMAMB7JY1AHDchP9ZBuKW7DyXV+4XiweEOwiBuaImTIIlZtByXh1sVjPRJi5/snzyREz2FWRN7obplTgG5o5+kDYCTqzX6cKcSiibo5LLgBcsiyWWOynKmmaz4WSC6OUWqiTJHKy4LnGMk5ExRwjZ4A3KYWr2CfxJ/S1RrzyF3/AMZXVPsmJGKbJzoOEtk42TxiUzHF0QiZzboHQ26cCHCzC7ca7QIGqYW3uXymRw9in0/YFyZWtTgw9UUUWMhVUXGfdQuaa8SyLUJoveRErSqwGSuE2ox9aokJZrfQ+xUsWHUkzD1NqZAansy84eS8eQoeUHh1fco9PgXKBt6NB8XhRQqcGK9/8dFpw09B9Pvxji2BBOSXuV1PsnIGodQyL/8ATPZ1bEdP8IKkryYQY9zji+wOD0t88HcZgvIKcQerOHwr6DUYaLzbJ0nsVkgHdEj65qbEDUKVSfjKCbciAAdq5TIM1+DeRNHiEJXLP5UbfYFA6UZh0MbMpLGFxuHAmxUm7Rt8xPRRjdVEm+mXdg9oIYB4FnDiTYd6Lw6LzYPDyb8ROnHyblD0SUfdvwisgsehQKHATKPAUeIWon4kFHCIHA4RHAoiybgTlYI4WnAoBt6+5Q6D2VNF0foZ3K/u9LuP8IKkqHih9EuJ1VU34df2q209in89VF5XTewQevdRXuvHQoIGUGIZXW/Kjb7EGeYyMQT3VQTQghaIdQfqm7FDL3OXIfD7KDB+J0Xh0XmweHR6JuDIKNnoAxupgyCGWwflUXzvclWG2e8gXN/hZfqj2UZc5ChXkB+1dyS+Uv6FZOn6R8T29SPu34X3V/epabpQW6OikJ8rsvA+FnxNEc1A3BK/qP5X50H9ZCsedVibmFJbaDpQgQmfB9R9hW/+xdjwf1S2UlR8UPo3UcNt68O2q1+E68FLPhdYex4eiM5KNSAjuSvx1+OvxEFrkRBiflQ0GocAAB4FAmG32JkSQAx0I5HJCE0KkV7mQAQ8jQEZUDAPOkhFhZxlSakvDovNg8PLhRTwelj49woG3r0MJkCgghjgwQwsOAIcAcGCwQdBYIcQoZYcGHoBZ6kKGitUUKIHyFAkVoNYB7L+YD8jgU0NbYAh7oGUgPAMy/pYikqPinoYg4QM5QGqyRodLkDfugU0IHlXu6Yt/grp06uijhHCKOOE7igAeEB4wTB0Vg6IweiEhBMxgA7nsh5s8A09wVkEMoZ4SgJUd5aPv0lHmch26hZ9BLTv9Cpy8dEZobUPwv53wj/B7hUDIehPLKOjHkWHsrwsD0WTovxL8yp7xZOizdOFcFoHMIjwO68T54dkqs7CwHUcCCYdlh2WfosvRaNzWXdH+imruxurhVHuRh88PHrxEbj4sUxMnpwHJHPSjlSuvAGehDJWvdeOtXVFHq/ZaIY7oeFeOh460PdHRzW/MFqt0deqOD1COqHwo+FHJ7faKKOvnLhr34b9CnQ191qjr1R/oo36rvfgDB7mKIfIVLkCPchFY5nymOQIEf0H6Xh+kVOuFkcwnok+othA86oKE9Y+Vn1EH7yfqJ++mx1T3R16zS49f0ruaH2hcKAouRNvygfYFSB4YRfKQ+FQ8WysItVcn2goHL9LI+N1/f8AfAAX6z54xZ2ECPqanWhPbD24ReJV4s+kGOWIDYKfuwgv6LP1LL1rL1/a/rX9iy9Sz9S/vWtzLPuX8ll6cF/JZl+xZOpV591mO6/gSsY2X+K/gV/JZcDJZrJD+lq6orEHdHb2X9Ut8uat7P2iU10ed8o7vLVVr7iSRgYbHgCKdwEefML+gXiOBm85ouB/kFl6BZei/B+o/P5X7v1fu/V+/wDV+39X70/d+rJ5zQfkLJ0CC/ovzLEp9ZX5EypM6Z0D9V/f9qEd/wBr+p+/QEuHOA74XZdejwZ9QHkbljv9ozPhZFH/ACHAIZWq14D/AAPo0QwgggtC0rMLMLIcJSik9y34MHjIUt+E/wDDzfdRlBV7wOB8GFqnP+TazOoITvgIXuXSL82fTBVU4bfYoIIYQwhhDHZDCCGEMDohgdEMDohgdEMBDA6LAdFgOiGB0QwEMDohgdFgsAhhDAQwhgIYQwhhDCGEMBDCCCGEEFv1Kqnrx8G4XWPtwcpkyhqYIVFPVBp6C6dBkPqhg8F6OgBOEAcXTABqEWovGunuoK8uHDvfHCevssyQBYGURBdtOBDrI0Qjgo4PRaFMYeJUawPvJg5A9Rwh8mfTCkryY/0AXQyhlDKGUM90MrJDKGUMoFP/AMnk3C73txPomNlNXsdUh0RchMn2KppFVfCLgJlCAFlAMjBFkTn34CzzeylsV0Hs4S3+44Ozf2TFyRKsXDrI4AQ/DFOPRUCeLvVNsD3TaAeoCax7Dhj1HuFJ4zwkrza/6EsAHJgBnJX6n0v1PpfqfS/eX7i/cX7n0v1PpfufSA5DuYHsm/5fJuF4sKF2n0vwDuFOeBDgYwjU62cF0B0xwolTyTCwvlv9gugV0Hs4dT7he5917k1yggwQgQ3AzOGThHCOF4sKW6nyCX5foSF5li6z3Ck8JUlOnSGEw0mxT6BhrGHsf+Jj6PMsocv+Xx7hN4qKFLY/CsrFMnRojdBFwg1Fk4gFbCjJeARY3RSFdJTpHhRDNCnSCflAXWLyLeHUe4XufddnsQoxhBmQEwIBsplqbjdGooA3CC5LDspK33vIJ9NvRXjVWXhTjIUlTzHCWcwIif4Um5ADzQucAOwlj5IQTRD0Fk3+KaISZVKzImYBUmnsgONwEFHcjINaEGizIyF5Ly7lHko9Umli7IKgO6zA7c9P9fGsXQ9ihS3e6KqKCAcAKllQlWm3R3Six1FojVNiBZOidl/hNghOw4kmO/0iCG6gEGC491pAOBXXJuEXjwXufddvwQPAJaI9BhddJKcunvJx0Fw98enGQpPCkcERVPFqjq0ZSG1JPRyCZc1JAXcmQpElyDBagIibcmD6ul4SeDctNJ2BPNk6EiAdGaO1CKoACIKqsanHcJpi4BSKr7OkWzHoR7y2F2FeXco+LesMj3TfG6ZgbcsLsT15IXIgk5G4NeTf6k6fsUKW73RQNUXZStOUZqA6oNM2RcsHARWkIkZEGmlmA1yiaFiBchGh7QgMXg7FPAkBo9Qo4kD1XHDx4L3PupbfKD6dFjvwruoCBvJrKw3CF4FBwS+AR9HusvIuUPOinjPB2aFrkXh1Tcj5Qo7r6iy6Z9RX6HvlSpATgCHMOWvZPRgwEDJxZ8oyKEEAELO2x4+442Tvw1Jvi5C3RalzzHbDWd04cuy8PZjwomADBI4d62gCbLwVUu9wSWtQCtD8oADLsXl3Lw1HrDAQa442QJDgA1ZnLCzsUsBNKbdg6vkH2d1TX2PCYwGYO4EtsjKmYFOrAmQTZiyCWCGM6etPS9qgKW73TccRB0QIKK40VgQZ5oDMuSnuYUOqF8AtdUyZQi4sCcYQMOZA4vF1XHjxYL3PuvBlMmZJhPEKF9084BAHCTgJcdhfHsOHXk4U8Z4OD2MNnVRp+FaFuC2Ujmuso1XUIN+F2bfgS8e9SuHDoRMKBgUAWXZNuHuOMJMwtmCWTgoFQdXobhMnMbxL2Tm+gC2qZTL1IGasdKESEBIzUkaC4PdWAURJFObBUJ5HNSwpjGh915Vy8tR65BwgdSgJhpiJ3q1QhyAXOHEKHR7u+ieYioQWcstZCGk7isI2wgb5qmUog0UONJBaFD9IzCenfEsam6UTtAyGrqoToCwhBDaDBYCZd6hR4wAmC4DQlyt6U+BZQFLd78LrSXUi1bohAd7BVBAZjINmQ0mNgmJ95ChPunrDAEtlBoYcGGxAjhqADYIBcRxC7quIHhwXz7qXiqavoDFicapy4TADAqQuv8uDrey9f7OC3g2HGm6nhD5M29wn0vd5+5W7j24Y+ia6yOwUyjw7V4l61JVbOCaO56g3DtTPZmdCOHuPdeDHBlGB9Bhq2SKVQsY7xfGrvLEOCgAkGCC4FozF0UgF3CxsxpkowMaOEWsCxC1AwHMwOU6SVDM+JIcEDl9jMgVjIgC4kXyFTQGCF3PdeVcvPUesCSQALkspgBMQyC9TsAnkBBoxyAWI0MEaIntFgDtK0/aI4SHMBXR7MURCFT9WlVApDABMIAPG19RY4NBZHAkMEvYSZGtSFIk5GwiUhyLw6m4kd+XWOU6YM4AMM+IMuC9U0Gojpx6nurwLKBspbvfgQboWT4AeE/FiA5NGRDQ2pPwjOAsq5BqoVHOExsKCDqnAEQk8HktVNENgprO7IDKBAFRwgFE44FPVLyrcHQ+xec14MoVFpQaouGEXKg0uE1k6aGztLnVSFO/5KUzu89RK8uPATxbcXA8upPB/OgmPgnk2UAAs7civCJkDaVDk0L9yUyv6vvpp3l7hGhgnx8ABWjHu4SNx7rq/bg5xJM8jIwURn3NOocsAISICBJIGoFARURIQGkwWBc7GiBiVIYgCXEgRc9LOxaC6uvCKMxLDV6tdMmkcCtRA1mraLpH3XhWK8tQo9JBGA76DUomWeQON2UGU9w7wN27J7HlYcC8TDokQUEBYAAxyZdFQl26pwWAaABAlAXENAB7tI3UYZgCmd6mkyKID4GRaVjhuFlTiOF4cmSRTRydBzUfj1ff4BAUvFUWY4CA7mTDiws7A7okfYWV6kRc6J6bnL/C1Qm4S9UJCTk0ATxmXUmYKwQ4dbw56xeVjh06RwYGGcJ98iyEYl1chAQRAH4ZHBU1UqPOq1AB3TCx2BXmwXVQ6Xt4TzCfme5Sqpxa+wm/EMy66eNcn8eSwarY5uvgOEb6/yCY/i2dwU39Rw6g911PtwkdmKpyJhifhVARHTiaCQP4TgAFmQbEKiKcpbJTOdYAaa00A1eU7LjApBKgUcgjBRarEAaiXm/uEzEACAeXDNk6VqTZd33XgWK71j0hjgFi4cPKgRyEDAw+0SOkZTEgEQ4NBLJXoKFAGvAANz6B1T2AWSkNB7OEyAu0mAoMUGiEiFI5gDA1kEibISvuwcxrJkPi7hAACi0EjuuxhRSJhgZpkWiajCiJ06FjF4C4SBdEH4Tcmd5XNhVgibIQFodwWqGLgxw8eXAIC8GUOANQhSPwqlIPClQAOQQHNbZKgDkyJQcoIAMETBaCyAd7pggg43Hrl4WOHRpAXf90AER9MsHVDgoDCAHIoBBF8A5Txfh5sp8zgCfKndVbt7RNsfZwn0uBI3Hupdfd4VUer1Ri4QdEtg8+i56hWWHUm1cOOfhfRPwLiRg+4Om1gfSQTDBK6gXV+3BkBOWogWYXbp7tIe0to0AjZdpgU3/OiN61bmcEtJlRYSITcuXAKA1sQdqCIATBlpgzaROhRBwEiBYriyR1Z13fdeVYrv9QgOTGgXbVkQwkO0hoI5EASABMizknD5dAhwIqwJ3OKIBggEJyAWiJTgdBKAYJjZZQBqiYBDnIvViqaAAi7S4I+yWRhcBKmGzBeoxN0GEwZhyxyDKsgi9UdJ2AjEkAAAYRQIevh8COWpmxMNGgQNZFwMXofkhZUhmIAOLXeH9CEgLwZRsReUUqOx+aAAE4gDhAdhFFRqFSLcAD2QUwVDKYkIDDRPjQXRMIWTzFwTDqiIJdSzJxB3KWZyo8N5EJDlULyMcPEumCBIZ32XUnunYkSgvAHfoiMZbgAun7NfdNwnjqtSBO0n4Tv+ngz01OjwuoPfihVdU7FPt9iXc/u3ccMfz4KbVFUe74Vemz0l0PaXX8GWgkG5vwTvZjfkuk911XsqKbHuJOaLlq3tKDtmGQQTrycNqgLi5pkMdSjZEm4AJHQXkJEGEaoAWeRgxGvVcx/deBYrvRwWx2q26Yr2qEXMIhAluiJSDNAhg0A1TtrdUTGB1eYtHyg6Qg9SFDaqixZigCFgEAgOGdIkOIHNe2/p7wowDlwQFwwPcj+oMC2CaAi/OgUotyCrbAKDFiQizCm5wL0d0WqjYOaTzJh1K00CgEYmjIN9QDgg3BFDxRkBeTKC60o4Ls2EYlL23ShpYCPnWRMIGIyTsZAMmdEp6vwZMZ0BgHcock4g1M6Ir2nyjvJFEw8ru3AohSBEw9U/r8HBx6PdAZxkagyhfY7oGKWsz7QmInWB8pz8gAflAkCkm9PlMY80D7UzeyBABQdj7Lw1TNB6mjsy5inmdsfAnRV3fC6g90/mtxPNqul7AvAuuZ2RKXhBT+E3AZ0OKaf8YeOasw5XTe66j2PB5zmAWeQ9oqCixIDw0xvIrZlSYWq4knowQYeBIEwNGT8A6ME1EsN1UgMKLhSRN1Nu+uzLAs5scKW3yvCseBnDMJJD/K/I+lg6BYOgQp9mRNqAYHyU4Br4YJOJfPJBpwoAXYtSblEICCyLDVdEYckgVdkRugEcyUxCr1HkqDbCoNWSzAYWC0DS09w4BsU40h1/qD5qSYkiZWrgXdFlHDBCJEBnFkaMHR5qjGBA/OLaSiSUyzhmMyHAuyi89s1owX6iWOk1T6g4QICF4FzJ9pWRWZP81z9OHbOn71nhHgfK/h9l5nys/T7LzPleJ8oas5Xujv6vpD+FEhAIBCSAIsCD0Jh1B0R0gGBoiZCwWQi8wAByLduDbKBpttLNLKqBVUpUESCc7ov1+K7pEfqK9lr6ha+yCx9iCwUHY+yiVIAcyhQBAcmFHkd6GPU3cD44lb3+y6g91HQfcpULoo/hNKkrn+017H2Xl2UnBLX4Bqz5bAqcS4BXSe68Cx4eSsO68FYd1q68QULwrL2rx7VHDuPBOt9mDIG1yZQwaKuisHMsNdEAeSWNXiIlEgsIqU0YEuREPsH7tsiQgLAcAaAAxc3U86JLGYbF73T8xr7L2caMgxe/wCS+yEuFLGDMMAecWUlVPDZBtcwzIClxNysd6IEAIygA1hVhMHK6XChATj5dAQydNZ010ECZIyjmhrKMDXBplEaMKfqEkchKNNA83ZAkkMQ6IOThEgECQHA4aoNBCYgQFqp9ToFO2/PwBwQjd4ID2a0gYQIeEegRkw7nR0tmtFBxsFgf+oTaQCqHEindRvm+UdAGyjhYlPwLl+99pwVNEaNR+j9VCgWy+z5F5g6PIuvgyXu+FI3Cl5SUqCuf2GVC0YaJhBBdXOCn2vIvQNzYzFvZHSUEYDJJ4SeLQJ8hw0EH2NVRmd4FEwMB7q/ElnZ3GUPH6Xj8rx+V5/K8flePyvH5Xj8rx+VQDCHnXku4exQZ1gB0hCFmjughy6S5gIBOXfmjEAEnaqFg0DizCnKiAlzFUedGHRMSXpkm2EWITeY+ekGj0F5T9BaMCwAXITZRGFosPAKpmgIJYOtNDQ3NTQlcKdlxJSNOPS4UIC87p06gEiCNU4S6AT2c+BD1ShAQ5RCCcLp0tibonsFENAsh2PJA9pwbIB9mdEHDnxKKCyzixITnTV5qbUPYm3/AJ4Odj3VExeLIgTCxkKEgVQEDMipRAEjcWRAEuEQGgCwdiw9fsiOyfG6nIdP5TBWByUy3dRK8+69T3F3/ChuPfhqV/AYSnIGNQCJAMOEcSRYoGyABmgAcgZQMSBAQXe6oexM4wBwJYZRCrEBgY/sjmMgHkaaJwGBEpcOl9LxfSDikgECnJOcz2J5/pfyr+QcDpc30vD+ODf3/Sx6y/sWPWR16tB93jKH6K/VR4ecop1uBLgc7FAIJG6mydiCRIvVoCESd1rBR2IA6yaVdG/UB3mIJZOtVVlkGuoeSDZ0A+HwNwwcQxCXEGLBR3J3SQayb1TSkJAJF7AOMITCHGszZmA5cHa2ssSR3WEJp1CWlUZIJoAIGKp1+uHT4QIC7PlMmOUBhGOEBfKAMgyVNUWl1fbJjRFIQag+UFhRFsW2XQIAQ0NEYocTSu5911nsXVHvwnwSeEvNApBVDiy5poQHCjFVACLF0aJc1AgSQQtR1Wo6rUdU8RJF1yHQE0gdnBnqe4hUHQSH6lDIWBI5JyGVK8a5P7potPlHBWnQjgoordHB7LRHCOF46PhK0HVDA6/no0PnNHXzmjp1C8ccNF4Sjp1W3UrbqVr3TXqgJALgNIUgiGj3Dk1wmg8EFqIsIOk45KZyVH+kbJgM6gaE1/qNTgSuakLnARJJ5HlKZ4gccOw+XdRwOjW3CfdCAQABKU5OAA7LOhMAO4BpeoIqKJ+hE8hhB5y1Pf0YBA2Xb88AgCzkJNhZUewiBPNEZB4gahDicegWRsVJ1DU1YgoAwRnIwymwG1A9TIGQXChMFN5lHjfh3Qe/Dt9x4SY+FOhmpCZJqFUNJEB2AisJrqhO8osteG61L3F5OkFAYAdBwO6z0EpwRoV/O9kPWGZtQWXqv3cNmWRZFkWRZFZFHJRyWRZFkRyUclHKOUco5RyslkslkWTt9LwH0mygKlB8qDPPqWo5wgNxoeAcUq4d1KgSC1UzFw3REICFgzgVkLL0+iAATggIqot2UGCfLoEKhcgtBnBcFASKtcqZsX7kbgLEhZFEBSvhXeTZ6LIzcDAIiBolg2uyvIEQQQ4EQRzIqkenwB6JIgKfivCYUxlUhURZCQ/wAKIIIicoGooTBMMlTW4mU8EwRD15qZFkSHEOjLgAAwhGiuqH4l4l19/chUl3YWLovfh2/JMhIqXdFChFURLciUGQOFWUc0HD0RwijQ6zqJAJg+h9I9h04P6a7JzuK83xPphPHzYf9tAAtbB6ooD2otpdUosyzXe0V5IsN+8SAcmu4dECbWBjaYBoujfKwgFtQs+ECvMGEB5NBhG4yxABiWGuo6ICYzAAuaoIJhhrAbkqogCD2RAGDWgBDFwamSHd2ZEEAQICAgg0NsnZgTG1Hke/priAp+Ko56CfZO0VBMA6l3zIWEJxgcuSPYkIigEyaF0PsgAJzREWgEcgrPAACMmi8O6MefuUeFQuj4OhwGf4lCciqF8GQqntGjguhkRC1uiYCgdUQaat6P7Gh8pg+Qf5ULy6K8mXonj0x7P+8mJKDIqRjtBeNkAYuxpC0HGilzADghyD0HdWkjKoA8i3VmQLmQuwtkGW0UuMMdMh7bo6IRLUQAWqaCdUBBrVsbmFQfYTQQTQrk2YA3o63hxATE/Ep3vqURlZACyn2V1f3Rhkixlk0QhCY99hVAgIVN0HEBxXyFOiGwCwDsUXLBorJuUGcnvEIuLxsgqwhtEOUig4ATz9ygeMF0fB0x7JRPyvdFkQdiLPzUu5BwQYju0gYuDCqSbNKMoThGw9Hh8b9gn8iIOHQJ6f2Ponj5Mj/vCYTmRAIoJrUFcl2kDAf7hCM1iDi5CzRyFILCXfVxBfPAiJqLIBJ/Beick6RGRCYgTcN6omCALxcNGqd6JkAAOwYLUWuiqlIdGr6vxATkNPlSIZALHRAKLmCELSVDVDOVXAqniHeoS7pxIKQd2Qc8CXF6ptwZgKA9o0uKrfSTVoE+6jFWUpl+pwIOHXj2WTv7lHjguj4OmPZKbBHIa3UpuHgTcoOgQGJSUAJIdpugkUUBAcPPo1udb5BPcdS5e/HfTex4hZ1TmC/Hy5H/eRiDpNAgGubPATYkEvuMDDq5LWUcWimZnk5gKBYDNqMLm4TuHuiAkAgoAYCCBUkhVM9jM94cFhzGUNVUykFoCHi/q35GFCnZ8qRB/JScFn0UCMyYdECLk1GqIzEgvsnghHVCRYLAfOqBkAKMEHSyqKpd6rECjVBVcmjs3ZMWp5U8Ax+SAihQ2p7Jz1914sF0PB2eABq/1dk0IBjunILOeaESC7cJk6prTQOjeD+hhqBdxMn1DeESegG4GOqIAJBEiaFE1Wf0SUxh6PLkf+CQBUgd3d7p8d+Iel3gkBzdnZ9WdAg4kImaoeS8ig4h0crpGFRAMFhIg+rfkYUckztEHjJHZBznBTYJxuIQ8kc06dOKgeasG6NQMBHAMCMM0ong4RBo5QAyBbiSLWRLwOTLRYCinkXOjUTAWidlF7KHJ7Ew8B6Inr7ryYLoeDz1cAfQ3cSpggJc7VT0DGxTIOUYFAOLgFSA6pxLp6Ae5PFXu83v8A5eXI/wDBAA4YSllioTCcg0xkgRcto4uFpE4RwifkLJYQwQJHLExkpNySUibhxGis0xggPA3CRqGV1V2E7OzJYmJXhtx35mFCk7fKccQxnFWNUwmUIBSG+EGCi1ioQA5KNokOPvjmiTWGiecX0hCAjDqWUMMQ4uEw9mU2BbKN4hgyVaPciArElsnDK4OAiY9oRkqHlz19yvJgpbffh5auANUPyKIaMDZAGAwOy7IAmADyKYAQhwXfJA8Ag1zHiCbjYE/BZXnHYZBTkkUJLbUHYeqvo8mR/wCC1EkxNQXlvKrWEIZmIIyAPFwxTMSIEElgd3mzRyDp6ah5iLGNS0ou4sW7GuqEN0CHGlGMEaFNHAcHek95G1Mcd9M+4UKTDuiEo0iz6FBnMxBWa4RnoQBAmkzq62Tog0VEnDZVC70fZDJc95CPZSSwiSM80wSBtGiAWMaE4kV21Vg1TYRAQy4HVGkIVPhB5QYGrsnYuEp6+5U+SCnt9+Hhq4SLMs8sDknQkrnVDHgBgJqQS8KhY72RicryyA4JORThxL8ASLQHv6RKJTEgveb6SmjH+XkyP9ADoCDAEIReuLY2UKzczAwwANksjnoZ615/8LAbYgMVrUiiIFaCARILGEdUIAMBYW9LBnczbXc/ZwZzWXqAGrgrc0RN1IPnxFxCeeGeifccK7JiWXLEIAj2LMS5KBgjgtsQUUK01oIzGeHRJytRjoiJjAWbGAQJjCOSoDlqp4GdOAl1OQgGg3TM4O8uCgyYobdkQjFUwbKIdJkwFYnoWeXyVPkgu37n0IwBxINlTiBBYwIGZxGgOaFjS4UA5ccyYBGBBY8kMAEBcs8omJqZc1KJRI+76CmHMPPv/wAIVeHkyP8ATIhLAOQeYojopGVcAYIWiu0yeU/8Ou3AG51r1VCAEAZLBxBd5zXHpc0MQQGHuw2I9yDl4CDF4LUSiEwYFrAORki6wJqOJoRcFuSA4XXNB2ltzPDnQPuFCk7IoEIUFF4g0RD5TBDoBIuNCnPhyj7E4QXnRh2QHCQLHklTljhUACThAInTILIiU9JqyATEh3NW2UBMOiIc7JtEjCbd052qU+3yp8EF2/n0ICGnxJKFtzF0zORyD8EWBG1rsUSOgE+yPJrA5IizI5yoxK1twDuUKc4SVwEuFoCCtAPM74Tq1kIE83H/ABrw8mR/mQyKny+icj5g5qS2pOBmje6AiJ9jdMz0YilU1aEJMiAY96TrRAHIBkF/92dwJtF5ZRdgkuE3OChMABABgMAW9JIAnMwm0eBVkkiHNkfLSEMmXwfABRiQZGvaVpgChZpZGBswquKmi6X3ToFQq7LdTIe0IUQ6CxudhHWiCbqApON0/mkBBJJJgAAgwC7ydU8A5ponEEppAFEQIkOqDxNk2ZqDqJkc3OTqOD/COkDFEB0IQbKLbogTARtwlPL5XiWLt8OpwAlZvVSC6AwgIG6AbhnF9EES5g2/AxYxKZ3BUV3xbcIBsSVIWd8BMwdhG5dkKaKAACgDDl/hVV4eDI/yDAxLqn0NSg6i4JNuk9Toh7Gg8HKOHbB+xRFChNhoFZVIMKW0O8KDoZ1RwZVoTXLP+hAKm7RsyOBkEHQ+DDmojABhnaYIygwa885H/CcCi4gdCwliiaoBDucdzjbh4106R91C7E6VEyTqNVMIYGh3UZeGAeYlOLWA9PIJ55ww6aASZ9h3TDgll/CnoKam3B1nGq6CqikNQB6uaAoHBcokHDEqxY3NBpbqG+UI6YOFxXlWr24M7fDqcHll0A1GgCjJT1AXoygos4sm6u7gB7cGICAQ6CH5KTjNicthVBNcLl85gf4xx8GR/jDgDU5Gw39kEvlB+iaICAAFAKIXgCSdBVEvdHsdFKcgUAgSgARPRKtkPlVAZ+FOXb/MmOJoMN7ldE+RUgl3IxaWOIWwDrv8p03Xm/8An41yp7H34M50QGpGoTGrEPnVPr7RkNDKeX2KEQhwYHMIP1E7ECpmDsi3AwQYIy6INIpjnoE6iRMC3NDHTAm1oyhlgSwVms6iyfAQ5ECxB8rwreHi3UdnDq/A4HuAEIeJNApAAepaqakazkA7tVOVgAbQcQZEFBAWqtJ3GgQGGgKAe+coAAAMAYDAH+MHj1PrACVaATsDwIr3MDDW7shMQdqltG1vXi2FeUGT2CZlQpwmQKhCbIphiDWLJlUMdbD8dP8AAABmog8bbp8QIpNqdhnTXgXoTgjVUlGODnRNYZJJNyak+UYf6eNlS2Pvwd08CzuqAByDYFklgMhBxJiKjVqpsqTnCA52lCIB1MpU5EpxojpVxdEIIbaIIFgAahNMS1EAU8NAQlxaddkAAGAXQ8LzbqPB1PgcIhggzwoUNpdFnvsQFw/MNwARN00ycj7QQACgEN/lB9JNx02ktJp+ppLYl+AxOeiIQJiHp7CAOyAww7nUm/o5xejPlUTEzZEIQgq3AuglAujJAwdJOygYkvcg5BOK7J2LM4BbD+tw07gsUWgkHCahJ7OnuDEjc1dkwAEAUAgDl/qAE+TqXPgwOygJ+DfZPBNjIAAcoEo+1BgPdVfQoAiH3REsZVxYvupHkIHi4QBk8BwiDG2qLrbRNRrkMgKiOETjqxsAqigDVAqhpUYV5Kq2mLI4g/Iuo8HX+BwcGyeI4E2I0bp31IraiyYSzT1TlzvugDORsi0DDP8Av5VvQAclgLlPBWXYfWIsxOhvjAfR3SNrEwAmIoQ4uNsHOvpq1DqkBQg4kpj8o+yg6geTmh8jG71RAgrnxzsFCnU7mBp1/wCg1okusR6o1BbDCURsiKhlB2TCcdCDkFMjzB9U/lBg7IQBaBkMMOTqgDMw7AkzCIqumifAzugATUoMHRrYEONqIMHhNIChnTygBlTvaiAAAAYNwA4LnhEN+HU+uEHgS8WhkZGwfg6RWR/38i3EOmCssG5+kRwDMOT3hbgySTUoUHgTCBIwdnDx6tdywy907I74tjeo5VTBmrU2Ltz0TIJCBUkwTzh/JFewapx7T0GwoP8AphiKtIQfZGEA5sJ3AGgpTG7GFoBwP0hDuACLlqpghAw4A5iWRkwzIRzCVIuKFhw3wnqA7VQAWnXEPkA1TFrXVIRKZIKoq3mFXUIUgthqN0QJNtEHnFLFnRhoMsiEBkIDUfpOnSh36q/Cd5U8Igb8Ot9cIKIoHTBQ6Dgo/XgP844TwfxIQeGHlEQLliuTv9BEW3Xs6IAADAGA0UjdPol6Ku/pAUQktigpgQAuGd7a6lBh0wGCpb+EAouvD0/JRXZ2bCg/6+ap2BBmGgClW3ZUMIfT7ycQwG1Rs4KincdwQcHLRvAfBQYA955ItzCBFgIwIcCfvdBFgwDeA9yJQgGg5N5AASjDJtiCLocH0eeiLDRAQqEXiQQwq5wigzOC6faMwBZS6GxU7ypXTKBwlv8AXCDxd0DAIwVNP9I9DB8WRhpECglj5VFkuBo3zxhuE/rca3R5mASHVJcQHQMm0/7Y9FgACGBOehOFyej/ALsgR/r/ABkX4BSkaiEzMArDtP4MQpICqWySgA/EoWh5a4roNdEyM2Fw/EklMBcB0QiG5MlEQAFm0jqVcCwa7o5yDXOyAuiScD2lPxoxVnvyQoACogSZQqomjQWd0GALqeCOjUDhLfgRAGAHpZEkAPupknrwwnCAj/OONF4tio9HUH/j1Dt8iJqQGoxDSMIBUZx6NQcimI4/UB7FB7HYKKFaMpoi8w81jXoQ2EV2oBsFNSQ1JD6ZWADgik266wlNEXoDAaA18lyQBAGVEgh9kzrJ4WlGUBQVXclRgIw6mIHZFgGFkAGARcsFVPDXTqnCe/AMiCWu+LoAKXAmGUCTiyAlESzp6IGSP84PGi8+ygejqBeZf/xuXBIGxbPx62FPjNeVEQax6UgQCDYd0IazuhMxoKvdVY3EZuEsnBaKlUYXC04i0gHVngNLLMyEMQ6HDmQ92CawJKNmofZA1JGyYocM+Fs9H0gLiNTlFNB1DoJIT6CtShnPVGhzzCBwAPsBeGPjh4sH04ygf6vHT/1CiCj5Lbr/AJxxovDsoG3okbhTf+NHhkMn+A3YTRnsyJ6yn0956hRYf0FB2TFaDo+kCfK6JzvVgA/RM+3oKKOiOndbd/tHx+BuvFg+kb+y14HPZHPDX/ai8SygbejqDg1J3P8A4shltAqAMQSzh7pxjtB6On9JE269CR8IkGQhTwlSiKB1m8h9r8Q+153yvC+fVjWtS8j5XgfKewUigI34lGpmC86rzPvwE8V7+hRibOto872P+1FHkhQNh6IbjhJJ3P8Agf0I4PV9I/oRy6FHLojg9P8Aof8AhZ+RPqnoh+APxlR5+59imF/B+lBUlPCVX1D0BBBZcQQ/5Y2exQOXohuFL4FUnc+oksDkHhOTu0ijlFFHhl7PIBheOEFomu7IkAKoqELhDBkf8L4ydhAnEWc1BkePclavDpSU/gUHB9K5BdYuqxLF1WDqsHVYOqw9Vg6rF14WJYuqxdVh6rD1WHqsfVfuX7F+5fuX7v8Ab3UbPYoGw9EjdebVEnc+/qeWB7RKf/DvBhHM8wFhuOWnkETX6SgwZqyf9wTsN2aA1QKHAmKgQ4GUCEEvAkxLSrwIBbgO8iyaDSyLg3QCq5VB6FVOWPtKD7C8ItyeQbSqwHQLB0C/MX5i/G+l+F9L8L6X5f0vz/pfn/S/K+l+R9L8BfmL8RfifS/M+l+Z9L8z6X5n0vyBfgL8A/2hdnsUDYeiRvwfJ3Pv6WC8BCjNrAiZ+ACtHVbdVr1IIDI6rUJ1t3SWIaNheF8I/wBfpBTxbL+n4iBZBqs7cFJOE3/QEBx0WCwL8CyNwPuh8jsqXgaIk4BsI4TDgV+BfgWHQsEYdCw6Fh0LDoWCMUY9Cx4E/h/nJBJIBkEzH+yOarzUD0SN10yJO59/TC8nQIJr8AG1RGWTmAk6cBZ0l+VflX4l+JEMuIRzXW8Zx/mRjsRkFZOzIeL5Q/f7Ifug/dB+6D90H7BD8i/kQ/Mv5F/Iv5PpHNRy87I5+dl4vpHPzstfT9LX0/S19H0tfR9LX0fS19H0tfR9I/y+kfP6R8vpHz+kfP6RWKx8/pHz+kfP6/2jmpKj0SOHknc+/plADuSdwn/h+kRYnmRwer6Uux8NFv1fSJEDRY4WnZadkZsgJ0RDhadj9I4PQoYAWpJoxl1//wABjmu5fPv6JG/Dydx9/TK8C6y9SzPWsnUv0FZdf6snUr+5R/QrV1K1dSj+xWvqVg3UfACPh7odi73XOdvYGup4Q6t7k/8A7sc1Lde59/RPBSTuff0yVDzlBb8ND0QQF0QjV+A4AK5wuQSCGRMRnsctzOgF3vPNfQJ8BDGx7w6ARNjsTzgZmPIIAY0DA2xi7v8A9mv/ACz/AJwpbr3Pvw14AGVyFE9WFgVADseEcPButfZX+kdeiOnMEI/g/wBJ3BA5T2qjdyRWiJapub0SFog6CKaqlvAHsaioQMBcGJGrA5jh/wChP+cLQYo4yiwkbYR4LT1lPHOB2o+EEuDMHZXAjeFCHy5oGGaS0Op+SAU7o4RmBGSLGi/IPtZE/F+rx/a/B+o69H5X5g/V1b2ftZHm6/n+1/L9pkR0z6GOhYQWTwGrA1KeYQGJqAJ5yX9l/Rf2WPdYd+A4WHdYd1h3Rx3WCwWHdf0X9l/Zf2WPdf2X9lAS4PBl3MSnR4MopEyrdCvB+F4Pwj5/hCQDJMOpYL+dP2hP0j7Q/cfaCiYXAb0Lpi1AJLvFWGz2Q2BVp/oOQVgsO6wWhYBaFoWhaFoWn/ZiR1Dqi7REFVFyVboB8ry/hHCJteZP7p0R1EOiONgaH93RA6AAA2YJ4AkkwKkuhUEOHLI+kEoCBjFNKFg6lwdS4upcXUuNOPrX9lf2F/d4M4+tRgPLYeg9J3KudOC3vyRW3ZGyKKKKKKKJRz7I59kc+y1LUvAfSH8Ppfx/S/g+l/J9L+T6X6R9L9o+l+wfSHIIDVAIIwRQplgGglYdiAABBoaUO10/ZXB1oBiAbFwQj9Ej4r+PhbiR7UAgdIIwLNU43gsTEQnakS0sAGIaF+6svUsvUsvUsvV9rJ4ar+j7Q/o/a/sftY+/2rBH+zjSmTmPjhWSvuKqBQKF5CxPk/CIiy+t8ILS1ZzrIZLasCRggS45o8WoT1HPt6d0dOgv6LIdygEWoJgDclFI5Cga/YOi+WO6Q7q/t3WiIOAHIITjQHZcwqDHNUz0n2X8iiughzsO6B3IYVASXcgLe5TnQH5oGyGF1mtKR3VYBwBjuiqoxo8b4XnfC8D4X8voiuTyH0sfLZNlDJQWpBauq19U/wBiiHRZVhbm7oiFjSdQy/S+l+99L9/4v3/i/d+L934vI+F5nwhruECAG2T+sIcR/q48i9h9+nAcI4K0PRFHwIooooooj0GLNOYO/VZeX8FUxfFD0LH3QNC/mEwh25A9jCILlJHPcndyOr8Kk7yH3GwMonTT1PgXOL7E9yoKYB9bkHckHVOsPukc2qCS4qA2PfdCWLXO6fIig7QcgD9TWRwib1DchncIYQxwvqPVMbP7Dhp6XIZYsSXUSm8D3kG2rMJLKSwYCNPW6b/Qoo/6T/jqwk4H5WxXDsiiij4EfAiiijwPoKtLclUcdieuQ5BOQvJNSsA8EzFTGhh3dUoNI7Fx7Jpy858dynAedk6IyOy882qgaiwf2e69hPe9pAYmGszkAQEUgARqAZ6GexbRSL82AbAAFpwbQndAWPZTtxctiiMiwZBQyApqrRRwQ4+goiBIoE5RzEyKuod1MClititjxQTA4FxDNGKXIf5AcBOlUAco/wBZ/wAGgCaP5aDuYVbkkkk1JNSUMIaoYQQZHotfZDLshgoYKGqGqwKGqCGqCCKywQW8MQ+SHmAsZA2VBNMkR3hi7wpTaihDIPulmrCbvdPueaG+ymA1wD4UJAnAIPs6HbLfUsu6u1EkpmKwHvMz2JTIoWcgCKM+zjqBWuqAStYAmHeqZQ9FnRNLopBllj8I+FeHxe6/F9l+b7Lznuv3vteJ8rxPleL8rxPleZ8rzPled8r8o+1+R9r2hD5Wo6Ptajo+0Mjo+1h+WUEbs7BJuXEBcld0MRNAk7R82R0IMJBxVf2QE0YtAXb2/wCQPA9gVLH2UYd6hxgDQIoo47I4RweiOCtFoVujqtXRYHosD0WBWB6LA9F/BZOiOD0RweiOXRE3dE93RMZhj5UoAux3me7DogcGLl1fcQYYpDEwIC1I5r3sidyu2IPhYHoUcuiydCsnQrA9CsOxRIq6FMOyMd2432C+Hl1WHn1R+L3WHh1XkfdeR915H3/0gKiiY5FdjTOHgaV7SPNUaj10KKAc4S25QWQUCDByD7o7oI0ac1WcdpCMwAXgqGpHVsmLjUuVW/0wRJYQ7PCLoREgchzVq3F47xfuvL+68f7rw/uvC+68r7rzPus3Y/z/AJNZv8z8AT/xanomuei186rn5uovt4Vut09/ZHXo/wArX3C1PWFuvj+0c9SP9Fk6C1qzSy6/2s5TzXuvAe6N/F1Xh/KPle6KqoGIIcUF4b3RPld0f3L5RN3n9kc9X7R8L3R8H3R/T7I/q+1r1/tHPU+1qep+1qe/2te77W/U/a36/qHjryeG/nNb9/teSvJXkrRDTohp0WjohhGgQ24EBg3OCHNftiA6FMMyzPatihkCrFHZnRvdm0lgqsyo7jeqN625MHIMVbTOtvJU3uGXqKaINDCCCI9lXHKFuKfmB2QLd+oteyDyEVvZY6f4tFbdAhlblDwFoj/lPj2BWp9lh/daoIY91GO6KK2TTRaoegPHXjrx+HjLZbI4R4acNFt1XjhbJl7oGk9Vp2Wy1WvZalD+lNQBaByT3KHhQ0WvEOQingo3BR4mjosBuZCCCPVnfwjqTKIA0B00Ts5m4MDUMa6Jh3ZyW2otE903Lg9+BZGqchOEVI7oHUGDRj5FeOhnxyRX7lDwLxl43DyFqPNk1vn/ACNYa9sEYk+CxYhC+TgIw4W/X6HNX4ULxe6/P9l+L7L8X2X4fsvw/bgRioxLdSrtgn8qWjoJj0kx6QmI8k/g+1/F9r+ZP5Ex6afhph0eDcE8egmHm14E/lTDpJj0k/mTDophxzygkD8n39MR2kH12Tzvlfl+y8D54wRNBw5IGgshQWvKKJmZzIRKTQsMAeXVZ4PlWon6IVqnf8R7pteEPJTMAeewlClSTMamSe5ZOhRwiP8AZDh1fSKA/oR/z6HGJVeJJtZiOY4Hta+y7f8ApvSVkRhKNw/udpJmV3mic95fTT7XuhKKMHHB1NFVoUBOVCezoxAkz0KI7I3qC5BLx2BvdkfySOya8WWI6BzBHuP8W2inFPDpAZrMixQCw56n/wBIkwlE/BMzA0XgAQIAGLKlAPtPd4sM6t7Jy+O6hGNUYlMQXNPZGSmTHwL8UnBwmwyAkZOJf1FpNBJ5IkL+f6ts+tXc/wDnOWFSgMCbokgggDIMAIHc0FbnKgJ4sP4A+eifEJsrmvZO3LgP6Utom906PNT2ChNVOxDGc02PJIC6nurAHJ/dQT5sfpMcEEZBf24MBrOw/fbgZmAgufZam4b7RVDD/CFPUgd1Hqruf/Ocu5cNdQmopO80Gk3TTc7PNPgIdC6dP2UBBSO6ZlL5XZ1VOMOqJ2Ge6bqDC9LuAldp9+JJwSDpC0HxzUuzoX2nkIHcqapirP4m/wAer2BR6vc/+cBPNUDmE55wPuwE8lAFGsBAAHYKXLEu2wx5dD7V8LRMnCcAtZYUKBZWVkCDYLkB4IB0nloAJeyJFkkeclN0U+kVgbiSBBYiQmBqPx3KA0TLvG1j9qSeS5r6f4vz3t65O5/7XnwqNorPh9nQkMjgML6OaINuiUA++wIAMjdqti3gA/giqCTQKA/8lEbFql9ki1xN3zIN9QMtcEE31LW7Vt3ZOliA5CBnU+bCFH9JZ4Mweyau0wKrUQBc7AYyTgASUaXNNzTyicTY+HjGirqjigb6TdCI082QKBYeSsWZM84UrRaJ7IgpZ26lSoz6eHYqcS5OZTBvG4ALHsUSY8aleRrkcx7LQV2H6TGNNNP0771c4ghUCqemBplNA6/4Qn2etJ3P/YJUGnyHcaNUGwBBrAGgaACKogtDYEscmSJBJpxKpNZc4ZcHMGS2VCZJKWpNFgsJZAh5AMaECC9iATNEblUBuG5nOCAdhtsDFA8B7J9SSWIZ50LbDZBsJsDtmBDwbiAgAavYE0klmMEFnsiqIMJvVBuSULJ9dBYhGWLUB5t7FFhqB3IZRzEO5NEyGQwRMJQcAiRFlVNijmDBZOF3QI+cBkygJhYBoJ3E7gMQK6kW2F08n3zQLVQPGVUceZRxrrKc+ZUnhO5N5hME7RrKcDwXkaTKM9RN5tCpV2qvFX0QNL4UvMHzwJAiCKICLA6AZ4Nn7N9dUxlWl8DTP+MFPpR65O5/62lQYk8qWiYLAZNqicAYxA7HFLm5N0QXpBqgYQqzh1oObiIsDOVrkRaYiAQDQAWYn1RF3IO/KylIBM3BKBNWxCZ1YqXlFCZ0ZLjcG+ACXH50TgVOrrwAwSq9AEwkQUnBICB3wChEEjNm4hkx5FF62DFmZpB6hARCKlUmh3OQh1gcKtoYqsBEIIAmAEEyUACQ1u5EwdpCxu6ecujMQoEg4aKoBCAmWOGaT/VZq4WsgdJQZU3A80Rca/SMsetkflS+C/Upgi4hnR6p/dNjbhVVLaxdyE0F+3gT3/iezYLOkubN6qHwH6RIghiEWZ4qyyp/zff9cnc/9YwnXQ4GQXmn6MRnGbAAsxHmZtSiWosJpol9ZoUK0sNAWV1p6IOAz16wWO6wQNQGMgmC7choAIEOICjhBgvAsSMRoBijYRzcpocBkzBOIgCA6V0GAAMdHalQfmMIpAMawvuH0DCIGCHVALkoo1JEEsXBlpg8nIE0MAwADVGp4c8wFUHBJMgTgmawPogdyKxCQJsKEoQLMrgBIFCHKFvNQYXQQwGo3zJAYoccG2HLokvDou/JOJ8/iNvCnFjn2Rfy6s9VBM2UvrDXZUr2TyFC/q5SrJ0Z1qB9pXHUp7LgOqZT0BWN3RKGvWf2cobjsPtlVPpQ8WRpaMfX+0nf19Q/9REV5Ya+5BgGwAxgOyDxuQAameP2TO4MHeqAGwOA2kmmYA75AUV0Dd5QEAagBCoqeXVVXAoYYAQ52tvUjUg2BmsXpUXAsiTPuIgcNQXIQapDgCSzGXLY7WOUNSABwfQuMywoi4NZDKKgaIQAR2CDJzUFvgiaCFEZisuZdcsICgAGNqcIo5QTRK4c8go3JKpXZwJNAWkCpCZQFZFshvzumFkTBCRFDrMEVIMIcUrGOCFQCzgJgG5IvkBZk4PwnPJap9i3ZV1UTbGlEwbRVn5qgCifz4XhLlCyzmiBWNGgHuFOgdAjfQT7qZQ4ujne6f2Di0iFZF2K8rweKbPn7/0jZ6KqOPU/6n8eA+UCZo490xJEneTkSR1kxIzIRsXAwQAYxBMmtzoIdUnaKg6ClzVC5LAXEIAPWiJRjNYcsAtc2ha8hU6slmkIJk7ctEwAoEOcCQmhEuEoGcwC8sGkpTI6oAuwzlcKKSYWAmalEKQCo3SyaKQBgfJLFL1oNKjOXdUYOjqskATh8UG66IOsADkF84bojNo5Jl3ZpkJyKSd7IYcEEZwQ4ACGQB3nskmGSSIcsYwpHJEjZV1aEL1+U8g6KJv8/wAQafGQiqdoJlDCEc0rFfYqi1V37JsYHmjo88M/Ap0WWzskAPZNGZDBvMeosm9uiBo+CvVPgUqNjxOF8fv/AAXU/wCqnqeg6y7Y90BVgS8aDQXmBrCkSzAS5hjULiwzJMXNQG6JmblSMSFRmDRY8OtAQGsk6AdEVLjRVCrAAZRCWrBu84gKAORbIDGczJ7kcy1LM2QZLXZcEagwAAgO7q8OSxBDiBGZFyx5wOheIFBIaAFPLgUBORkLFow7hx1VYsCRIjefeymmBzkDBM2MOgzG2GQQS9AqhJyTSAsUyAoqGlA5ixzNp2EIDwwnTwIGZMpqJpruRohwDCU5arn991IYkGU51RNfCpZ1PhVgtVAbNGqcC2bMD2UqcklGAhlPVkfX8VSmRT1EoPJAYEBBxosnRAYaQSepDIgO4YIADr/wOp/1MR+SWALmIRg4F2HIOol5J1ZOHlqh4MJgVWDwNdB9IaojU7S7sAjZJhMCFnO+GaLVjnAQC5jXdsVVblxuAwHKpmmHUtBwyCwpDWWB2QkGYBUZDA2QM3lPIZyCBZXOKDsXZCZYSXGVi83hYovV0Ggig9RI9CgJJgHIs4oKC7jLoVDMFybNmWuZT3YuGBAssICAwIFlQrTgzQupsaAYHACGwrkhiCQmw8tmg+E5sBzAoBcGuoQ891G6PmyfsFhdiyh3vvohXzAWjq5DKiAQKAJ2ejyO6x4x3m9159rcZuk+I8ERhFQtvP6rCXNvdDltPpNloj64VB6o4dT/AKms+6PpUaZAdtQnHhuTrC5hQxoWFxAE4F7DSxZHLxEg5N+hiAlCSYqRJuDsQLVC8swAPDjBgXTIBUDQYWmQ6WXIiSAsMl4CQxYzKhwBDCwJ6rVJLAqpOxsHChx8y65yQ7SJZNiDBTtyHbC4iqXZg8qiEStjDVUTEu2zoLLCLqohFxUL8FrBDGoIEkLCH7kEahQw2nYZLhBKk4gEBsTReBuaIZmukuSHqNarNfHWxB2BTThBxzNV8MyZmXmv6i4w09Vk+WQhPSibP4nThn9tv2Tk1HLbCnZEsMn3V3gnRoetVDw6okxDH/WHqjhJ3/6gDjvOflOE39yLwCQQQRJzEHpTkSHVUcsq1gS9YyUkg6CuguQcyv2WB5doRYaLmV0AoHEurlLjdMHNx2fcDWyIOFiJLAuAOeiHbVIO72ARgXp2q8iAHcjCwm0loyDhQ4AQdgCMUGkWqpdYDQkIihnTk4VFZCYFhJUpTsWZVeqAwEjtFqVrAVTOuGY2KzEGF1llQ9GMLwXxuEHvQygKBtUVXItIJoUibVrqOR8gGc4jaF99QmbDV1TlxoyYUMeXQN97LHmV27t+Jh8tadkfMIPVankmo6pNE6vfmbdyfnTdADUKbG+ChzUydzPpgLk431VgO/uUIBuFEAZdu2xWb6Gv6jRNhcsNoj3/AMn/AMHU/wCmCiAizOdAUhA/QJxcOC4aTgSL8g1BEgsNYtnrQhzVNLmCXLkIysI70VREmNANwiKySQtEGppDAAIgaFINGguQwOJADCIHao3DCIJiIkKtdFzYTEA3AZxSgq9U1Qxomrosl25JJdfCqEFzAhUJWcdyCAXiAg9aQFenKkwLXlqSQM3QBF6AFwCwjM7xagjR4ZdVuIagtBMgQCVe0jZ3gJKOuN8CoULT1Y3XdAhxk9iPhD+IPNVIY4RLJrbqmtft1qx58IzC8qmX7zXgTCcAlzp+o2EzlyBqtcy7nbxO4kiTfj8RxptwMZLe4Hyj8QSi7zH+Dl/hLy3/AEkDXqBCkymYn7EHN7uZLK+Qk6ppcWkC51FkS4NAclB29wEy8MEuCSO57+aDJwcARJIk6YNrPAJWhAYQZSbzgga7hSeoSOp4tmMDW60AhqJk7NTBOjoCYMksBibrYUBEgsYBDGrScXkFNJAhQUzNezIxUYmoIaKuem6oATHCRhDwF1mEBZkGYbM48gqyRXewuM1MBTQyUj0hwYWtoMGRgklJIgLGijcVX1JO2icYBnQ/q80TsOaFCanjIx5KKMS+mbz0Tc0OAhzdO2ByUxVyOoj4ThlmU4AHdJ0Wq3ye50OImHv3b5RnIYTyE4OnoFDYi+d08SG8PcowZSaYIYB7IgHJsMKhAGgyfz11U/8ACXlv+qvN1/GRcxyAYcuOE2iMSDS+N6dkYVYhVWF1dVVoCwVC7LO1vQgaSwmQI1xBkDoqkwC4gwG8xehYOgJxJkDmBRBcJbrqAD1D/NUMQWcgkCRt2jyFRiUCHEDQ7AHzICRUkVD58gNlAAwAjAlhh+TRbBTgIMlgQSd0MeqnpIJ0jASgebImEk1YHJ9Iam5TG5PMd6DuOUUZXMBtApZtWBNUIYBgpsnVA+H9x+IjV5Tvt0UbruvOyjZEmsR53Th6H9uEMDvdAUbeplc0zzQjs8mZLlxu8u/CwPyDz9nTixBwmpyvH2LpzKGo2QEddkFnGR6XAHbkmDNA2umAk1Prgqf8JeW/6WKjVaiHqDIZxOS9pvObVK7EkzyIQprQsCBECXOxXLYrBBmjFa4AIIE84EaCiJgkRQzWjBHTJOagXclxoTRy6NCwwkEDstczdk2RjAONMUCaIsOZFgNhoUnJnkYQBp0UtSoMJG90xhCMlnTkRCoBt1Z7hmZ3wCUzjaJLDLWpohDsClznbG2SXDjAPBptR2TBgxQfnRFTmhExlc0kqSNPZMnqAZTxR2GgQz4Kr41QgMZ8/qFG8K0Qel0XBBTup3ANh7XQc4duX8TkCjo6PNhA7D0HrB6fiA6CTbO4JhMmys6K9U/okIkK6AQEjLidtvW3+IvIPVYEcEcPOSP6fi0dUcjxsjh42RyPGyOR42RyPGy188l43irxiDHaox2oMHpQeDwHjE26EOQrwPhUABrg7KV0lnQ0cOcUGsRbgFkABJaLZCtIVNSERMCAw7TkdnCZBmexAM4e54GiJYMHBopBmg7jOZANZeQCBRLMtYLlJFlzsiClgAtK3a8GbHN0LIJVjaTdiJzwGVHMwCAPhy4JHYQUSwBADACLIDj2KdyAJIrQWFlpuYEBAnMDoYixtXKLqg7maAAX+FjROHQoAZIFwRQol9Ko1ESB4PKRJUKoBehILmaCcggWqUBmawyuZHUJwNAjSGATTVlUk0DdZ91pvGfHU1EdgsHwrQ7KO6n70UfXmV1ei8/EKnImWrbcw7lDPcIfwQz2IZ7EM9iaAuWQ7jJTwWuC1Ec3/wCdbKaEMIYQwhhDCCBAgQIECBAgQYQwggQIECBAgSpuiADiabmDlUE1OXBc74ryMK4wzWuCYjdRbJmAq4VICchgBzYCpUBEtQqTMoIq0pqsAq2hFodzkFTZIeDA4vYWbJM+QQRkLNMj7CByByBJAJFR0CRqhYkLqoAJUMIrYWJeBptRCajiEEZpij7KdwIMwAwAwFWFnCNiYmTjg70C1ig4KGQSecvZkTEicggNWxqMSpAVhA5SVJAAOAyXyVAhSQXCeqXY91DNc9qBd+AYXlzVXVw21heZ87L3c+ZWeyyEA7JgTgE9FIpbPZyF2TKFz2Ap3WCwWCwWCAWP0ICfZgabXtqgG6Ekj/aOEepz8fHXjrx1p3Qweq0TRBjuQwgx3IY7lp3LTuWncrTuWiaJp3LTuWnchjuQx3KGO5Q8KHhKD3ViEMQuazSWXIQ1hM5YkEEGJDo8EIxnAQ2YlO5AEku4NHfTogBS0jmEtvJp3JgFwAgwyrGEncgKTDMmCXuR/EI7IJcIUBpdkO6B6nRJcGQX+4KIcu7APcEO4VnlhciJLDkAQD03orCqrMpFtepSBwAA0lqAVDiKAgs4HmhaDhd07QHQ9ScSaoC0o5mCzJpEHZgMsplgRUckFUCGrWU3Nv7WE0D/AEKv6VwrUf5UTS2tEN3+PtT55Xg7brnwNQMiTAqY6iDsjkfCIC5tKdenWgshg9UMHqhg9UNUGCkCwArcynTSNHZXAE5Nv9IGSJrTLPspDDIkdR/nP+HdM/7PDRHuB7B5O8HYQjd+cOaSHILHAFqHcUJstVX1kbCZOIgq81CijoNAEAdzVtAmAwiQ4FDCzNIEfQUHIJ2aVSgRgCtEAio8gsHNAzAT0Af5UYqjUVs4QzlvMSmDMxqEHAzccj7KNWIABAg7WSyRDMYgEgX1JZxlwhMAAXPMixIZcCQsjnBGyM0BrKWqjAmidVvCMpwYAG5i5JEQa1E8ogxe4BNzRLKBqB7VQn+J3rIFJ7Jrnzzkvf8AvmEzuvGUdf1Wp5ji7AWmMwfJQFqAG2AhUWd/W6sUaeBMz6h2RJy1HQqCGhUTerFkUhgeahWhJ8hFIGh0bmuWxUDBJs4UPV4OiIhhGEAcI0IloRJYMehhbKQhUMRVx5g9afW5/wC3wG3untIMMtEo2CmZiZZzyTQGO19wqUExUWG61ihE8w02FYN00vUjLXGSGJZJoYGLAHrxQNc2EKpyXl+4n20KgEVDyxrB9mp1AAXDgCOWIdzIIFFAuXEAjVFKSaiTIrlb+0FkVTVBIWoa0I2EgWNwqSliHWaQmEEA0kEakuoYvwUXL5IKDpGbiLywSm4BpIVBDDNCBW0FtRdO6X2K7pyVMjWCV1KmlwquWfw15MmHnkBDBjRE/wBQ+90E1L3JwqoTc/agROaY9bEwCVGhMbo+Fk7sWKMx6ARMhGxNVXw9keQSDBkBKHJwnllCj6IIQIeQYuLMFGNkA2b5LuhcHaDo/ZJ9Sv8AgYf9vS9icCpxJCScRITcql3kDKu0ChohwAzUIfwy1WNRfVF/y+6u4klzi1Bc6AXKgyZAEi8rmJpwS7g7UilLdRMcUNIHIHOtsg5hhF6QsXaaAiCmSxUMnkDYqonNZXEfoRY52BJWCIci5qcgEuwIIL8gEBXLn1bTQ3AGTYgsZ4ezQkJABhQIOWTAANapOkI0DZXaRkrQFdUaudEeRiomo6FVfoojzCrMT+9CUwqeff5VlmTnICAzk+YUOgOKtB5aNkVheyXL4H+M70rnLLoSaq1EGeoUQMipOqOCQ6FGhAAHoqIgPkowcELuF5BQggSQwg4zhMAa94JeJKJSdER+qkN6oUvU52Tf9uuqmrKJdrmssSGbI7qLl2BBcwJJ+msKYmBEwCYCo9lSXdwpmwpkHQjcS+ADsas1QGc9SsUMftIMaBZi4DUpguDkq8hhdyzxzH0JqCxuXqMkHURZCbJ0FiFEoCQRAaAiCBuuyk3s4QCADNrs3pwBGykAoInrh0T0EjsCNsOFgLOipcgS5mYO6mXKYM4BKHIpKizARNACSug6yqoJw7oKlCrl0mFLjk+U8VhRy7H9Q+/NkBq6NoRWgBm8vZ1IUpzr6mJouo+FiRfmhb+SqDrRAcMFnuXooh1x1NZCIcLpAONChcCQLKyXT7YdtAKkIkXwsGGv3PRZSGMM6eLeqE5cJ4RwZNwJCse77X9H2v6vtf3/AGv7/vgD8CPyI/Ij8qPyq/Kr8qvwq/Gr8Cvxrc3bX+NX41fiV+BX4OFF+ThBFgWgjSNQul3ocjUB2BCC46pPVSDGg2SyvIbChmGFIlwBrU/0md4apAnQAINzdaAs1JnAlCaEu0GFMtYgUimSZaJEA52FjSBEiRgFYNmDW3YZOTopFZIFwNQWEsDWKJ1jFcWUBtho5TnO0E3I0oZk1CoKdqEyc3G7e6oAgOyMczcjJJd0WXMxG4UialgRBwIugvYjiASCZBgADxz16BbEYPNzk2jkXmDuJBsXWhY9yeaz2hMMDqq4m4iea/aTHqJ/Qn9X2sekpj0n7Q/QftMUzkwhlzjMj5WHSftYdB+1j0H7WPQftaen6iBESGov1NRMw487qEOw6aowJw0MUxui0nqDoR7q4OQOuCMB1i1mIYICg2Z1OUwmDTA/hkDPQUs2H/PVCk8J4ymDq2PfhTmP/C/+T3saCmuiII5gWkJa+JHBVNZgA0CRcMZOFikwZizOWQNLlksf0MaZTPD4nJoYZ7iQvQGZAwqG7xXiUKGOrMdRxjYKSWId6NuvA6umggxyoQZCBS4cJ3JAPQZnsH7QmoIaGfxW24yyskDBQQ+Sv0q2UTKX66DmT3Dq0Yg5o6hQ5sXyDAK4nGliezCATOQS55xcGuOgG7MnCgWWMSGV14dZUTf4BioC3V3SHcN62T3YhPoHZF2ohuRMmTSdE86h2MVhlkKLQxEMN9bMI5E4OLCM7LJgGqHKlvhB1KWMjH1f/GeDqGuUBsDn4CfnVNyTic/4zxbjHCOD/wCHRGMAvccQnaXLWlxB4/SKIkEFiGINRoyuTU4S0OQPUVJAY0SWLzY6hBg18sHORhblc9NDEQzHZ7gskou5y45HBoToMiDMjBOohRaAcA5oEkxDYZEJyDcaZAJYfkFAMazUcSYSTU4RLgBQZ2bFV7STfApxB5Vam+ChzYArDsCxwK6L9Y0Ah3kkwEuijkruNCzYRUJYk3mGBWwUZAlcEEvkERTvw6igKb/JYBYcQ2Mjsf8AAi/WnVCJFmrouIPZ3FFoyxDQQKuuE1YzTBKAZrapgy+1nFOQN9UJASObg+1nUR7MLRsbv6Z9TquHwoa5O2twZmzlf0j/AEg+inqrusGpq6CeDlhqagnlK6E7F4QSA2LwBqtzM0xIjgeJDNkqZ1HS+QC0SsKqkhIQXM3UyH2UUUocTROp6ZQn4ejw1UiqSmmHIztsygYM1SByG6ZpsiagLnECLLFIYKOsUNghnJXhJMtQ1WAJI1JIpUdJ0WJHat9TQp2LEiADZlgWY5HREHYwExbLar5ASog1sByJfa1eiiAkyxhnXeGYhayoCHtilDzXh1FHqL+hirKR2P3p7e3+GY2ovAsFt4KvG/Ug4aClDY1TwcBgTLBYH5QJEtVDcE5B3OMmuRhNDjA7mOD8emvpdQXMdUGFAvsqnk5ptbg7iH+rcH4R/lXdVd9EmuVAXZoOXDEuZJLDahO4uXguJhDQWlviqLnRxLBwLEHsrSSZhkQzwHl7qPypuajEo0ELRbwXGBF11U4vIgRgYWypuYgly152ErFLnQTMpAseoEo0uLFzLb5QIEsAS8HsSQxIxDaxWFC4DDYEY70BNU1C6SYaRUiolntwIG0mGFWkEI1Y64Bw2WXlj3DkDsCiuBgRAHjQsLhVC4A5EETMOTcJclAXT93+LFUWtYHKvrfoWOhQgtyXRJFzRAQHbZ0QBMPcIEyMOiGxlFzcFKgOHyfTXi/GS0Od1I5s7nXg4xTc0/wj1Om40/zYmDI0EGWvsoCaoqJOWYkESZhCN3gsKgWyc2WCVo1VS5JJ3qBZcsHC6V661Oj7GdyUEsHJEXAsQxhnTZk5Y1fWvns4C3MTAAExaNMKoOX0GqAtJyYTikmrgE2kFhMFBLSwhiM7ATMHeiQJMwkOIagUChVCSwQCEsGXnYogiRNjJRpLhPRmKoOzC0URqjAvDlySSxiYKaFHO8FCpYxssAAWBIJg8HV54doVF03v6n9IB1wx2BOtxHT1vrsqMX0T1F2ei1C1TpZOdIBSXs82QdSEzfbmnevKzGou9Menf+bJgMHM1QMMDlwpzPj/AAn/ACnjHpjjpsTdnaXdRWAAMCSBARAgSsgDZwGAmo77CtQCGA+soc3EGqkl+jEGekq7xDGGBeR3GqCAqkzgQx7YbRTUpnGMwXOdTfCA3gJ3PZlnkE0C5Am1BIiwxaDsyciQ5DBEz5hg7tKexkguYYMHd104sVsYQOm0hNaLk3AMkAkANmHoCIB2OTiSxDURIQGACDDGJESVFLi4nsapRamipu/O4027llGpLHJFQGcHD6LqHso7J2C8uno0cW4sVRNhBzUPqZckIcMURqyGGGUCYa3NIRBYt2Csg2kFSt3caLYYjOu/phTxcqC0vgm/oFenF5yP+E/5SeMf4bkFyIMtTqq2AbJ2Jgu4lOh4Z2DZHzEzCgADgGoPMw8yXkXgtBVG92JoFqg2wcLnd2FOuoQDqXAWF6YHo1eWqOQ7yC0AMGEQ2U+T0Nw5kzirtUgXAnTl5qAyZhXZ5C+rJgehcqOiwUiYLmoME4vRQAXAcxc0AKoGwRKi6SNSQ5GqGDBggINqnmExDliit230cRQCWm+5rlKCSMCA0DsDsr7qh1XQVNk/rLqE+iYg8Obm36/w15FDUfKhuQaqQSxy3sgaAj4ZF6z2RMBhIcX+An3vvnb/ABPFunyan3KZufurwZl4cr/8cnj2/wAIauRYVJjhTKe/PUjCXqtANCwLmGDctWDCYZoAvVz6EXFRIVmhFjlhuKA0YgBgDmVzzUEKrMztCAS8JpI7FFENyjkOadkFGJYnYMJci8J3Jk4KXXTA1VAJl2CRdLC0CphMK4w1GQwMasFU5ctEIcoLMdmpiwgwkRCIceVxiXTswDAxZqpYnOiyAiWioNuTVXRQH6SKxTEBgREHmnzQp0JgFdOVZNhNeHb7E8HUf4eb+jVzrbu3+BHAVu9UzXnZOJrlMajT4RO45wgBOnX1TwcnPNcqKXsO3sT1qZPB3Hev/tH/AAUb43QkiWYUTC2qK6qhrAs0CTmDhtlBB4YKAE2YMHRakOxAvhd8BUyosDBZUTciiCUASeID3E4oWf8ASk7Yaw8vqvcJglxZiktlTABsSlJiIB4EGhUUFi4IeNCZqFzFqGJpcmmCr7OmDTUPYsQDtmkwUUwaACThTMJXVRL6g0F515ObFJrA6jABBsQE8i9kztD1a8ty7HXFVQRsTqBYyfparPkGR4T4uoGifzo4l6R6b49uLgTN0UahLNpcH9D8OSIQIhMm0Q8t6nPBwvAFBdXK3ZMF35nDSB/F+8Wqn9DpvS3GR6G4H0uo5pja4dj7U6zRqkqHR7JT23Z7qbUOxBhqKW71C3R31JqXYGFFe/uflUkARPRMMjod08SE0RMXSl3CFUy9oJgDRFESbpETJmDG7SgLhiLn3Y5G6gTMZBDAnDBYhY51AIUYyxjI+4u4CiKGQBpJwbbsQrDdAyCw5NFFhM4DAVD/AA5IEWmoFzTUxd6oLvKgLwrH/G2I85cGPI4M5r3Hz6rekYRWQ/wOZQD+BVUsqUax4OHuvj0Omn+Y14yo4zwcym9FVHNAPqXuEz6P7lbdGHPoN15ci3NDkJlliEw7LV1bB+RezWyeAnUGBHqSyUAYFmzOAnqNwA6CmEmWXVFxYdAIgqZMSKheUDH3C5TEhcgGGnVzVl1QNQAOeQCYAUJCZWpNaSsXEBhA1PkDI+wxNhFuUg0VkoElqg81pODUEMggAwROx1U5L0Di0RtDhG8+w4HLd7FR/hIOY+uDl16Ki0yRy9c1xX06Fe3+FSnHlGwUjsHlc8dYRoFO3op6G9AN+MejPGeMben3VArvYTb+Kz6Tj1fOqDlp1H8JgL/f+pvDOFsAtVa+7CJirmcuN7JwZZm1Enb9W0sjYrozdAFYsZkvbWA4s0Jmu5ONWLCatjVut2iwMEEGh3TlidnkGgEXzMVR4YgsSLFBhzUpg7uBCCwIBbe41VHIL6hqAFtUasmqSHAxgyOvCPiigLtPyqekuMZ4yGV1HB4KnRODB4wv5wcmng/DCOF7+p0yNYfaYC9BOtTsP3gxi8XOvb3TcZ9V1TWJgdUbGrJyAHQiFpmpqbhn7pjqhuG2aiuwoOXbooDGJ3cQA04bkpAgB3PM6J7EG8IAbQa7K0WEFz43RyQIciByezDVEGmkuVNgxndkQFwCQxBNTjZPYwWDkuQSVVhVJD+d1DBIDtkDagsIZ2yYARDmkYMgaqDqmMgxvQ4+NVIH5C3VDlaXOtE65DFy3myfce4TjX7RCcufgC6bVQPt1TgNj50U71HJOpdSCcNWeo4VXkZrkn1ardWnqnLe5JryTHSW9ApEEeqJ5oOCrZcQEBqkBGEA1D2M6WLyWIpdVqDLktMrM6GsEAkANjABm5ErHyiNbVG4rZQ5Ko0+SLVDh2ESnZZCmkgORZQC1YqH390zSwopZqxJ2TuGIld7rcryvuUSLAIJtkmzlEYAlwgvTOqoRJEgWw6+06eBYnB/CdlVqbvxPk1JZMJBFh0YeJQDhJamlaJrzEF2rGtJTYIBgrrsTCAuJY0cEEy2EQQAuAg4cOH6qWUSwcDYqhA4MWBHNGDC2YWBYlNU0GpvVdhi6Fha3eaNPU8p02g+VyOua8YLR5mvGvoklXTcAYJHrZhoWKGwaAxYIlClVZDqlLJQAh2LsLuO7JkJJIKXNgG0RMu8xizEc2RdKq7exLBVRc5dhmrupRxkOJBquYZGgKEOlc9dkFURIGENBZ1Cw0gxlrk3KUBDnDT3yoCAoSCMu9JRDNS+CvM6KQsBMklu4rFWw+iBAJqdqm2E82EOBAtJ+EyZkfgJdMTkks908lz6Oag+EnVP4OGuvYqfC9U53IbQqbuKEqKz71F7k8ZXWly91yD9gXj7F2gdj9pjU8BNYbqC2lpVbooBZwBXJHPCdikbl2LrpqAx3eQPgpwUQTb3TkZmtH94PY91RhyYjWyciGSK/wBTuBxI21QoJIc3QAoZHMauiyALTRY3kqhLn5CIAZixxVLc+ifAQYFCu3NSPOYXfbUThzBgiud0TG25lXDKRqnJjMTaVQgRwSSBs5o+yiIgLDgACJY3fayYZDGTP0GLokBAPoo4ZrOAnYzAIaxuwRq0VisgKig9I5oPAAOLGsaIQGHYXOcRcBNBUqWG9YDWdzNQnmsEkAzijQ4ZRBoshWGqoSacmkjmNRQiIYsAxgYEaelyt75K3PkpwLJ3V4PFY6iamTueNkw9Q1uMkUCDyBzy6ETonAoS+hjmhAF3C4czhEARNtddE0VkQXnfN0HFg8mOm5QQGuIBLuU1pxZsnu2SjVHSapAZnFqXUQeckFwHWQjkDGgwHRJCQXem+xEhqAMVxd0RELBY9TZWE6WzXRXgM4kGeo7kSRgwaFo+wyOAAIdgDvDpndJiSbmQRIsEWIc0gIEBrVO5RQVih3RMZAOUtAEbQhc0BvumVMIeRW5RHVm76oHIYColQA4gyt0hDqs0FKf6O915sonoTcz+LqzoalQYuWbkHymLjoTkstynwN0JNRMJ0gpqnd4uCaWCTdxECHy8OF30wqKgNiUX0EQBh0XGRpXUm6cWFY1OLg4RAXJqLZTzTWLtqCmYMEyWlkCCRTDe5kTIgoRRmYoK9LtW6cxZZuIEVdUXdCAjEy4m+91bJLwNDsDWwgJcjY04ENZMNkIjCpMTAsHGRzKkeFoJHN4ujGVSZwuJDsmQZIUEDUB3MiIYzJqJCBu13USnMTAeXZAZrjj1MEZ1ZBdXEIL2TYJ3AxYAFcVQmGTMAYNAhYEA5IAYrIOVb7un0OgSMNm9QyLe9+KRUHqsi5JqZ4c2W1Hf0TvwfhZT0HAVsa3ozWlClyQGAaPNUJyHOeKkezdNBQS+AeKgvqgGgi1xllnb5Rxyfq5Yt4ycFY7FpN0YWRPA5MmJjp0TzgxVoOGHPkqCQkkgaAsBojBZUFRrOE83Z8SaDg0roiDgAWB1hyjOWLjcPsdHq0ynVlDZwcH3BSQk1gtg3uhLXgyXCBoLg5lDBDNUKCQ8KiRMgUzdEsQwGTJBJ5iUwJy4yTdg3BhJm0DX5QGo3OyYYnetXfimFFAUmXUHUHNqVTJeVB6ZQHEAUirFoFQYBrNx0UZMklm7oUloBrQlUPb2Cf8AhwHwvAqpy+cKJ2q4HYofwcBRO7D+yRpgubg0SB1KsNU1cuKQJY9lA3VDr8rSC5qgQSKH1z91QNImiPuSmOyLuQRssFk4ASS8nQg3O8dGUwKXyMRXVaBFXelUMdW1BlBzpzUMSIQD6d0AME4Pqna2E3hnLvcGtx7cAHWC4ycColAUmT3IkAk2cWvhAQyE4BeCxoAWT7VW+qAGoy6K4wYzlyYaJZDgJgCEuGEWupUBL3ABhAuZQQXp2N221JTgiJxCMZipqpFhiDKLCKnQEQSSOXIUZwXWcyHYAsGkP2QFmbIukY9mj0Ogctz8JyoZKYLvxcdVLDoD74wE+z0ymCk0wH6v6mAgb3UwiE2C2VzDLGSnkiyEzC3N0CAwAVOQywgN8JzCAlw6lsJyHmaQ70CI1UQoLH2YJM4unhIMWKGF5DcmTBaYwQg0AkMWCkms4M6ABQ8luGRZiMA1wgJXDDhiT3UQcNODVuAHmhLI9XCxQAEEtRSuZEkWajBqsnQkSI6V1UBydwLAEHoOim9qjsoHGiEjuA71mf1FzsDzYqzaiYBXVOVVVlFBlzlBjKSxarWRgLHtbwJxfYbhAAJYapJ0TgP59kbQy227BqJhgxEXqJEIjSsM9SzXWYlmgZB3iPogaBl04f5R5ByDIEmzOtP4iww9CEcmw7uZbld30g8w5gQDg0QA7anKBrM5lpMVBSN/lCR5N9w7IvGhRycpxxQz3HZQsBDGMAINk5NNlRp2ScaJwaZrNSL9VjFwSdZ2wpgd7Fw71LoAQkZPh0xAlWQCWZ9VNxY3koTF2jtwJgDDAguRvoh3BmOoWZv32+ME52mtmV+AkxWuCi75fAmwlq1TDATC8oJmtdPPDE8hL000KPovRAaTjdVMAVwtwmUDQaCOC4kPsl4VHiZhZ31D0DgPhFmeSAgSIhyQbK5CkyDRwaa+hydzXwnCyuxHsvbg+1TDf8OUwYcLZ9UFR5ZHBU5BIDXRJlIMBButNkU6DKwB1TgL46h8Jh2FhFAuw53KIQESRN7RuUWZzJQ2DwIaTFGJCalxLoExNlwBtq3QGXa6Zgc6oIPOBKQihzgXuhD6Q5k1gCoHugABAlgE8WbuKAQlStAOsIjBBYBAPlOZ70IZwi0BdPcC5D8xV4ToAlEAAU3MNrVTGEWAEmblsD6TsEBCDWm/VFxGZZgKxXHuhDTQzXmWHeU3IOBkmebKrJatEALmpJZ7U6os2IbQIZdhrzQblFZ1U3a905QwCwz5CcGA7gXE4Ux/DlEcRAygSQWNkTrTemmqIaIkxoRqx+EzDBDnc3UouHR3E32lATugS0I53gq4ZIYHCIaoEEgvYLuC7vlEEalwNu0qoXYMVV0KORhvkqWEA4g1Bx3ugTdiRD5IFgfFyAlCQLTLoBIuTgGonkiC0yOxDZhAAdGuGPdNsFjPB+XTk/rqYWXZ6LgshruQG8AKl90MAZN+YGsuVvUiFVByKOFcyRIJdmyAX8ZJbKvfmmDEyCCOps60ZMURF623G108JkMJ8BkW5oyoAADYOBdum7CzbBBrjEqoBxRnITE6GULsJyWNQAXIQgHaGEEoFodCpsBCKi5uH4upDunc/wCLdk1wbNvHQeDkOMvyV/SxaJhMYPKYDtZozpwAhgSOyDDMQEuyOhT9EJb6G7OhGFaxgiwieqz0jgMeZydPTHGh2yA1NuSzCiAOGq5pgXcZnLaoQLQgBh+zUqhtGLhrAs3pCcZ1nURcMGqIRiBDEWL62RjqpiRBYEZMPDT9qDMmQFKuDshEWwCXpMi/UWRKNgMu5HJFjSHOrYZQJQCDSYQeA/63NQDm+AMBugMHAByRuBQMEcM5qJzBrc6ujJQkKGNSluaMgA2gofZUxfCWeTZOTQ91hARILiXaN8lMPM/WCgQIpZjkN0DAPFoQsCZMLMygvXJhmP8AE4kzAMASBuiwmpUnxkwXlznV0DhnEAfKBoaXfVQS4u1DGyEGEQq8Qa6ENlOsJ3MScPeLBDBBoQBByYElECUAAXdju26BxyCTFB33UChAAsb605KHJNuPsnfIITRmDhOiOUlyXuBCG4wBoAkj2VrICQWYVa0+6m0CCSLEiRupgYiKGHsXhBg4RYldusFrogqYhjVy0VYc1XEAmCoTJQyJiINH9V2RGnCZQCkBFQeVVC2QeitZ3hQiYACwgsYEmWhCEdhwO9ScKMgeU9wA0JVWRoFkB2itUwoAIBdkk5LQyEs4UYNjlAJSwuQYBeGNSikSSpZSahOEDIuC7tJiEMJDAqFwcrpjZxMrSf1BIUhACZmJEkbugeeDg7qGL01TwCnLsFEHUqMbIuTAzmGrxcqD/AUAawQg+k/eAAlQAnojJvI7ngwT+mU7ZFQqXBihgAC0Fw5Rg4sLOWDqacoRGsC5gYTYx1TgF5diOoyJQhxrJuaw+084QzgGIoZRgAh3AsBaj9ExDhzc0NMCj4xVAajYBYhgWAT0WXJFSXiuqhhCaOM1BuwRA4NAAElrm27ugANHILjyzAyiFzMBmbZ2oigGByIO2Vg90RE5AgA6mWGfpTmBvIaAa6umKMgu2A1u1WdEVTMtiXpKlUD7upNn6og3dLuLgqERfqiJskGIhQszlAPfMZBPwEX6gKAXE6vhscAW5rXFJHsMIvgxXFyQ3kpxOURPygw7sDG9VFpZhw+uqDXMC3MHY6KKUwHLnjNUzwwCsKIkgRHPogwfaipfRAAkSYIEQ5wgBc0tcCE0l25tt5hNEHBhJdtkaFBfRvlOCVLkO13CdgOgypNYKoJkPSyjyXeUHAmhMGcVqMIHBznkPqaEQgqlizna6IcAFJYhrtt1RfwMAsuMWayZAlbNy9sCyKuqSU3DagQBaQJBFQCxHL6FWcOCNBnwUw2LuvexDvtRAlaggE63LS8gFEhFCgAoCRBRO9QPBsBr00IEiRoKtRZV6ZTNJYPczmTSqDZyJ0FpcUAxyQG6qEHFGiMBlQGBziobi9dQjLJXuLgZBI7QmNEZIgWZqP4ix2RCyQawhkSCMbNpeSo6ULtZAWoECSByCGvWsI6IjaBYGKXN9LIGQuB3FwwEwicDh3Zua878ZMpzlGwTMHXNePdPC54l8wiQt8qEABCcs1LXTh6cL4TwJ0GEWQAIsCgBQJcSSGFrMKlhVAUFGBO0bPYGIVOBnRS9n23lEAHENcLsJAZCAThI9wc0zIgkCXg3w/snIgA1zXXN9E0KlAhFrHKezhMBBJaBA7qQGatQmSXgNLpwCXVM2NRCIcNbWKgYJItKAwjABy9SMBkTIDoEHMbk9giZkDOZhlSRCpZgtfZRk8YaHMGHUkog4kBmgXO7wjZqNWGe6CEw0Pj8og206tpMoTOQB7pk/CABkS5Y59lPL9Q2Y6J+xNDvdYKRiTmciWCdVAHo/EMF4w5BOqcVE1BHM/qIFmWssPZC0AENC72IheHU3+UIBi7coXIYrTKd2FaWVBya2FQUbYEXcQCDmITaADhCDgjUQWcOYW5NkjdKNAZ9kCMwAmhwRWQvG6odUQDuyzCBuihwa4JZz5qm8oAdwoUqMwMEEO9HyUATpkK0KPAnuTJFk/CLwSEEgsGBiz6QEcFrAAsMjFU5OAAPUQzQQLoASLCzDX2Mg2LkwQDNFKtJEDLACXhlBUBBpuSSQqah1AAMAlaEGjZANBUzBYSgbm6e7L5Duqz2buhThgGIBDe8RunwIwqXudkRzMj7u5u06IyJqQdSK3+EemAzbJLSdyoDICJNdjFUTpGru1BrHCIJVE1D5Th0WMmgFtH5nREFUYKbQ/NSvBDkwuFTnfiMGF4VPYc0zFAndVTwwDs8Mp+D8XohOpVPB1Vl0EOZiWAGTITpDhIgAzjKuoiEB+8onBhDknFbGZsBSNHZgBlz3KcUHUDB5GblD1cvEFgx1qyBoQHAJJkBIFAkwEE0icgSxwTJLNRBxAOABghsCv6JBgCEmDV1ZMRnMRYS+xYR46YyVwGYQ90UALpIABi8OXgNtJQQSQYLHZpXQQpdpTskVYOtIgC1Lwd3yUVKQ6KQFQgqJSLHdKNKrGQBrl4qXohAMhLWP7uEAEExAbBLoGQGWMsIq6+gXMwYGUYAz7JoniQdgY70ATkcC9gf3EsszU5aLAEASRajDR9qgQhjAdteXMpwdEtWsyYFhzoOUCYEOILRn+lRIegk8zDLcIPIv5RAnJAYmoVbAer8lrU0/aa4XPZOQMz+6ERhj1TtFqCVNVBDXytQAuYqaE+AZ9RnVOWQEikc1E7syoTpC63yiSgQ+wPzUoQINcapRBJSaA3PPsg9gDNJAqcIED6EPG70siRiwvAsXoPtQAFgxZ5McoQI8ZHkImApExqEhlFTkI0lGDiBcNFToEaoQEJYnwBXPZWdGBBoS8XrSZTSTFrM5AV6BPswkgHL2MGq10DBDZLKFiwMN6ommoAQJmnRQROEh3JcSfSKRAIKgDLsNapocAyi2SpxzcUcDXkikNRWOepE2WokLwBlnY2kwjbLm4BtxYHco1sgWTUPYNAgF4lBic4FoPBg+U6bQ+0HHQX+CdybueqlPtUw3QION+EcCUBOOFlCrAYFhGUKBgB1IwIdFiBcEtJwRYHkNlRCgGM90pgAVjldeCDDogQaXmtelNUXj70NAHhlUaxySw5MFMsREC57jEIIgkCHuuVaSGsEbxQIBDdiKoyATFmgHsJzVG4DKLjBYCSiDsZzqC8lPuU0iMpdphHOLiSLnBcgsTikQEWLnYk+yJJcmXw0DZtzM4QIhGAOEagKoygkWSMq0wOaLsYBIYuDmrUZEBlJSHaAJrylAM4YKzYk70ZlAIvS5cIAaNVSGAxd5JMkdPHQJMTLCBjUoN2TjlQMhEuUJE87aBMLQA6iADcl/AiG2MGlRQl8miYJE1YW5ZZAIJDg9QsROE3vLD5+UAMGDgAC1XsiRIYSDZCLnCSg3TBoBvr3UBDA6cgpULnZ1JJNSmEbhk5H8IpEiQz7KoQdJDAJhVOWb3IljAMTIu3bZEG9zB7754ZbRF9RAAqDWVCxhYrbx04AAEokWMeyJeEDnXYe21VLaRZoHJaiAoEEDHKQCAgEySzOHelpVAvAbACKXIgENJIwXc7tDpsBMAqJsmJCcBmkJJUe1NAoGB+7UVFjVDG0CGbmqebF0WGAMQwRja7UZO5Ew0Bi8YeiCxEG1JFFY5oNhZ7pqn4XQcM6HJo5EiD4EC8OLTIPMqgteG2TIArhl0RBrFTJvkZIbB9u6DNTCL0OCCc3Vc9BxByaT2shF4ZMdlTlzqiC1Gkbkl05UthvwW7/AMA4s2BPhYe67qnCnpdOHXomASOBAD3dEAgUE4D6QniFgviYQ8umpRkDwwTBRAQRwzxA5XKAYYJiKiWNzAITHBc2fBFslhDmxjh8JgAQHIDTs9JKkeQhqQPQ6IUQGJMUmw1TBRLCxm0lTdCzgFnALOHad2EIQ4NZVQXqmowC6DUeZG5QRMIRV4RCbAGDwFM3D3RLM5LdQUoVIiwveZrhDUHAAB5aJsjmArZ7OQDYJMwcmTryRgAgnJNWD5MBCZo9jP7opNmCSAgHGjoIgG3y7FGcKkLYCdCIgJwm4B9aI0qAWWJPwAnw8CD4fJUYMMt30yByVFHI0YRIUCJyVoZlcSStoiWEACkDU/CIMBakZTiHAmS1jumjMFzqDRGYtvhGp8DJjC0wyuY5yEHOAmE0rycRRkXmEAyHlqURa3RZS5k/ImKPC7qKy0DLJsGsamxbtCAAAIExkmIX0KjSYkXXshHti61ABAd70RGAYZDVIoNUxAQlpuD0GyL62EwZQqIgg+DDghQgfKcuOZJ3WJZtqYQjDkDN0CudES7gLgsxlQh61RFRBpQRXJEOmX5IQBzxFm7oAD0IBdg5DMhAOBQypq0AViLm08sIUI5HlQ0tvkIJADDVGwkhmRggHsXRUSH3BAExiDNzlFlIQwAAihdVyEHLJhoUNi0y8qNkRzECxtQbcENvcmbBLl+rUPa3AAEmgcnki4qmS5/Q9FdFdPxYJgWwT6jckyRNoqg55rmwX+WERBSyZBNsGRQTCgkOcPUtsquJhkayEb3RLdgh3LkGBIZThBZLZBmDuwVsciBVFAmoqJSJS7XNEIwiE4FtC8lq4TLl3S9zhDaIy1Q6LjariBKdQmpgVuI+VUpIRwpme9FAGhA0VdBEv5RYkAS9W3E6pw0HJaiXdMaiD0nNWy9FGAMDQOQVQEyZAQa3HTRAsKzE4i9LCyBEMAyERooJNEEZI5hEmkiwRELGNUkxhi+gCIg3vJK4hUkmiBBzdgGt7p6SDUhGA9JxVGsgjEgB7CxlCBvhAaAmLM5PZEOgFEOuMDTUjmTzAOR7MLKoO4lzOLVrogGpDRNeSJKbxHdBIDd+hZFgCWLxgQJRqtSvVSkjBpvVRG4HBDdTyiTQZ2Z3QYYKuCAWr2UlANRxZOQHBkAmeQsjpd5RrEzY4owiCEOUVoZtV6cDlMwYMDEMKl2lAkTc1EGpAorIeBusp7qSMzPANltfZ1MgMZdXcV2pqiERamCjewTLhIEM0pDzQZRaSwgLAJXGcq1GGBAzuHtzVEFUwAE0ZOJ1TNpgRMutgYQcHSEXOEkltNynNaGLJ61YAl6qUtMGQMQQxeUQSJA8ahhrU3UeOm0aNDVMoXRSJrr0GcJ0TXsjREwCaEUlFGVsQniQAlgCQGVJAa24RR1nsUbEAZsnojqx0DdE4MmBoImijvSSgLxByIvUihNtFylIapw3PgqoZp6h7txZMnC6KODng3d1RAYTWM2AGEIAGKs4RtjtCARaAjoiMphbgsbykhzVYQE8ygg17OJ1QkZ6bighyfZDGAWYkLj7RLZXFUi3yIjihZOAOzYdsaqO+GCq/QIsMICD2AOA6AMIzgmLs4jc/ScFQOXUeo2DoiEsZJQKpdsoT0QoDDqDVRsHODEMg0jkgAHDBBHINTPNQtpxg7UlwigMhBtXiW0XTSAlwa0CdxKIgcBUBFW5A5JoEMEMAx3gJCOvQgwyRyHNMIeBxIcQQNPaycAkIUglnN0aALlxiHt4ZAIAkuQRBHNFgiCEhPXEzWwmikGVvYcT2CZ0zRoJZ1A9yyIbHyjXw6MVRphcwY+EYGpBZmzoncUJMCwY3W0Y1IB46JuAAAAzTHVEskFoqPhAD1xBI5DKA0ANDckJBQB5hx8LAMAzuUyqahBpzuieAObDbsmAAODSGGuqJAtEBZxRqsSZ4MiXGpJTHkhVConIvtZBAJ3OH4i5y5i4wIoN7I68YSBawFLJxltIOQSEsXvKcmoF8UPoUTOYMMbMKjwNkMMnifDvL6jCIjEnJLA7ACs/ZF1hVzuOBZn1ZTbdXOIliiJDbMMF3dhOhhGQQNZeahwe9OaKISQargWO84Mo5cKoSTJPSLo0kUkDIsxzZFE2llRlhXKAnhA2fKII5OC26BJcJYIBS8iC9CEQcEFRUsiZFhNQiWAjsKIlwBSNA1HsZNRNnk40DlVGwqGFcOdsUxzFOw+LqjSA4vrdhXuo4MAMSdVPBy3COFvJRYN8VhAVQgaDBDbIMwLd3g7y6qjVE0Dg0GdOM6zBg3bsWarCN5mHOixVDCQLsRclDhdgGv1fo10aKysTaLiwKiAaIAGQHLn5YVcCwNR5lR0CkAgCkBlTKZFUICV4+UBR4okuXi+/NOSCYuAkSSTRlMAbNSRnES+So3epk+QIn7EkuL2GVuyWgwG65wgBgBB7nrYBLkEIAgDIy1SzhBdInqHf+lAhm2O5mN4FVDIA4l6LnDoJwAAJAjs6sqG0MhBrjdEOVnHUBlz0RclWOo1YRLPMsxYhxJ2RkIudAObFV0T3rtms7aSmkEAAQ1JFuap4XSBW1CVXrYVrAlqXVIC5gcOdkbJp6gSQ7uLDunoJFnYZP0o0srWkoiQAIcQYuSUDuYB40FycAVASmM5Byv7qAZRcWqSgQBM/ORoiQU3jwIQsC7mjQDKIYgAC9HGE46CZAkmNR2NUQoVQdgHuLOiOkFVMp0T5QZSQJBKg2ROwy7mvseqgh8ELFqwoqCcLPVcgkiaMqWeSdEwdolGABAEuHU4QUBoEuIQMwDvK8ojamhIICY3IoEIAsAxGJB9Sk9BMyenKCoQ7kFHL0IONkIKshjFoN9QgFEQwAmIMgM0XTgQWIHUwQDzV1MuL9Jk6oJO5EyAtAa6fcp1UGqMA0BEudUHGDETA8q9EEQUEYYVvRNx3NchAMoOGUNcQpeA9rod2mAgZS+sQq5JnGMhTdAfaYE3q+uL6A5+AnqVbD1RCDiARUZb6RiYTxJFpMwVVPDug2MIEA8nEQNQoMJoyjOlnQJgOSpsJg0xpjZzv8IgABcwjlghnVAcUi4zy1A+GZE3YuYFGGq1nQiZsSHJNuaIygZBF6jAA7LZIBuaQ+rZKFhYDYAmyT1EouwsJc+SIOAKaVGiJlOcAOAUh6WDdAm2D1FpgElnYWZkKTINJONIUEKVhLAXZBMEG56DDVEIoAEgl4h1mGRgymFRBPs0lOCwmAzhAbnlGzoEaDMnlM7wFzJAPGFfNKPRqTGqI11j5KLgSNROFYaNdO2IwFybmM0ZO1IA5owUYGpKLlwHI7YZaAjKlzkTUwFOWEeYYhouSk5ldQ7JuWsgJVwAC00E4QAxBDNneBSI0QjIweQ/6sDg6VUYEF0u2qEachrOO6AzAJjqhXdCSQaSQjCiL3iCgiE8AoehEi7Jp2GEGSBsdPkO2htWfC2Ah9irE7eEBgJeqAAQQJ3gJDiUEQAGR0hIIDgM2EKWADCCAEEVAUwjgLhMjajYOhQAs5A4CepZqIKgEKGB1dUFkhqCBjBhhQoQRAILwQZs1KExnVpDOr4aE+0NgsBVm7lzqpp1jTDqDIRJUAg1IS+TG7onAC3ISHSw2icmXCoskzBlBE7DcjhIA7j0QEO1e4qwKQ0JoApONhDXwjrIgkgzgDgSp5/TLgu9BFTiyIXXDOMVcE3MT51ORZUswDYiyXmYYREk68lFXgosaHFSIu0OKlmQTP9bU5CWTzHA2T9g6YMNkzFAnc8cFLuaduDcG5J24sp2nh5kIzAgOge18B049EzGQalklGAtzk1aAvGqakD3B0KMZQtkA4Ng3ztlPSASzRmvc6eG7FGHoWnyqI3g7rdjvuDJvCcGbiw3PJMncCBjfLEXpn6DB4VXcOHmVGELwFKgAEBZ3dE1iERxmQVVtEUggEADA6MlmroeVkCq0NFB7qTceakGx9ogSZ0ZESca9E+xN3MAAhgM80AAdXAjs0lAQUSWqpFYViQLfQMNMosmIgCAAwYbG6LigLQLo1ZJMAbBxgfKBnAhzLB2g8tUzbXcEsFByXwI/wnsMwdAGZJD2RAleXJcEGheymXGqSTgAy1URwMFQZMmBpqiUzABsn3oUM0Wq73k6KqA91TO0/AUqEnVMcnXZNA1129kCAghwEkWrlE8hNSGlNyoANhcTjBAATjURzhPuSGhWioTHtGixQth2Cwu5dASG1UR9BDwqO7hzQEaJzFpYQCa9lFg7BgppyRJOy4nvpOqu1EHYCyXEk7SAXgEMNGAbYCQMzewoOACxm5nNC5pyusJDI0eBVOwBY5hsAXqCVcWYHGdSZZQAejYtnKtC4AlU4CZfsVKQEQTLQCJeyPQGZ2ETcfBFGTEgZzMroD1ZC4iEGBkFxBmJdtESYVkDUkKBApRARINCEu5o0GckXQsm6gTlEsCYJcALi5PpAB1V+iCixwFCBSzoQHDkAIEVEyCgoIUc4vYICo1UBgAYQNIeMMikg4wPXJsBmEI/KNRA8kMxsgUOg4WgoyxO2v7yw7AXmiBHAIYZ03kEYugBydhhVQsNCHiyDiaD3Tic8M0qU8l78rduD8LZ4Nz4U4jZWQQNFiDiyRDc07We1nG3ZMXRM0lihJQFYMkBaX904sROALPHyUhAAmc9mMhoCkxyctmNE1pCd1h3oBchMcgZABhJF5MkokNxg5c1xTVAAEBVpZR8NkAhyRTom/yhbk0mT4YoU6MFAODjQaIgmZgEXe8BFEiSIgSwvR+5WRSTI4NzhlMkIBAQFmbCBoiDlZqAAjCcEAIyeWBTZCB7wa1AXk7BAmEkuadgCsqC2iAhmAyScoEaYAHZrPyjFpgkwGp3QisDgwdANAHuQiDQsDzqiFXvJiI7WUpEGKYNYfKFUBR4YsEmNUxBPAI2poCBwpbYGNg0fCcgHrkiS8MIvEcmHZ3191UXPoc2OIughAyCBqlzV1LJsAuIwPlHMPbmKYYRru1KMiBiQ1Hu00UA6g8gDamiKSWEmteSIgNPAcmG6JQMcDkUHyUQNBg72v1RhEAxc+FKeCWNqHXcKF0EVGpg+s2Ty9wBNDI0sKgG7Q7poGWrcpD2yjYSBBFDgGPZPiDipAPwkp8EgcNU0JswQqA1HENYFVYBMOexdB2ChxGg8LQimqZEJklBaRRBISODoDdQ5RkmC/VGcG6AcDDMRRrA5CJgtgJRcUYj6TIMYz3c64MiAEuDpLnALQxR12shziJYiRREJESDRY6A2lMUaEBZW1vugbCISGDBlVBR5hruyrhpdVIw7VEFfc6OHEtDiSWOlkUaaAwyTqhqLICb5cACIyQQ7z2UwOZAnpQCWYoyokoGEvIgy6DgQEiAA0dwl5qmHVPFtduQmVCpwqp+ivCOiZGR3KYAYCYAYvl1SGsGTqiBaTmWQMJ2Bg3LC3ZClC4yLuClABEJMq2AwiVDZAQDkxfZqqEBx1kDMvKFuABmg7yooATCsdbJwBEmwAbQtUfNPVOZgEtsi+5sLB8J+45IkOAMMmCBkYyNGVkHHspAl9kJSGgaavpOBl7IsTmEA0d3VNAEjdkCOlkGSASAy7KobAwSdidZRRwGlEsSKYVKAzMLTD77rAEoiFBgCDEALMG1J7botEIgRJc1oLCjJwOwB2Q7oMZYa1U7FwfITnKrzICLgTJE6FNxL5IclPJh0G+5zVa518A/SYYm41rTI7AXc7MmEAhSBuSIRIwKtUxEtVmNUJ0FxT5K5IUHkHAAtQoAcRIOXOXh9LwgMyMF5EmAayKbIqlyHrVAnLmEHLUujLmIJ2PMoCEXQdG2iclxlxDkm+UGEiZw/JBEKhqAxCmXAQBYCGxbRGkC0BJyQTS7ozHMMFzx6bwnXkOYioNMpg0FgEHpqpnXMW+GQpHwEs1UF8p0sCEEBSRo0o1s4Fgqk17oGYINiaNY3UDEBg4ZJljlB3SzhWCXyhF92Q7OKCHoir4hUHJEuoFE2BEIy6kAcozgmQTLku8KcF3ayAOgopYDsgRc3hRhgO2STu2ZF4mMcQ20hFZACBiWC//EACwRAAIBAgUCBgMBAQEBAAAAAAABERAhIDFBUWFxkTBAgaGx8MHR4fFQYJD/2gAIAQIRAz8h/wDiBD63xcY+Dg4ODg4OPITA5OWcnJyQs2WwSj2j+0jzr2FsiH4GxakuKWj7GZM9LF3QiOuH70y8jZs/Z+BejbcMSfkWSZGnMYeRNZihXFuJMnX2diH1J4Lu5HwvvSTKVt29424MnKfovJ3jT5aErpjUiXwKPupEEXxSCEIuixarLk3FkWSWb+2pFlYimXkdH2D5MftRW60aF+IiketCBX7nYE9Vv0X9rl08jCZk9vY8scJ8otd5GyM5otuRjLVlF3kbiWelkunlLM9ifYlLDBOEhlpYn5rJ32Pr5usy/VNfot0w2pfCdwhEUIJJ8Cy6Yn4cbv6XVtUXQvWzkSC/0N/Qtn3OBNlJI4ODg4ImxwPY4LpxkJ6u9YOKulOBbC2FscHAtjg4EKnFYUl3KnuWVs4r1OtWMYx+HAkQhCORbnODk5ORbnJzSzLrlfB8PCY6cHHiWpmRej0LqNzXUy2HnFsDEsydaWHs/LPhglYb+RtRKC1okri/ItaotfNkSuQnBZYG3wXurHQnvT4nuaPh8Vs/QaiBtpdBb1viusG6fHJGeK1LyToQyJxStD15FYu9hWcQ9G5Lc2nQtgzNgh9Cljl1HwrZ+hZetBmOC3HsXM63IZddcGnYnVnPcs1nYv8AmtqNUYdrk5myJEpPKPcmWWWBNRNGu21LH5fg+FfY+Sy9SwfI+zgh+aZia5JHsMsJe9FmJLLLfUbLb78GbWVLKinRLXuIjMkESzkyS0EnJaty8jdmOaIaZdX4PhXsL5LL1LofKhhtTOt/QywHoRyJ+fwTZDGTnT3I6nY+mRAyyosiL+ov8oUSux0EspNcpIzLGdZlHsQ7a0vW7giH0sfCli3R+Szqy69D5UHYTLgsI5Ia6XJaO4XOpLjkS4zsWT3M3MesXGtbZQSskaHlFpZHkWXSpNDaLShDYUwMtL1J9Tfg+FLFuksurPYj5HYEprgsYrocuw9iDPeBJDf8M8p9US+qtt/rI6JsXJvQlxsJJLYsqZs1CZ0GmkRM5mViWl2EoGRnhVouzc+4mrJfQ/lnwJo0rDoe5uN4UbhuZuG5m5m8bxvm8QjN9dyGnIc5n3FHzf7oO6an7cUmjZWpZUiSzcaVl6mWZL7wJSefA1iHhTLxEi017E974S2FsLYWwthCEIQhCEIkSy2JXAkQulHuJ/D/AA3zmllSDSyMfuiECSlriddSHdnqMnOFkORNc0sX427W8oyHsUd3aNhuNiBkmiy6UTTqz3Be5a+glYs9RQ3mL8EwuxZVzMknnoa6ja7oy6lp3lj8mi5rrS33kyvp94rZUjWlyZ15GKsWaQiTt0LKuZwAr6DWGtTPp7uxCeVzrc1abfwal/IhlqTSbEOBr3HdZubCyLKuYkfsWx6mUPrSY5fsvEcOS7bqvBh8FqRcWZ0Ek10LKmaboSfYx5hE4RE7noqsq5kRWRnqXh9yYJ7HiQ3K4nl5oT8AmrKJNWxPgixmbLm6ucdBxuN0nQhwWVc6Rvkmaja7eXBBeDJH37+iSR7kkGawwTHAsVqRfbTcW1CFa63JElyRob0wQmQWzFAssxZF4SS+/Yr79MhEpyBTbxFZa0az2G/UTX7isFJORI8564ZZCU9jJ+D/AHZf07Ez1dbWq/JmhZA83ix6fwWuQ7FrZrQje05C3EoItA3mbCeWGNRieizJt4M/hUu+r8n6yRn0J9TNGWY3fJaUujITWQ8qzLKtmSItkOLX8O/V5O7cL2L+jJSomkiELEmR4d+p+PJ2fqXX3Mt5m/W/FYTZY4VbvCo4NyPAnifyZFvK3wfdxW7qhkvpbgYxokKEh+g6WdGSRiVIGOjGMYxjGMYx474Pr4r70LYW3uLb3wS8iDTe8/8AAvgz++Q9nS/0xQzgTYvPXPc2mz2/pmSzv39SbBD5t5kaEzebZHPccrucruc9xyF816OawxjGM2Gw2G02m02lnvBqbsf4DLEcjKfE/DHua2upSf4QP+BphdERdbmjK3o6e5/i4xZ+qzNn3NVe4ncVStYFWxGwWwthbDafgXJyzlnLOWR4cW8Fkw9VItnn9GJ5PR2+bDWaFsSOgteVIZUumtBjo/KwmZvCVDyt0zQx84JSh7se7HydTrRbC2FsLY0Dc3CpJBsWwthbC2FthsbMVVbTabTabDYbDZQ2Gw2Gw2Gw2Gw2m02m02kXauPE3YfbR9M+mfTxlbgkz8zHgWWAhYb1z/4FyWIggMxrDeufjt0Yx7VdNPAuXmrT1RJLw3rn40DGMdGEEWt4FiE67k4reSnwbLwMjuoho0xWwZ+XsvXwLkBPDt4Gfi28Kyx3JdIGb+Hn5eyx5l6cEiH/AMGssdmZ19DpNGry8FeWsumOxaiN8nkR5mPBsvDsLJ47+by8T7qRq11F11g2efywMvclYlJ4o/GqNfv38jXgSxbC2FscHBwjhHC7HCOEcI4XY4XhWQiYJyas6dqykyYBC2r9yPuRvfbYj9eB7+Bfx7Fh7nglEq3/ABhmhrwJ8e/g2LT3PBJG+cX+Gev3cWy/OPXzFi0u64ZUk8Vu1Z/4dkWFn1wwZD9SsCYnr4S8vYtM8NyB4XubjdihdcMnNeUc+O2kW9SQxjGhtkywPar8Nj1Vzjp+TZcI9/wdN+41tZDvbZHyflkL0HEj8Cw91HB+yPu59+Dj/SDI6Phm/wB2H6/k/n5PvB65dtDT0eHXFkZKeT2lnsjnJJdx/gnv8Exd6s50mj8HQfg+Scs8Vl0LHwPY/R8D+7o/aGepn0Z+t+hLiXf5H3+VmP8AnyfeNTPhbn+4dMNyT9Iz4tt99yfVxmddXnsZdz4dzLo7GfRGZLyyjQ0M76nzSXbU5FqbD2ID3EMe6PvQ9z9nW3wxrXgd56epMWzP16k/dTnpxubdf2T+Of8AMckZ0iRL8mTPU9M3c+CNMl8kTbSDpaHcV76IV76oT11gzvsZ9UT6wPkXufZHTOmfdHukuF7zYz4FPT4ZaH69ND9fot1t+ifuxOfflHvcXKf5J1/3U+8o97+upNfesE50iJXNxR1+BP4PmEZ8uBe6S9DO+b++gr2vJL9TPqfUE6622LPqZ3eYp9f2c6kTTP8AZ8GXQ/JYewy7HxGZ7qOxPqi31kP79zG9ef2aE/PqifUe8fwna4vu+C/TFr9kyvktj9mXqz5MysO338jlZZycM5MtLltM/Ud8szOIzjoO+VmZ9UZ5Zmft99TPodMjIy67iPcQ30FfiIM+HKOlrnTc5yyP2P8AJ96028XTkV7MmfsHwRcZrg9grZbmXQ+Zl1Yo9b/ZOGc/bnVrsZ+hxoK/RCn0FbK6gsEu4rou9D2E/dq5TVz5CDK5l1+8kJ2GfMDvOlh34R8bZl9MvvqS+iy5Pmc5vYWozcPsCvdZCvk7C30Jac52OxkbZ0X0uvdDtusyNEr5o9q+vkuPWmZFvtyy9X2Mj3ZnyZ+gttDa1joGkGxGfRHujJ8GVjIietHujI+TPmslvxX3x//aAAgBAxMDPyH/AAxpK4FwLgXAuBcCbiDLo4qhCFRXLYYXYGXRxsYY6ckCcJtfA01gbbBwHxZBrs8fzQh9OSCVZAMdJNxBhP46UjE15ItJpPxYYMVxsZJ+76dB0yyUQTfQ6j20KT/w1tkiucEImVwnYZ3LPSwY9Is9VdBUxqQaGLHk8ketZ9TESebJEIXJhrkh61k81+57nk8nk8nk8nk8nkdqJMIxYVF1VdIgYx3O7weBmT7mY6DGMYxjGMYxjGMY9g7WDFZvj0FwjweEeESnje4GGYsmRRbpSK4e0mbs1wMfBi3D+TQUT7kU0rgkxagkizNYGYGrsXsfBiuV80w/k0MvkmjQhkmDW89UToNOuaTTFV08jDMVyjJj6mhl8kpqmlcGtxKPYLRakLJjBKM3TfgmkUyvYx8GK5Rk1+TQw/kyQzSuprQXBwIpJ4JaZpH/AIYM3LoKiGYoxXNGpoYfyQzKJgYxjIDCsggS36kYJ8eCDNrIR4pEXTVP0MP3sJiEIWaXAQhCFwcDgjgjgiHjQTw14EMe43019TWlkaL1EQZryQTSBOuayRR8j5MfJix8j5HyPkfJyHyPkfI+R8j5HyPk5EpbMg+T0McQNNSTNcU4eSPcjowqZNPYxs4oxAseRm5rmsoh19XRuzBOgvk5rkxs5MRVFqFYhOiVmKSTXO49ki1nGRom/FsLqSYx0XJOxXEamPNIIVmCNDAuKY6ckMmkXQcLFabo5Y6NjxZhjG1T1ZL6Ua0l19bs35rHzSVWETnoN9KCaa09T4ROEhxnqPWj+CGKfcjUVIXPXp80xUs2aGBvXAlp1ZqTpIodER14dcbVy7JTJo9ljZvqUy6IpG1x7LGx8HjrdTO5+yskrJaqJZRPQy8o1M7n7LKqUp8VzIvR5J9RUIQqEIQhCEIXTx7K/a7/AFZ0jwPjsePYq/Y7pYgaXYZ0GTHg8jZ8ehno7MWFUXJyORyOZzOdK9FJw0f5g/mCQnW/wj5PLFyxeX8iWiipjPLHz9TgmL1X0oQIcjJJyORyHyPkfIx8ietD/iH/ABD/AIh/xE9Oc9Fajhj9V9Mi9B8nkRnSkpOkJrcy4I6LGM8LWSoF4PY9j2o+R8j5GHyeqhjrLSPJ5PJ5PNuRHI5HI5HI5HI5HI5HI5HI5HI5HI5HI5HI5HI5HI5HIbwnC5FclJnI5nI5HLsDfbZI71jcSKiFRj7PGyzu87LG8zssdux23NZ6zHRjGMe5aJ991O0yPVdugn0G9Dy7GlSUQ+0OUkO3PvWOr9txqZsySp47Rr72wSmR2fU0uhvs7U0thmE6yNaDWqELnsGX/PQ0ulXLgXHYMs0vztf573Z+elnoIZptf57W/mmT/voZpofez/wSJW4/NYJy7nWZNTCPttJs1rNPyOkGhofg/B+LNKaUxtJI6v4ppboeK5Ziv27CjQ0t1pkx2PTpZ7Jp0l9DzsMds//aAAgBAQADPxD024vw9l39b+of5xwK7f4W4/PBvWPRCjT/AMGcKEeLTwsgCnTW/wAHU/8ADlP688D/AID/ABf/AJ8cQ/8Ag78X41/yHpp/wD/QIf4v6sf8c8WPqY/6jhj/AAP+vP0j034Om9Q4t/sP8o9TKONfRn/LX1+P6W/0x/hP/c/qceqPRVMd03oH+boJ9OA4FHg/Gf8AF/8AC/8Ao3+h/wBITf5V/wAz6CijxPGP88f7P/g//inIOwhdf+Jv9X/wf/o19I/468apxrb0twHrHoCHEIeoIcBwHEILX0hP6cf+JHDv6JTHdT/mEOGq19GvpKPo19boFa8RwGeGvpCCGVFUFqteGq1Wq1QytUEMoIZQyhlAXQyhlDKCCCGU3pf1V4Rw19AQQytUM8BwCGVqgteOvo14tw1VOGvE+jVarVao5Wq19BWq14arVarULVbLVbLULULVarVarVarVaharXgcrVHKOeNf8pKhAHANDhVTZWA/C4rmdHzVh+T8Ffsopni2SnrXdy+Fr4r39NTlz5v3Xm/f0sRGPxfsvF+y8f7LxftwS8z7Lyfsv1HAVp+T8FD8i/wcIQon0MegS7r3yOCbut8ZVmLyJoJK/W+14b34J/Ug0f4z6noDR3Az2/QjyB473XjPdeM914z34Mee90PoGEc/rOHH6OAH75/1pUFQOr2V/SfU/wDvp/i6Hp09A4aenRaLQLRaLT0jCHEcQhwHAY4DCc04x644SoKr19n+0/8AFf8A4Bwb0t/oeB4FFHPpvx14t6Y4QqN3/Ybjp/xN/wB+vF/TCjhCh1f+dP8Axn/Ut64/4Of+SFHCF51vCfXy/wBKf5R/i3rPDlwb1v6G/wBH9Dpz88G9cFQvZRxHJUejuq/+MeNP+2yL8e/qqoTqP+QFuL/8/Ja/91uFU3HHqqoUqD6nx6c/89/S/qt/4RB/zhOVBU+n0+z0af8AUywtP8WlP/4DrTjK6J/VCpwqpUH/AAj/APwL2Q/1hTwqpKgqN/8Aq0/629FJ/wC9+M0RU7eqEyhV4Qf+9jt/g3CQf/E7cJ4CqgJ/VCrwhR/5z2V/8n/wbiFEKgLEXX0JdM0Tm5iNgI5i3qquSpwOIIJsgyoebov1vpF976X6v0v3/peH8L9P6Xh/HBHh/HFyv1fpfqp+j9L91P1fpfq/S/a+l+r9L9/6TPn/AEv2vpfqfS/X+l+0n76eA9l5T2XgPZfsfS/e+l+t9Kf8a7KFVQoKjd7P8zJkEEOAQQQQyhlBDPB/Xy/cC8QcKD+8Tbj0aPxpwDnSCfIoI4r72Dce4rSBgqD9w0LyPhGwBlKnSVa5KQsQ7gPgQ1DwX+hwEfr4UfwJ/Ij8nGhE/tX+/hMfqJ+qgffxn7/DxjHDgGJsPx8X4T66qFX/AEoR9iY5IBQ0Cw/8ooZ42WDouMJwujH2qv3PujtdQv71d1AQ+L2X430hDdkHeiLuUerwLoVQs1y5o3yFnUraD2B2Nj6AyuA9DbohidXocGaNElUh4OSE6in1IYAGxv0KBo5AWcQVhLlyRHMAVSENAhCMmUJQHv7mHdFrGChEDz2Q0ZLW/S+Sz6UrJx+luG8Qnqoc+GRM7W/hDIBFLA/KwU18spOJeLKlJ4sjvcv0vxvpfVvpC7AH7eiGYeNE/kgNdEfb/KJWPiyyQDWGhvjhC7plPphSVVRwkdPSD1v56lGaQskkc7LzXsj87svPey897Lz3svPe3ELI+MqjiksuAR2cCPSykbhQ49TtRBV4DfYVfjvd4js7uMgHYCshnMXRNcwTypvrKvEqJUbkC0GKvxEG/Kil3ZSHFx0REQAPWigiihRwhgjMY3QvkUBYWu6CuFvcg6BkMw6rCvYy0IqBIRQwNRQbh7ISiCZyvAB0cnd9KHOycCDVuANBZTIZYA0VCyrpHUjI+CFjcgTrt5YUTkGEdqpI4BSOD+huElVQp5rzb+jlAJZkYD7AWkPEQzUdHGSwOR8RMCDlNGIsBg8WT+C68G/hqhkdUDcdeAz3Q8PobgsvKv0reiYEcTQMNA9jxkxvLKxNCUhOKLJmByTu4H4FHzRUj6XQ5AFSWG5R0mAK9pSDRYwPrUR1dyVjsQ+oPfi6y+1OdqsnLNAUyXfcoM9kZ5uR8EOGIelzdM2j51Cc4sXpXogbhyWVwvamEHrcYVxpoi7G6UQDuxOyFTN+LUbBSOSNkAdo1lFgWSoA4KBbHVAFcIHkG9wqmPVE31F0DIWaiY+5qg4JcVyhYvDITZzqYiEK9ERw/AcXT+iVVV5p/QtBOeYFOaNB5GaD0dIaiE1uQneLoe4wbovNkGcyoaJlUdyTuTHBmJqawQYjomC6iOb97gKB4s6iPQIbWcEDZh0QgHsBG3shGHHSIxHQUIb8VKy/tTiT+jdocfFUVJLoXDmhSneBEPxlJTnBYPm68cIFU6N1ZAOWQCRZIQIRK3LFdAnCVTVWEUuCaRw610IDZOWKJZM4OhKJcggVxyTVCbBYqFvLKN1AT2oOMoDUa2QaLIHCTHLK9hyndiNVX4ICX9kYoXojdVPubCIOIlCJgaKBdODtRNLFWroBI6l0BLLRSYAcygPZoqYJQHYKsoAIAxqKAEiMeZUiFVoZe4xA2Ru6oOSJBQ9DJ+MqE7F3cTZRfyBbH3OAyBsdocKA6fahxo2gEUGrIbc1RA7dtvXiiDnDkOZGCDrXgWKG941y1HCHV97gZamPkJ4A9qau6QnAygZPknCFIralzxgomjssi4TLontwXcVz4Lnjm9inv6Cf0+4XRUpzzzhVyokeJz4VKL2UQ81FAOHhsjSQBbgDfmWsBUojjhyq2qXlC+oEcm3SGqE/GbcnRcQ3GhKI1XUCwphAsPP0pmVOyYClEAIi5d7aq81YRJkrBUo4uEB+aAMn8RNNkJBomNJ0VXepBzMX5IwRMFACHSLaq29lFSAMKKNBQu1AnpYhYgqJKBYKJsyit1U1lp8oEMyYD5KHDuthHRdAwz4mhAhhxjjPCU5Jhs4HOxULFbItHn62XxXsg6nQGMIj4AlhqmZKyRJKj9Woq8CEfQSyY7MhAV4IMmoDDfmRT45YjQENcje9t1Feoc2JZ5QkYE0VHApx3wZWymefumY673RqQnlDNNamCV7hRA+YBWCFgLSJFojkrxFPdIyBUqR+S2AnJTwdFw6COIzHFSs5oAH9nAyAFUJJGHykHNP2DNL9E5ld+TgBJF1VZB0V0VeJ1Grl+hDrAxhDKC0ikgsyqyDWRB+/yKPMSEcQYuxikjj5dY0kUCB8Hl3VFYNwggTbopGHvkI5LCQnFZeUVT2TH1TGrr/Ez9QI2OCwhMqVFohchkAIgmAz58Cm2pAWNHZag1KJcwYRe+EQ0J0yIKIBvhEg9hwmVpoEUOAbkBen6mfeFgfdEh47pxzHsiYlMIM25q4nCBiWw+n3URdA0GMMP2oXumGh48/VJNtJiUcIe9nikJzKYEfeFg9m4H8lNUKCiAD7QLJkqowI/hwLHk4Sfv8AJUAISZHZ9FtrFbqe2YCG5kIZ3gOaDt2IMgRDlGBhw0EQnNbZBCfJhhAHXUojXZcBygH9oms+qMKsCUsxzkQAT2IDYHyn2B7CDpqoIKC+UpFDzHCY7gpW5Y0QYRg3Kii9AHdQym8gv7EnGgQ/gCU/A9A2IhFz5CxohaQILkw9hKKqKdVYVQaxp7LSsgUebE9XJew6uJY/qCDGULLuLWSjlvMSqDtAFN5f2JutdAwrT3J1F61RC4A4QBg7ZSYByWKkFVQFBpTugDcr5tk5EipZEAIIMR1jGKEpxIEVVN0CRAvdvtACjoTIqTOignoKY5gCcJIZqJmABNLlMXCd8qoNZEcxNAziibsqu0MrqypwIj+wUJCRyPIEQDcjrBxmY9MKXCkup7OEEKMDCx7Ijk6oA7B0D3ZMm5KAhw0NKp6HDIkU5tuRA3NqsehA97OEBTGLZfUggS2NAq6H5oEgCLNByEBBE1c3suROXKLyhWRV5/YgS/oKJgl6zN185HSFyC+7loOY0CwaAPPiuocUEMGXcedVInwrVbvFDoLIEwnvUKknBEYWRjShdUmO1KhObY689gFGLWDVOg/RcfrUMqPgUZOz2VqgJBDgjBGEQScTP5zQBDsQHM6pF0XK4oTCSY1O2iLqhqk/DtmUojwAwUALcQ3tjeTni7cN0jqlUAEIjl0XSFgAzdazMuAnJNkWCEIDiCQk3q2QBzOcKajkgTXKJJiiyJoF1AeSpYDKwtomIZEwYNYA5wi8IsfRBhlKgExaG5EAIIM5x9IcgCdGT9EHogAPIG6JQ3KgU7oUggLcltDUQo8oUHJORcAMz7piJeMJhLJlHftDQyDCAWgAtCkaPKoK/ohnjihaQZByDI7cX4yoUkxKaPm09Gah1X0A1QrU+xU8kUWHMeRUxHPZAtjZAW6ZyrIhQP8AqhLj2Z1YG37zkpKjV8ITSjFEAXXWEIvmiAGEAAPco7Zc1jLdFkQ2kaJIvgR1/gohIEm/ZgIoWGjuThbUgHUMiBYZ78NHFjQ3DgNJoCn/AK4y8UVSz/N8HwtiXzCaoARb8s6qfgXSfwY/SKhHPmtfYjFwLkNeZ9ShsyUuxpmh0BdQ0TOyijK8zqxUsfC8ObEmEec2oXpF4WY1UU+FCxbUqDzm1awqqQZrHNFx7nsNlCRSI0onFp+k1xOiB5nN1AvICAfZMkJ2nsgCYqoYINrsto91g+6pMIYUmiYoqGFD2T1iBTtHdSu3mESdJJMI9Syt5RMXeKNogaoAwOYgcZlGzDkUTlohOe4hmb4C/ZFTb8K1C+ETkCMFjgOQ/MM4N6aqSZhxsFOAawOYi3JAJBbrL+IkngIRui5jMgJB4PUEzUPYmrIREVSiFvDC7KbIAjBsfbkoCP5qiB+ihA1yiTnsLLaJlDBUENEVmgAQo18zrdFj8+I6xuT6IDNR8qhOMOHzaioIKPvyXhBAnYCGVCTAINGbxDFHVOWS14sHVkBAln78NylP50oysomIJkC2Rccwi4KKUfQgXSnoh5r9ZdFof5CJBAKrNQD+I27l9LfMTsZtQ0UeregOhqRTIhNjvcgAIGFgEVClOVVOuGh3qU9kJZ4QhdGBD4lv2m0uIgENordAOMqjs0rhCxEIkwX3QAZJhAiPloRCc07a1JYNLlgQQRqqJZk/VwmChtaogYP5yhYvTYKQhJwF4+6KhjTgQqnLJHMH2P2nWLuz7Qu8pRtp80CWhB24T8fjRQev4Qmjfw8lWnx9Ca4zKnq5lUAvTVsHhusYeiCbKLM59UqCmOspk8fQiY2xdkppdAC+gvrhCkCvsQ0eUMlxJ+4KUQAJjAOSNgFU9eh6Lq+mEeRGBdC5tEnCihEwvf6R1jk/ynsTu4V5IQrbiXVFnEqz9JHcYYaVkSx9gbRhsUeQT0QBzMfThD8FoPn7EbGaT2Vg0dL0eQLJtUfNNbjRe5fVWzTwQHnwE2gjUfRMIGbBbEAhinjZHdtik/EMm5cCGHjLQz3t+8BHGM7y7MeXA9ARBwCpyrheYAAqp/d1HGUweWXLglktLpngPR9o5fYhAJEDwKizEndjXBThdZBJ0wwj5TQH1QtxSGzqgdUs5H8UG1diKpzudEAGRRk5ynCxMCRCewWQcQsU7mmHc+6DBuyBqbgujUZ9alQ1elKoSliiCWd0VWaoh0IOITiOBrKEwt8oB0UckGSaj3RdwgZssTwxvLd+hXLeUlT9PC8j0HixUFF967kdX4iLA5ClGoA5P6RcBEXFSwVV/EPzmZ61rpfVdGbORYHdwGCXVcDu/wBqfZUaCVKkJYj0SuvuN0ScXZ048db63caK5ABLqB9l1AODHUzakpyg0BCATR3zUSVZwOG1R2Qj2Lf1ARr91Q8Qjfy0FsK0u8I7oy40oaYWUiSM2t6EqGgWbpvSo6kZDww1L0AiJyViv1A5lHNwk9kVoScJlmNCSwS8P+Cvf49EYLkxsyoBtZtwAFnIo4sQqjVGAIUunkm/ipnZOjVa1cdVP3EF/W6ZVTLsqQKoWbcRNjSMr3UDZZPK4puQSyftTGyypnklPMjlMWbo2nE1QsfeHo6vKAJvStZAbcyoSU0XdU1iWTRMaTGaSyAgkJlYO0pgcWO4CiOHXQEgAi4Cn8GPnU7EQJcjTg3pcJ2OF3qXzYjuDUdCpjqfXB9gO6oSylnsiQqh4OcptCqh3dWwZewRJU5fTKM2DMmGLni5KxfCgG7nBSLuEDrgTAb4GnsnJvNH4t3TkWhot8eVHZHlT6x91N0NiMbkS5IhHXrkr4FFwrVu3w1LaVb+VBDeBQUDYEPQkALASWN4dM3R0PLmgdVQguFLJtQZ1HodKAZMidpFhzRFj3TYboDmCBGnO6gdTsSEnKkxZDFNEKqETbuiyasqrAnNHImqe3dO6HUKOaOAS10Fgi+FIlVT3/qMbE4omFN1JOqNDaJ9Cbhkm5FFr/UQdYEtaGZwLPABqkedh29VVHAbeU+odVyzgPbYqdy/Bh4Oi0NpafZdhOZe104YCKzNPKrIH0AuN1vrM4LT9E0ECAAAAFACgAYHEQO0FE07kyh0nr+EnOZl5Qr2G66Sc6ZoRnBum6BAhA0ZACOyid3GiigT4TXIQXOSvkC5aJVrC815SriBj1m5Aqj5WM/A7VRoJ+BZpCfxVSHBXpR7BU7IVz8Iiw1SAi+/ADQV9Eegb/KCgQXzzTGBApBnIIRGhr1VjNCalWVrkugsXfCCSWDVnKIsC5FaoBADoagFTe5USGrJTG772KIaThGMDCeKAiDIRRByTPhOEhGgDIHh2WorTKkCLoh4KHAKQnM9ZHTBCDTtwVBI9E1A6xa6OiccpWw25SyTfqwPdeuq6JXW9Lozf5IMHo8KME0O3akIQb6U6G57Kx7PtBmDu2+/EkFQOGe5UGTKy7Ji4QkUehAQBwlHIcaEbrZE6JFavlMMNJHDXhWILELFDs8uboMedndGPWhyggMUN7KHgGWdWQCNJr2l14MpDgvl4LIsHrp5hfnzwwiJ3s3Jd1skA5T29FDkwhx3vtUjYiegoFGpA6CIeie7p7opB8+oUY6ntFZE8Dk448KUDsqNMIdhfhp/o0BG8m66eCc7lUPwHWgHb4kieRUOZEW5z5BUnuebLAX8F1WPnuhcJKqFtRBk9odOZphzuqm4ENTXPSBrfKnY00y3jGiv8zVT7P1JAGMbrKPBlhbgOeg4dCL8H4wVKnU9OsJpQPWnNRWp6KKxbCEORJfkbIG7uAgPGTEnIw1CAVoY3upvdFwkjp/cqeZHlu/1lD0Bj+lslNgPQsIR5MA+VFBwBtjqvFUJwRopYN8PQlQMvEp527NdPPfUIFQqe9GFEHMe6V8FDeruCnUzRmFEIsoQhTVDdCroPbhHAkiUUQIpQKQCBCU8KxRvCMHqRWUoLFurgTjbmsUZdSLXQKCUygCLBAAlrssaMgsdDYSo3RRlARNGURn7I5buq2qqmTIc61ENAmeP8zLIb2X4U0Z8QEh7K+VB2TUHSX70oG+NLIfZWPGqwAEnHBfQwOS36H6Q8BQ8BWdJ6FB+Qqztjsr44otQoa0gxE4pAU7Jym5FOZczRjosjxrnKICKIjsWCyLJ0WB6LJ0TO4ZAhY7B00QsAh5IB1+vwbv5/RKQluVSnDixFeJZRlHMAcDpwE4omjK1onByjyxYCXdQDZKD0RJKqu0QtquHuaJ1FWysfgJAkCqbuS2R5F7VYBBlQ49RRQ7AMlZtF+UNHxJ/pMkpgOg+JR+4v3VVzwf0iPw7qyPQCGKiMEo80R0eo+1caB/uqg6VtI1UY2O3hVeMd0fY/qvdtEmG6zN9pjpXj9WfTwUF9ECkNPP0he3coQgHYpYtqLqLbNS3yxN7JBdajcFo8FbhnhVN5JSGApLMl3PhigPxlZaU91ZIYS6t9xHUt1v5ld5TIcVLPSqg50aXDot7VCgd/wAISSXbV9KqTsVihNne6ykwHujRvA1RGHN/ZO1fL7TmbmAL2X9liG/go6nlNPqTyfaY7pQDV7faEfw+6A0Loh8KPZQERfuT2Vnhg6O4o1i+xF6N3XIpNBIPi1TUwfkuqOvAvuww5OG2z9KMyawPiGi75/qAje8FJwb2R15ugqJ4Ce+FOccltzXsRfshDiqUxbJ2cDHZKaOSA5D0XzyQnqiB8F1ID+zaeGG6/QyF24AiWOymhKp5uybSnC/KoOeep8AsQ5BAyCR8TBZT+bpQRR4W2QvBipKhY6KqcBhFS4NktZXIk7m4TnvVf1ZeF9+AHi/KzdNN4Ro+e/AkdobS+UJr60VjnKy9SzqXxhvhfofSzKyiXy0+HNUG/Og1Iyzr+FeRRd3ODqVurOh+AdUsL9LGShZ+yKjvQFqmqnLegfdDu4hMzkJeo8v8I6+5QcA2UIZYLlYiSnQ4O4uF3k+RBj7E8y8NV+B+yBuqn2nR20BPs+0OTbcAPQ8qrE5PgrnnRrWrL+kvyrnX9FdprU9VW0yl/wAALpMU/pKYr7G9kNBAcisUdSGAnSvIfdKh7zorFqLmg+yB26qvgiuwB0+6aFBaL+sorEz5KWB0HsokXXe1SVC91JTi0RvOUAR7JTggsaHUqEaj/MHAEF1/RD+kEGe6yQLShnunv3XjpkyOOy8BHHZeMgLdkMOiwcGHdf3wskxFFWy1RsR1nbXkiK42ntqLMDiRJ3XstU6AqeLIc0SU3AC6GU1OBLugjJtZQ/wqdW6NQwCpNXqKLCTa6unewh/pFh0MrVNdaophXxkEOAWOE2nGkN9T7VKhQpK6RTHcpABW4DosB0WDosHRYOgWDoWDosB0CwdAuks+l+Z9L8/6X5C/MF+Yi+gvxF+QvyBfkL8xYegV3QWLoF+RYl+RYuixLF0WLoFi6cANiwWHAwRf0j5Wvg1QIPI6kfdRxh5HAOjyybogJJgIWy4d5QVqOoCF8av/ABAsURLoHdBpVYcJvnDBKZo0QbI4mpBEcIJszjWQACT0dQJ/f7BdI+y6VEDZSWqiSY0CA9UGcKRENyIF/ohhTErYRrFz9L8iD7iP4FOCipDRx4tp4IdV7VKhQVJUtU24o/5kyJR1WLqsXVYuqxdVi6Fi6rB1WLqsXVYuquet34x/g3FkKxjlcDb4U9H+E8ghHjLCB2Kp3SInY5Q3GEDMFPMqh33UIQHS7MqQnBQDJeWiOAx6oigXJkOzhNGzOAjIFChDjKQRonOiLh4AEfEpwCgbD2RK1k7n3Trqj4EBC0vgdEMgGEN3uggluCAoIC4K0VvQDhuGhcWDrIjOUv6qWaju1x8y7CZxVAhSUJtAqXnHCPV+8CiESEoDhgX9Cl33ivbhxvjdOJxzk4gLF+rClVKJx/o6hPwZRx56chDDZOY8IQM0ITMigUBh8Sg6CiKIoqTgA3QLZB04UJSRAsUaVjwEvMKAbe3AMsuTJfjgRPKtwngbDhaZ8JJw29gUkwFU1CpsQi2gNEQmbptA9kIJhGmboiBUhPgytMj7XxjReRXhwdhT5lNwFAv8o0CDu4KGqIbjYcEHrZRhrej89VeDnKKNeBPAdUUdUav9q8mVA9fLi3+b3JH3qGyfcu6EggJKJgomBABlBsQEuonAAuTRCYFnKJFSIIoVNKoWqgAwOOXseaInhQEsZQhDnJYgeo6BkkHks4gkTjRa0fsJkx4luAMTw3k+Elv+gm6AwV90LWBmEIgSXMjR902mhgCTsZBovYKYoGT/ANK6CfzQFd/gXdzSraTwLrJ4dTgQ8JCYh4PWyOUNIG612yh1ITFJjNSDdgU2C1KUH0duMKAhQdssICGwx12X6x9I4w5DAkBMF7Kl2PpDFWSBsMjBX8H0jA0cZhVYZxf4FMghoMiQCEDyycK7ubUz/wClOGHl3qGwXgWIS4KGQuQo3D2F0/NUJ0Sg45w6IEDJk6tkWGilkZOSQH2CgonIQSuUbV2dWAlajvcl0BCRUqM5vYp8PcXnREgd5AhXgso/NgvItxSPpGmvhJPV4AhSRBcckGBTTmTRNcouJDdEGgmqcYgtVtlFGUNvhefBd5eAwJp5Q8CQCMnbh1OBI3Hug6cQAdiyaa7gzIfBalVzR1Udaq4yAnKSNYMldNFaoIQIuLkDDkeOgbg8+McUkbrqH3UsFLIALkmOGA0CB0dVqvxr7LN3IVLLpA6rYEPS2iPovyiwCkTdpYPgANQRIlMfC45XySOGnF7kPgs2xCafWFPylhPNcSJecwxGB/kgFu8dBMWg6u9f9M+beobBeRYnTRB+yj0N0+GvUSjiLCCCXuy1gBR6FWuyIHk9EUWAFk0iS9odUoAIAALX8CPAJq0KIUQCu7bKBBUDvDVOQDkbgw6BcL8EvEsEPDpwCddanw1Lre4ppTiWmTQooiDnuq1EIgzARhDvAUUB0AcRaRCouxOZRLdPj+xpvhdRLqfaUSfZwkbhSU8x7oPeg+A2J3lMWTzHgquYgHJnvKn82UQwaHQmZrakfCOkocAeWH7OnPvYBzZkOFPCVZsUjcLqPdAxmvNCcEIFgz9YdyJjn46nbBtFbhBuEqmeM81Iz7AVhEKkueUE1oBz3+4TLiCkD1W6kFZhfKq+fgozcQC+oAZoh5sjCkBwmwhsKI5QBEEPIDNmTaMsKbkjNDdFZK0lIcQyqxAURDABdCAOHIAh6+ujeVNdIey8ixFrIMzhOZsntAPM0hTKPZQ4QRqEYMIQgeTE3hPQBAD4dBsEWQ3cM2gI3nQLP7qoTeEYOC4Bm7dTaIctVnQIegT6veSfHoF4tvQFmvhJP4KUKFQDdRNXaZVTmyBcPIRiQCh2IDb7qnJP4CV3cM2DHvfD7y7JVooUjce6kp5rY/nP4mWpocfwIRuhyRq02cJGFSwQl57g1clOwsBE6MwhU6CGkFhAepI+uFPCeDnmFApXsaZSzJho8ZwPSgr1CcGZwVzTAK0uVTz1usKRVEt4X0AlPLNkE+5VWhASnPBEgcZ4kAVIEcl77w5WQVNx3OIsYw5DGmUXKN8l8qaguhuaX/AkC2vnzOSgn5h6IHdUu2lnpVOAMKHeNeECxQDAAINJaDVyMrtw9+GAEPpD2TyfyKIDoCpiE8ZgH2Iy2JqYHKcEoMIgFAT1U5hgUvGXVVuuER4jNEY5FjQZTH8Si7VG6RhFndwiGDkCCDcIphlJMkCcISsUHseH/l4XiW4wdKp339xR5SDkJo6BonEhXmCcEDFyHRnog7pnmM8AEAbuuoFL5vwPBoJ+EZLhSSo5pzsKXllVE53N5vglOCKr25QsUOXM7LnoElN5GcsRNbaQzz4dGMsvvHcnCfKgETwUOYHfg5HhBdR7lI3HupphAIvHAVWjBVGG0b4kCmV5gEGheGMFMTvOSgGKkrcNdxoNQrCjYBe72WjgUWifHxh0O3T42gQPUHBQAHpJQlCBoChcjmSLKz1t8fDnaRZCI75CFWM5wG5S0y0HcoI30XPB0Z3CpnMVnlBCDB5LYQdCzt4c9ECWlXMNhsIQrAknCHdghGBqYuqvZM1AlvA+3p6l0nsvGtTozB1QWxFlVoEQg7IFe/aTSD/CknACTzVaqkdkSXChlUIsse9CmieIdeIZQBcBIFzQrwsZxw2qITsHNeaPeGBZ7J+XAxGgUeiaSSoAhd5mOOGTwagbn3Jj4epBYp1KBONy6OTPkK6k4+RFodylThmRjIORkCJfUuoPdT+Loz8Kw8VTYfm2qeXBzqnhoqrw0qlPI6dgLJwBRZPuub7xaEGZb8dbU5oqZ2TrgxXiE6YVwg1XwfUpksRyGgITp/PgvAuRcbouVALYmJUEHrZa4jn3PtFFdplHBuABCyfIRJ4iE26P1oQmKTwfbdNaiA7Yty/2khdCdSCWC6Cj0MOb1krdgVUow1BOzwKFuDBhjY2BB9qTVqH7QNL6qDMcg5QQfyhQTlDT4RKeFFHS9gjlaIQjhUoNM1ZYRWQZ1aQ4iMIrwREAl2effg/Canb2V0B7Lr0fB/YoRXpMGEDdPalYRGgVQ1kgcKh8osYmbuEyAnejCPxABDDCAQCcAe6H2IdGZEUHkHI13JEEOgwgDMZAEzMn8Z1+bjgHj2VuBoc/cp3KIMDvMhBGIrUFHDGZ/Vk5SEGCLmIQcQJQhELAU5pg3+VNn5kQf2yMAoeg+F0S+YXincNjuneT2IlwDwgFNL0j20VI34oU5zK5qOhax5heCLPwLPyijz0mMyfA+IMTmhU9Qb6cDgbxblTdAFhWZGKyINVgiAI6blJ/tJxD7YZPpYhrh/BtDFqBAy+CIlIpK7YgFZV7GwjdBAN24FC4Htkd4MqHpJRt0C7UTjEnBQZC6jrkTswtSoMk3PUEcedAwmEFkYYexSHKErK+JxJKn1wNhqKBcRGHTxfzkNwmdGnSk0UBqR8zWwyyo+kYXy8p6iGG+wf04ciyPZzssSwgGeBDocI+fZdILrUdlMwqowHkm6qBHuV4NUomZ1H2gsZMsG5plM8en9T8GDsAZQAGGS7DbooIGR8boUACGiETTMnc2JYYVqAEMkWLUZEWyusVD4xwTzLKOMguQrF0qjlBOVJ14KnBDOQ9kxc+EAMRAiiYziidFNiykHMqVzPcn0IY7gWBDgA24WQ3RP47gn8yEyo51sO2fhageiOd+weFV5CgqFbBJ6tarmlo8Ny8d0UEHMOxCMoPTTuZAVLLt8LU/hyvBvUjkuqLQj2g81uMWyUlckyqqDLSGiVkXmIEvyM5wPQAWHeAwFPQvDUc4ANwOb9OqgemAhgck5iCqIrg+d0AJubrUHWbiRk+Ug8HqtQwiGPGw7FEVR8wyW6nwJCwt4LRnuI7aeOgxeAp+tf+B3OG8EpucQQWwB5X4XAUOiX5SA4kCXkcTrx0DLBKJqqwAHFxMWHDoqeXZdIfC6tInsIiWJODtkK0PzBGSUCZcRdEU6Qh6wU9Zk0IYNydgSUBmAcmU9dVCGepQ+Re8ZetkJAMI5mJILgpk1QJPQoXmFuSLMQW4GmQ5DSGPKocu4W8qaNBQA4YmKLk0nQiEaZt0ECAz0JyCAAPIGy0Impk1LgwGRTZmcz7KDsfZc10hkk7NcqbfKhyZAUmHZeHYuidESVGwqFR5g6pOXq0VdyNEx6+6rDIFVBHhB9kDrlNHDJgD834TV0nyG6OyUBZ7hoU6V496ncEOovDZN2dpvCFMNRBXY8FsKgYO2DeSDKXN9n5kM0ZWutm+4kQJxYXA9BLzfwJqXILD7QP9A/SfAuoyLepqTEjI0nqcUCB5Gwb0QZ7aKqNWwRdiLIuxQdbi3qt0MK6rD2TEGqRqs4nwcAshgT+AAigMvVVAgmSl1uHfWA+tu6tsU5TQCR8314MaKJQpBPWzgVBy0WNwu2X1UZxFAZBRKAXR4Q+mEAQlpJKO8J2Sl+biiUy7iHEkMR8DAeBRwGj0XJKe+DVHaaJ3LM/kn72bh7FAEBmuGVNQqUAkSN2IQmDL7ggFtAUYu2Hymk3M5CjI4sTKW47ZMtC8PguB8DBJogL1YF0DCwTcYbYjFtBlAGuLuwgKI9I0ipIcgxCgmGhTIawD5QMYA0C8y5dFHruFO5ZSxkY6v2DhKjPsJeHYnq1Kg813PZX3zq15lSUmSqJSQdB2JMsQyOBflUUW/KODkU8BzITyuLcZHM3JAxbCQyY1ARQiypEh787RAI9m8d4hXSXReGOSmYBPuCTEltE6VEQ5SJZY6v0sJqzvnmDrrQn2Ku9AMzgSEGbuEEPyEmWfCyEEz5/BUgGwexGjcjI7iiqT5kGxeA1QtB71Ro+GZ07oQjNcNf2qJ5lKIbWVpi6D82MoOY+Rog8L50QgkqY2WuK2TLgRmBVhbEwXIEToS8iDEAHPAxInBlQTkAbecdCLTl5tRTguTALR6C0HYu+q9P6V0gig9AYnEnJH4HZEUdRIcv5TUeTx1V4/hjg7coLiIRH1Ifuh7xcbSX3V7L4b3T8vk3o4VknhhjoFz4mshJJ4JAyWIPctfXgWpZ2o67/ACUeO5lC4OwSlUOwwyVK3kbIAfx+UYGysLuh0PIdDcOa9qS/aM4ERdlX8yR9zGTBjCQeBufhO/zlUXi69FXcfZ9rw7F4My5bBS2KbzKrmXw2TkyX6zwkwde6SdR5ST1zy3QYyOFqn5rEv1bd/QoILHq+1m6vtPdj1LN1IbdRYFsOiz1KO7nZpLrm+6Xf7TwVioqgzJNyA4QQLzBqsQel6GRyKjDJ4a7oLOyiNWs0tV2UORoD4XCapgzvstGEDAjEqgedbmWoUgXloxpt6G50XqOK+uj7FO+nB/MMVUFhXRkhl3KXWpYnSMKCDAJLuBZmYDBhRGotcuzGqBsydMrvMwugExu4PRGI7mZZGRcITIvGiLBJEICGZhI/EEdZQJfSMJsTSARbtwR+EyfAoym5mIbgJEVTFAIvzQoWQSmKOLkyQVsKZHQ+RQogYEznQIwBB5HnKoTqCEOImJVeM3D2AVzQ51eeEixu6Yl8uRaYDcBCZaWdmO5OZkpmkGw8pF2I1rmXNBXai2yFd4isHPJNCOVAQ3N0gEhEb0ZVUfkdyZEAwPNk6WWDG4pJyd/tTzLha3AHQK8xNKifp4eboWEgiZu7FQxqKwqZfIAh4YDNk6DUiXzUlwT9rhh2zMAdCnCulXE+idEg6Chx7kCAUCo4mwKDhDy/VZJS6Ccq3L8AmD8ILBA5QNubos+wVDMCdBQ+xRAok+VVI2n+U7hTd2kgRpIJe4j1DAqNBdACQhSgo8J4RrVWkFzo7wcZJGPffDEhp+8V1QH0rzKlBXeBYLoBR0CPLhMIFLp6FYgkHMJVTgI9xAyEcpqwsgeApi+l0xkNqAUFnBQANQ+Vc2OWRxOTv8l0ckGVjMSEMtUVtVXamqdkQQ3MGcLYPuLvXXNOZ9hck4PD1Jizfom48MSa48tR7dUE9KWUjKhqYuaLKyDYWtFfsQQaIdcWr1F1k+GeF7IZhSwjxwtW0SwhHiytUHwmeKc0bnjon8CCGx33qWwV2bNSE7hE0M98GQR+MKH2oDRWqCA3aghdodgrFOqTJu5qVRde/cKeYbxCzuabagLJc07KIWvg0OilClAIL8kNClbSvdZMYAHM6IgMQNyqJNGM+LRfspXPzgL92lijmeNODr/E0TacAyoPLHCt3j9USk7PPQIhUZw72Ig4oILoVQhfAHkYnWFBAoeLjIIEUgIIgGy+4g4SIsg/YV/K57EHnCqlpmDIAUij6qddrDmXiEgWEdVtlwEmCASvarlPmEZqRxqgddx6CPZxcuq6CoRaKpywHKJQtBEc0CBcYIojm4d0YOExxpsNEIBAAvsir0YF1CWXT7iBThLzsvwRV7DPZhLweagaLGWfKvLiLhiE9aiKvcAgXi6f1u8A1BtslPMEIfaytzriDXGhCJi5wYKKiy8wDFAUkWJtdDJ8jhAe0STzwDg8mHOQm+jODcQwPIcMsQECm7MjsOGp7kouBcLgrzDU2pgKXJOrgyqO1IjI7lC+gos9CE/CsC3L7QZpSEat2LMRqUbfSt8dVkebo4PUilg2pF0LLZoQKbeckXFUGoe5RmDsjK9X2jchYgJ7qMX/AIIj7hZLqFo3hhfBM/CPm+EfN8LIB9X0nCBPjCPjexC8NNwU9LINLSQZOWZs9HZFk9wdy6LSJdBYPhqn60V3mU8QX483+nUCHMC5Ej7BaARBOQKUUKcWVIImqOAO2rg4FYHlQK1Q+5VEbXKsW8SvpdyaUJRsjkCgDGHKKGITlFlETQdSRVndPagizJoNzQdu9gSOZO2MwQhBNIMXIiCgaADIe60EGqFZeeisp5AfYF0MOgW1TQDug9TKdaXuifQOv59E0U24RSfOUKsoMgGodkGD1tZPiC4Q6E6nEXWNi8pqQHIBgrUtStYaqsanQVARTKPY4fCYHh+/oyrwasCRkI3fovgVV1jMAAw+pRcFBy5z4mfvH0j+/jl+pfuX7Fg7HgP0KnhbOguQ3IbsIQoXrKsq/k+uGDu6ILKEdqGWcM6ywrdbawOi6M9SmAmKjEMhoRPtmezQ/QHYPnNRJdVSKtfZ8b6ozcja2uGhYu5BVQa6XaQdVqhJYQhAoDLNytojoKDM6hIMAh/nbNxpcgNMO0J8EqOAPiYXQXUIbogZY7kEEAezSomFuSIDRShVynNDVRS4ILd0+BoiDZlGyhvQyg2gsFjB8Qskk0k8ghSEJTBlAohBaG902QAwjY2EWPqhM8cvbvwWAJlUGXB0M59h4jjSqwPKKULAYBD6QM1Guow0SDTCHcwvWHdExRudTaoTQ45Cvcj4OjPX0NsvU/DgB+BGfcTJzr6cT2XYF7KSumnX/kP+Dr30CQLg2Chg0UbUXiylp6Ju3C+pWqzXPMBj3FQCfJdqRtMTmhmBg6B5Kd8R8zRMjqQt+k9EtyWAUQdO8gMSxWwTxV9uENkocV7xvaWAhlYI5HcGzkiEAUg7h3cfRF42E20OCCmYhsQ93NNw7avCGQOLBPwIIMdVkZ2CXugke6mgmCLCNsoBkM4Q2lNCyoQ9WwpQZku6YHWh8K4cLiShuYJgYFolAwQfCYIUAAsuWXLUOBePoZTSw5J9Rqd1KxRz9og7hZO8o2cDSxwgNGqCVHtRD5Thkki4tfb0eEjHdLsFm+5TZ46bXh7E6k8d3/6dON0CUFJMfSZGABRSIFnZRGd7Scuiim8XZger9EA5LWczojghehK0AuAbBIUk4wsQgQRqCDudk2AMAvkAUYsGEqsoND7CJjg/HrwMLoBbhnCAxCSZpMXRU1xIDE80wPIkuRTqRKYCdQAKxojJa1S+KKKa4MzLOhGimzoiuwloTNou0vgQLAc2lxtCjaBYIl7RZWVpQExHMFghljwSYi7oT6nvO0iqeV3ywTvPccpen0MNjYPZAn0HvEIsDsTQmUd5P5CLvHBgxuJRE9Y6ElPpvrQK5PnvnW4Nw2NoDy72WmDJi5Xtw5dVUp4SV0XZcekH/OP9BwOCI7MbJNBpKNZBaDipPPpFKiy019p+wr2CZfGYJIVToc1DACbDJeIJRUwxtJmNEBqkaXInMKqpDGsImwjxAgDuCUqGEuL+jrVeBcLoLUm9UmWhVnpgAOeSvJRwS6GUOoG5ZAMIMNDeYROYQJqtVkBUZsa0J5E1KDyUJltKAVwx/qlsl00SvqthFOatqEOzNgvl2QOBXDUB3EPiEBsnKguNM7oAqCGGFPtNsPTi2k8K7jtHghWptuQKGEEBNBZVNCD95QqAomyUIw5aDjVhV/3ZPshPuB6MuM24TTIqroOyG8R0ymDmG5IEg5ECFhkLupPrQDPox6o/0Hvxp6reFHcBV4N45HQC6HLQxpOeVKILeoScly5CwnHAERkfG4SPx3SE1R8xBwOmRdvRxu864R59MPGukdgn2spISrYPUIkb5QfKa6xEGDo9ssQ7VMRAMKtFVYIFEcGCo2d0JGARCB5QHLI4JTlQyCmCd2Wuiq0D34CmA6soydiYZveXUY8gZti7tnAhzCaQtc33nDooQNh7IeOLHhqVAwQWmFeqCYZDMtgj6Ere4RRDLpMLBadkJUFXuHHmr2YNVIDHw4cuGcUgEs8NARJG4CJyB13cIeymSCfAlAMAEDhVSeGvn/Tr/i3pddPTZELOIgN0NVLGrFV6H4tcm4IEs/qHDvJJsiJeTMnvF8IkAn99NPCukdiLIOww1ZQOMED3FTICnanb4T4MrmNUyyslNOXgATtCOTzRUqDxoGrSZTIrDqZjuQQKqQDrLwOCsRAY9HZBkYdwivIytRxgOrFUXGZhG05VuWKe6UJfBxOB7cHMPHXwF4F3BuSmByRaYBHCAZSQB2CbEmjRvhUvqAwdUAD8rzsixrPum2RDB7KOBpgO5Mh5ZhapPlFV3qFXjBUFQfTp3/77Q6BDI0mpAWpMhaDNjiZuLpSVToEQOq5CBl3H0SMB0ooGxyawonRdi6h5NsHxq8EMi0girgGJCoIqCDUceeJdIbBdElRIUIQMOWRe9S74D8IsMwyIBoniBYBaGLHb7EDKQwygUCAZcXDDqLwA90ia0KnKavNwx0IE2wMZFOLjC8/DqbXS4SSv1QJii10EPogiEDnkWE2hy3VRfLF9nEp+JfxrzkoJ+RLFWvDKjAFTllRgQavIqRJiBSqqFBefbKFrYHQY1VUGVWHfVTxTF5kB2oQIeQFbhPCOCFKf0uj1MV7cKC5oM3gbLn6h6X9bEHCHRmVzhAsKwg54LrGCAMuE/AGIWJDtcAgtaDQ6LtU2UgwKIY0siG/AoK1I5IOo1T7qBGUNQY1wINIPwu0T5eh4ZBeeVJsdlt3TKvFxBqdFlgweOYqslcNlxCnyomWKaoFbDayHzpRosLkWUHAg3SwFMJI0AQ7SoKCJ8ptSiLk2egkfCkeIdByOIhgexA0CciWsq3sC6d4QEVyf0tcCvEEKK9y/KhtwSfk38G4ER2SHL8p3kRm1SfsImGgyAtdDSgU/bbd4gggNIS2IdBhNoC4QAQADgguCOFWSvN7svDzCWFNGBk/ohVUFSVp/mw8CCgDSew3OFfyk0SVSWaUwTTpqcCpCaJjAeDP0Yjp/wHQUsSxCLtOrBTV06hK+phu5FlD2gAGDKxv39ALuHBBBGQYI6JkwaGuWObkI+UMaeHwh5FlASrcPntQSAskG+VGt0tEDZAkSHB+aJX6iYG4XetQEzu63YUg5Rmsjq8PKnmb0hvVBLH61wo2MAHUApFh6m+U9R+AQge1j0dEbWg6ACxgSNe1Yb8lM00x9Ck6SD4HTvirCclD+sA/KfmcJILGV1flwZNkjkKcUyyobdEVIHIbkRhB5z6O1GGsRLE2InfocAQD8EaSJLG3SGToy7707fqQhUH6kYKqpFTs/zdfiLmIT+oEFpqitTbJ8jJ5ImCj9o8/6JD+jzZHltWpyd1ANo3B2RoJNS2cEARMEhBBz6S/WFDJwXAajQjGJLBF57B9kfmgQygZnLpql5mDy6B9iljlkicrqSM1XTJpqIbJiaPdEB0h5BBQIC3unRzFiBt/CgC09bRcRJQIh4hyDgo4LuNSCiOWe7Qm67meSp0+0QG66zlBoiMePohc1yn/AwoCginuwpa47PCqh5A7J2yewqKoyhUuIu93HjGXW4GNLinKgAAtbKJW3lM1EHBQiSMjsGUfEZ2e4Qm8dVnqF2aIA6IYvBQeBgyhKYaHIgGT/AE5fpn8NVUwcHuez6YUcIKnZ/oTAQiVr2AFSVgclfADjImh911JROSdEIORHIiS+l4aOFb4uwU2I21aDfGx4z6rLfi6dOjMZSBmh2k0KJFe8GiIBQA6oAwCDUAgNB6RyuyBGGK0Yd0wR6r3qDJYyKo9GfI8RYVQ90/0CzXUIw4QT2gAJQ4LG3A6z/cKGyefh1VEPVX3ao5Y6Ra6pKMCEGMY5UDDLSGsyokfiEDEiBNdE5kcCMiOCoBdhUaGLeQFU0W8S+yIkIioMp0RN6Cr72T0DBNgNADkgDvEqLKDdC8GakXDo8qey8G1Q8VcCI+FfQAMJtMxHcoNUFn+ESpEFsggoDh9iVPmaDZCDUTSBsSBfO+qcq2gMF+XudHAIMUpqJJzAR278GUeiVCTs/wALPwpZfaL9pQYzNBAOqkNkyi1A1Y8XRCrK48oGZBABBOqdCkEXc6ZBiKZ61QUkElNBcY5byDQm8evv/m7BuvLjYHEkPbKmFX54XiVnHLxAJcw2AoKkVTD1AGkw2B6b8J8Ci4cDEGKukeVqTCFfajQoOx9uHGn9ZQVHiUAbcLJ6LEMXCigBYL6bJ5hTy3HlWaQ7lGKN+gcq4TLMjBTL4EPMwMkJ9FBSyRCHtWOhSPkRyQRa5lMZXcm6qMD2dSfsBSeYdU8nXmwygiMcwJvMEI9Ybfg4KuR4qV5FicfCqZeDDhUvbBy+XWMrIYoLulqT5CEuolBZhPC9A69AU1QPaOdftCF0fJUge8C6RWlyD5BQH034ypKSn4yf1fejZJsNSg6MAfi2aV5rgXRqlUWwfZ1KkSZHCA5dECcbAQgS8hMEDgE2FU+q8gtHbSnRDW3IDaEV/wAoqDqIdIgm2ugArgf3EfajL3XTgL8k7k57n0D1QUyNfxoKAg+sHuiRJEQEPhVa+WiBzJpWh3ADKLqjOZmMpnAIlUCxJ36iG5Aexq6oDIhoFnUFZQkB1E3AzX+qgCVxEGGDPIkloCKGLGqCs+tyz8ggVX2lhVyX8GeFM8h8qt5iqfg/BtY1MjztFAF5h7myMTik7huikcXOArgSDEVsDAJIFEB3ZAzdAsjkxqVcdFcD/hJlaf8ACRVQJgg1KAcDxrwhTwJKkrzKEHi3owijOcX94C5X84O1A2QjE3ZDxNxJowDzO6BAYJwgUaIGAgB0xAAquixyZXkm806q42o3yX/wO0hGQILgMMlnK6bGEltpSU4C5OY8fZdAJFgwKueFQJIvUg92GaaACB/nBXh3TyrFCDJkEJhEaFhZgoc3B05oQwEHdGGALlOAkc4tN6qFtBQcwDHcc4QtmQIDdkN4CMDoiqkmeaC+ExxRuYE7obkbUFm90MiDS/6nLAcFz72VUEHYXH1OEwzEuOOCBUZgAGXhU+1TyHuV4dq6P2PCAZpqjFo0QmLQps8jbEDIJE10fKDbVBBCBFQQU4qqhTzMHVQO5gu5CAerBsD1V4QVXiz6mA5LYGSDkvcwKNFiAOagw7qLK6ln5cTF3snMFqUeJawV6TsSDXJt1IKewogDrumJXSQ6HKblwpdzmhTPblqKA8kJlxBJYdn0p6nTzgfCJdwWLF1bUIl0WatgRM82kCgAADAMNAYAaf6VRiq3B7mZDke4KiJInBAos7Lu2QOT7AGcrEVVbfCG5YBo8OZ7FLLE0szBA/qhBWXMoEJBd8rkMAXfdPUCI2E13gRdRnXPRsLWpkE3Ti6xb2SpcQIxYIpBBG6V/wAFSrHs7bnHC88uFui9jwbf8EFA4PwQlrmyYFXyonCc8KcLgGxCIQwBAPhdBgAIZzdKJx3Bj1T6ya+qHodPwvxgqCpUheHTgfgQNWUB+6IkyH2WE2StNQyZwgh4hzo5yCDn0hBsg3d34QQ4WomAAZFAC2VGjjoBN70OYRLsQIAMJT4VVS6HvjIdQlDN0RyXlnoDnf0H109E+sENlRbA9JpKEhHyOM4EAAc3BMgY4WIIgqVAIT6gMCCeuEesjwT7KJ8CFJashcQAHBGzexV87OHBPyivDVUEqAgenLXddcWJTYerF7CrAVUVDeg1ZGr5NV00UE6prwAGYBAugAAAAUADDouqS/IF5N15scOr9uBt8LEqtGiBoYJNUxmA2UQ83ZFmKI8BJCS52Tf41UFQpVE5EoHAGkv5Rb+lnocw7owjsEi5kPiDBSb2EVqQsYnQt0j44xwJA8aPIU03aE1IgvW4ZGrAI9fgIOfB2SAgAAAUFAEK20S5mEDQzIegoNXnsBNh/dk8SaenP/D4EgdCiAEFk0gaaDcvEUpokAECjBChAjUKdBBRJy16IBKnmbLgBOQsIxkh5w6DdohPDbOiGoF0wcFD5YBGIgmCckTGql6Bq9AXsWTITsCAxBzVQStVUJIwoKvc8JmmEM+RUO4a00cJ1Cq0WQ+io6EBJPDCWwXkZT+SnCDV7cDbyC+xdlMegQecMh4MDoiOfAiCainGVEcXUKyqpKTwR1RLWiB6nQLnRHdZGHrROKMW0RtqW15EHkp9t78K6dz39IABHuj8VTUCN3DkLwFBRDMB+m5Mm6dc746vdk4IH7ogRLAcOceGgOjwKf8A58ww6DSd1UBaIe9DVMA3IsOyTg8VSmKIwnWLABKp40u7E6phzZqt1LCNIOLUOdATDcF5aSKp4Zft0vRK4AIA8zgBBmSCiKd1WzWRCELPZhDQIQTDijpwYYFyUQUTldaZWVOapxbBL6I4vYGd7NZdS2ODvYF5uU+5w66eC9cIIEFm+kCZfJaCqDHhlEkhGhAin+ck5KkL59l5FJWWVdkbW5FZMrOrFWiduWw0AsOHiXW1Ii53PFuDJnvaUkuBjlRmBd5dtKxsmvxJ4af88LKeDLKPiy5mZDMNM4RiiJh00IW6hyYaboJsmqdIgRNgYzmlQLoKF1HaDPpyIE19HQuKXCMqeEHAu4cIg9UKDLJU1BaVJYRYp+dREG6EwnZJjC1SbAp1Qu3KiYa4TmVem7QcPdBDxdcLnqZ6Lx88SDV8KCiDcBFSPYKi5JZbRBxDJsCAQ6JyKiEBFSCATQf5zCkqV7kyWhsOB4eBcIeXZV3/AMCUSn4Di3HT/BuLrum9RGSHx1k1583g+fqsA65nuRdFBO1/d6cTMEcs0yH5gG6B42qp1fLhwBYm1RBE7+t4dRuClt107DZJl8G4qwvCeGoT5sh2gCgEMZM4DwMOr5o0AtvhOEIgkgUcFQYajVU8GUBJL+T8GpPJeRYqN3BvJZVTUOAZFOCBJM7DIxRI4AFBIl7ojKlPXFNEB7kUOCKcef8AiVUruK8q9dIe3o8K4XgWKu/pKdP6serRaIf5EpvUK1l4pMPXgmJ4QJW/rVyOxUARkNIu4l1JebosB3T10WbRWyBSUD8NuHlOKUKkyEKujI9Cf4CCAzBnIDwrYUwggAwMPeQ0kOXBJqyZhCIBLVkOayokRVAGhqCyJ9gOqDeW6gDgCDc5mpPLgSBwlv8AShB7gSygM0bLLSmhCvs1CIFCkuD2i9kW+jhP+MuPcfZeVeuk9vR5l1MQSdym4W4OeGPQB6Ah6M+rn6524DiCmuxI9zVAWouuyUHUrsufFupe66hPtFbWU5auUHqhDwwDVUkaIWCo7AVzRq+UfHR8dHTush3WY7/a8D9rLw3Rygyo8bq5+VJw5LoUO3Bj3+lCKSDocOiOR04D+COeyP8AHCf8YVVK7lzffrpvb0eBdbqTxLo+l/S/DH/J19DVNuc1cOb6FGkkMeoAJki9tCjODgqsp81I24H6EEukwEVZCS2y4Du3op/L60WIIIvrLJxeXl1QHmU4GM8CNnMATICCwUlEoy5XoHskxcEOXt5LTk7/AJwqqV3Ly715lvR41149UeNc8acGTVhMGrsHPaUH2PwjWvIeyLxuy/TX63pHAf6jjK1uwMCa50AL9YkHZQWXRmh3VY+ii3TgpUCmHIhhDCGAhgIYCwCBsENEMLR0WQ6LIdEQZhFoojonuTAoGygx0QYQ0QwFoOi0HRbdFt/jPCGUFSVTf4XnXLp+z0eNdcooedc8J9E4mrAbk0dBQNq9QQZ6r+iyPVZHqtXVFxNx3QYJpNwEAJYAKmxB2LoWIo3XP7IhQSAA1CgzQDh1nB3shwb/ABqPRTdHPHw6IIEPYA3dfyqhXeRyu5b387QpmMIl1ZKLiESaXUiEw0Oqg9UH1F+8L8xB9ZfjIPrL8L7X4y/MWLqF+oL8xfmL8BfhL8pfjfa/F+1+D9r8X7X4n2rOlf3/AM3ChVUDgZ5lvRPo91dW/Ou9V/6IVwp8AIDh2VHyLrUGjllBf2ViQCvMBPUiYY9BlU8yLZGxSrqtU/q/vpCA8K8BCR+SZlNKs4wlEY/O3ZadBDeSIybSDlYSk0XT/CtR90bo1ESqtttz21TU9pIhvMQrjbk+F5b2V3gaI/M7epaaZqpvBWxp3hfZD5vZeZ9vV10UUV4/2XmPZeS9v8ZWFBQZSV3KGqeRb0dN78B+fd6XlJ8Ie5QzImdhEKtlNP6iIJBvFkPJ8IfF7J0H6kCxYYvXHJE8BhsBcMyvdvQT+2nyAUdUGwonhYxC2AYF1SBEZvZAB6o+lvQODQOL7Ln4Vgoqk3Vx38XT33HsoqENi38SY91dkdLyQ6hEadBFU3IvwE1N6dgfOq8r5X6f2g+/9r9dfp/a/a+1+l9rB86rwvlYKx891h5brHy3Xm+1l47rPx3Wfhus/HdWlnnKz6P2svHdXdH9prdl/nVV4eG6nWPYumODNw6ZeZVHn3ehlRlN5hpEA5YdEBA7kThFB9T2RXUsqdTsPdXdv7Q1fJ9r8z7TPhrYoCj15lBq8RCUFNEFc/8AB0FNI0V1Kx2qPdFXlH/AqsrwjtHD0haPN9kI9t+S/ET8FfvAtyd/KBSgnihlTwKUouVVlfQuXpldHk4V5vATD1Lj6lxDmP8AnYlV4dhODVQ5+/offHvwa8+7i6YFOxOtIRks6GvN5FkBkSQDnMQmBTdLWldiNi8n9IT8v0mUkYTgB1rUZ5XRYN6VWpugVJ0xTEB04/xdDgDITVHoCHEcQggh6Qggh6X4Mh6tfRr6JVVJ4Ek9/c9EmhHTT+VdwfjNX2I0rENLnhCfUGwsDnJlfb5CsbdDqPhlFII+F1f1hfxU1B+WUXld0Xl+wrHSZTXICuIWAgciUUKa4VyTi0xAYQXGRKcDi3+QKHAeof8ACEP8bcY9VVPA5SybfYQ4hk34fefcn9D7y0/rLX0Kc+PlaHlPymNJ/F0z7B/VQAc2Ukb550VBGzvP2yK/nNCx9kSZDishmzCZhKk6vCK0cMUXeFVW24/DCl7Ajg8ETUoqCUd00AIJoBI4Mel/U3+WvBlqtuDVarXiD6BxH/AlV4NzffDSfCS8gICzqhl9kM4htEEAMkIOuuU5mt3C7FqYKSclDwaF8LE9HN/smU7nyhEP8JwpaKsPhC4Es9LcmBbCvuhDVmwYQzUTtvCuO9OAl53fHCvEM6D7A6jAzdvlfDIgmjKkHM8219Wvp1/0biEMoZQQygtUOOqGVqtVqteI9S3rhSmPdAFdhDOl0bnU7uqJc0O3PhCkbIAZI8HRazTgVZZHVngdgfJHVc42RB3TKtT+BGZt1B0JPyQgzGg9IOwngoRr8n2jsciBQHILdygT3CHyVptwIfJBHwQClXgE3kiYGuRmCVdQgsAgJ7dU+7p4bmiXTAeqslK+Agg1WDoXl+lg87LCmNMR1X9lh8bLCm74xw39V/VfxcJ4fpYPOywdP0vF9LwfSwedl+3knA8cg1lGbDC959HWXjjUC3VlPMqimHQqwFtcmNBrGDAsBfGm0TCIP3qUaFuFWQHZ2hwiFh6rChW9Vh1cBgmPcsbsrDuVvuWHfxn/ABhSg9LMz/uEYGQbaE/SAQaqvAT9FezFWnxKkyucPQx4RBMsCMo2stzKwFzTkjahpfSFsFKgjEuzK2kQdgEVI0mHNGCDSH0kIDaZ+v6PAUeWpaHmV/wyOCQSb6mdyyBTjg5bFFsZ+SzBxCngAbA9Mew6o8LT0WQ6I/4t3JEjt2V5uSO/p9Fn6fRHf0+iP8PpHFyH0hfpcDB9zhcdbR+1N/ABDIcUPpy8Q8bor5+tHsMZ/FNiBHncD68ZziK0HJ1Q7xEiLosPHh1gEIp7sBMqbdZGKahG1ICDzqGqCgOAfyvuh8fvwSOHOIlUNqH6kfID98ZP+EZVUyOGR6DSepQaUI3MFkZdWjB8KklGiXuAq1YjHkr6KDvPbMn3JyB5DtQxRHB67xMyy6EEy37KFqjboBPwqq8ZV3UAR1GEBgzjN6IRg0GCp6G43d8oQxTEANecw5R+S1mbIylSHWQi4qc51S0NwIUP5FHqOg5xQ5JrbjuvMJgIks8QjmgESAtACN3Wa+68MItDoaWIh9wlsHW6IrAsQ5PhjLyeyKq5kqiU5VTM8Ngf2UqoXSX4MfARfYPpHnqv6LX1TkYIgMg8zTdAPUlTkjU/Z8ny6KFSDoWHFCD9z0OCtnoC6ojs2z7KKxALpgmFUENUEEOIGQxxOpI/xqiZEtFp7zO2p2IDBgDMITKl+IIoYdkyyM/F5HAKO6yTElHJRyi4HumFCNkFpXDIGFRUwdD7ii3B4BZKRooepinkn1+AkuifnsiXQaBS3RuoglAHsmThwCwZxs4ODxtAwjpD0DR02f2MGbikRuroyNsk89X1ShGfYKxbjtLtoYqlmN90VaiZfCt30TwEGKoHYYCEtyXk+gqKcGi0QTJzdB6ODgDsqQwTNJQKIoTMBqLHKlR6QDGnsibH8ITFAIAs/DdHVFFHgfQDlFHix/zSqqOEiwDykdimyaCIAEDTyte68BZLLgaU09FmFkvIRusEcI4RxKGjLNWgfdMkVQDpApC5Hhd4gCEtL44LomAByfDKHKpvFujB6UH7FIoY0eH+XIqwE3Q/s96gzqYRzwxzrUEPjvoYvkuB2VO6c84IiBGgeMM7bIvQjhZcwCWPcIAgIBeXTa/GqijBC0gzUKnLF5DYtAQ6GPAagcXKu6lyVA8CC61BtxiPTl/xAePtwQDr2AoQBFNKOSmXNMmgmLP63ZBUIPYwF1OgFufl1r/p7vTHEMnWLC/bh7xVFyBnLSMn8oriR2DYrIsnZfBM9yhEPNbOqh15bL2qx6lj2cBikYKxTFGrjoqgQIuiRHIuhoUeO0237+JxXVOzT9g7kbQ8jyDkqEPaHDEEnBAH+jb7o+oweiyzFvaAF7TEiZZQGOQQDolTNKyDLmCNx2Qx2Q0/7EIiMgLCgTEgjdFuuvwoLjP1Izp3B9wUp5LEj4OafRpE6F2uS9HzuMEP9lNzxue3avuop7Dg8FKlLGvboDQtkghXBbk7oIJIAqS2BlCU5AFAvIxrxqlAPLEzg7ZDBiTaKrWlShCPZ4+7Bsv0L3WcYbpoUMcNP8IU+slxe4OgYHQCeZ+Q5IFB8oLeyDPR1aSZunCPwI5I27iOLbFY40KwWP2/pfsIfpK/eX7H0iuT9BfvIfvL9hfZl++gcs2g9nuXgKNQNGLI7EDJUaKpX5ZUAOctaV3fFIKJn8EOWej9r64G8N7cFDegoEwKnItfcApmAt+iOx+OV5D3Trp4DS4JHXhQXyD8Y8kbXJ9Bu+kP8AGUbAIndukDiG3GhDQj/ACcHKIb9x+AmOCAHMtRFolwFl+EzO8ozoISwnPNKM5iDeTyhQ2FYCBW9eRsNKvJPUN3yZScEAQLhIgqhXjWeMOG47dIQ6Az6GHqOTgVuyBgj6GBVu5/SzI5C52aq1jYEPJoPtRJcLMPtAo+zusfBhGYxfJU9xI6ecypBuQE5SsvleR5yQeI6p0FZlHP9kN8acOEw1Qod12QrzwuGI2RHhKE2GAIKofBuFW8pkQi721hiy2o64UdQUu6kmCpFi5o91I9hAh8yhWj86dYJLXoMJ6iQvC9iqVPjVeT9rQuqaAjVua6jvQ3dNFN/lDZmrv1PgGg/r+Uy8oxt1J0sZ8cJXuCV4AaihFzJEVFIBrYD3JlknzHUdAym12wO1Noo+4YEEiqJc29pRaSO3pIrd6Zk5bp8oGgMLgM5vujexRyaXGqboZILjCZUBifzx2ENh5LPPr+EBAQ5kb3GLURp9K/ggMgnCf80wA6fXoT63ws8tUT8LIYcHL7ImpHk3yhrO7q/vAIQDdXuQQxN7ALRqgbFbVOk2kEosh1qeS3dULDnKysB1u5pv6R67ETqDsUUOvsjjqVTVOB0WJ7J7tkcI4Ig/gmLFs1Fb2/ZBJB5uVOSF8CCx9nyqMwbhYDojMr2IX7CDJQOoF3RSCHR3ugRcz1t7JjU3JA3s+09G9lkkQYA81koWF+uieIHLBUyaV+kAgNeSflVki9xZO4I6ymEk3+qFQbEMD5otqALn2iV01DZHaNlKiKQrHoCgBKCbjali2UxMA8GMa6ohqs+Fc/UdyjbDq6QksIUuJA91Yx3+lyAXwpJr9qA5saQ6a7IEdSOADI69l1DwZCB+5+lgOo+6ArHINMJrlLt2CJsWhHBRMI68U+pg5QXDHR+CNNoh4cJ6Wx5UV+hKOhGXFOTfj+6/P91+L7p3g9V2mPXWwDK+sEVgYIrIDNlj2i2SaB0QBC3J14ND8rom/WBOrl9+E5GhKYPCn6pX4NJKgJLDY1GfaTxvdBVcUN46njrjnD04od6yZrcDQBkKzRVFUsSMvfghMDkH4r7DvmqligR6AlcvnKByYPF10SAdq51vyGRnAL9TOtk9e1DQajJV3VZM7kmrIFToq/cI7jtSEySSdxWsAYRgbpzG3qtF0QSEOJp7oAmGbZCTOjMpVCFWZ80ooemEqoVQU8dxCtU+6ZD8LsvO+3CVgPPKwdR9/CQmPphAjRFpWJ1FOhqw50ojjJPxUoMAAwgBgK3/pOaTAlEa5wLnV5oJCKJfgGSbIkaHMBiP4dRVXvKa/CZCZr8MmUpeUEEg1TpaqkuJF3ymMalnpzQFBqf3knI2LBh2Rq9/6qIhiK3/gRPRFE+YK0hsOs2MgRuOBEDRCGOLI8GDDR77ASVST0djugPkdl42PfRRuPDLHB5Telwtt2gU85poZMhKwvlGAgOpXNxeHLjXc+qn+L/wCr8Z9JT8uE+p/5waLlPyUB7DVWfOjSGp7qxjql+B8kzQ3smkzGxQ0frtu6gWushkP4muYwilaIiAlpaJUg762GU5o5jzdGx/bIbTiG0QY9gxn4Tu0t4qtC4o0MovU+AjBX5uyEs/pAGgnQEirgWwx6oU+p2C025wqEDwlQnU+Cf+kLHA2/4H4ESAEOXM5QUlDRDeyFwh4Cciug2fKasvPMhVzWlzt0QKXPgzH6mECQ6dcIHR3HVAG56G0VJMkynMDl7dXZAVKm7GSqDWroiQqRU/aJ6ODR/UDJtTVzPZQNtWunkk22Fo4sqHgnWaoAqWB9p8HzfGjIcOiPbBd22uNhJR3Nz4eeC3XgCc3qnYfxRdEZDK8dUNcmf6zvThVPwso4mEPskdJPCSoXwp8E/wDnOUqclVD0HsPdQMP9Am79Bde2TI7HUoRIW7gc1zdAmreDJx2qnRQEOf8AEBQG7mrw60MBPynBYOWHRhLqMkPOmx7oHoJLMIp4U7lFH2TweftRFWg/isa66cygSEMSQ5rRwOgoFd+aMogmLs8iwaEHQHbN3NyJqjN4obS4jDK5O7IBQpWaPj3WiPWJ+CdKUAu0QYXKKHui/wBghC6lV9TDkoDxL9qSrwlRwk+E/wDG3DPown/wb1T6TQVMDcqSwIbxdCs+EdPgsn0GwYjlgBBhEXoBQJo8lHPV2Nj8inHInmiJLnnGgWB1tKBBQGJs1dd0IBb7JyGGATTkiAi1TRASBwphAtB4kDX7VnVUCIdYxVVLNrtMpNqxwmwqu2QhLkkq55oYKl4Or4KdE9fjPF0wBBYhAe9lZ5ADsn8SqK6wI6KGwjq2yLOaAEP5IGpz6ZUcGBTDTuAoO3GFHDwL/wCjf8LlynQGwnoQcf8AD65LGZ7dWc/5YhYXM/mqlI2B5xCxPKrbtBVPVKsvFKHxb5BUdYTwXGltoTAMfABGxG+xOJACCQXguLfnoALEiTAudhUqZ5kdIYI3nAHMpM56H0RSLXEC9z2wgMl6DYeUz0J3qfDZQObCHRjex7lEwe1PsF2IY1KJoDZ93kKZaDhhCOoZGlZpVAkHqNBVAUd27oEA+z2ujLY5jlKYwo0XspvYYxpIa89EKxYQOZxCzO5QIKCBnB+XDl8b5h85X8cRkHHGaBwz4vFKdDVdpCFrA8PYIIDIFoZAsGl0EASV2jUdNOE+piTPg5LqDsp4QoVN15F/Xp/o/wDiyY0O58hjWCNOdTZ/Wi6/paLgKQ+RoegKBDOuh8E6AKYJ3UvIwliaGGGd8tz2UQq2ygkLOuHJCCOC2rDBUJklIwYC07wpgSlah+UFNI9AYDDishnE2Pd2QjZX8kCF1EJCgOWfyxESoK3bBBPOSxrlyVw9O5qu1EVWhedROBqVIbPrumQwGoH0PAIO0gQDIBrizKatSR0VCoxBqHlCwl1qaamKMaj/AED31hAD4ERDdiaR7nVz3Ts93itkZGG6yhmkXuKEZJvFTFEGTS1Q13ooMNjBwvbRODnC2wpdgPWkIVlsHy/RMJliIJHB+FC9g2W4EBwCWCFQjlEHzseFC8fHXqm7oaSeP8icthUTIp1B4RwOQdiqpPCFCpuvMv8A5N63UJ/8ALiwErctE3ZApjIns4lvrnqyeIQYkwCrznYMgsqixUIYAmW5y93cl0DJQoGYbEVSb4dIMsVXfapb0IjZrvAIFiIkfBUgC2JmpQKoJ0kODkMrQhyEzHwMrRPSEVAXY7g0JWKS2l9vvyuK1u5E00fCipuQhcuUOGoOQGi0B7jtg0RSNRYYhNYXYs+6SJdWo2bIBIbdUmQ1xP73RiNwK6B0Q3B0espgyTsPtVES5x5RE4AmyeUozNIkjOzK7gXYBAyFBSoPoAsVL5EIXiSzjRNUcZyaqsUXpNkFxGhG8PcrpgCqlLQejq0vhQlQT6HU9FHGE+yfaFHCUwUKV5l/+J/8ZKl6T2SoUo/UHgu+hIQCmP6Tgl0kuBp2DeUnuqFByIoxKAHTEYtJXUUp3WXc9EeFomlMHXwZSLkQFLyYnsWUXdGXz6yHN/QkEIM/cpGKQUcgEOuJc5SWboRSReHJ5LT52sjpZ7EBmo74AP5MMBQDlvYfEpzaFOxjonath/aitQtByA8qhUMKvYed1JfDYVb6ynFzfD11lM9LDWYNlymYA+3sgTRMgBtiMCLvYDn7I42oHIc/KL0ON3LRYFx6nd0XY/8AbZpKJqw/OR/YTt4JTdEbhIsDJMOqE7rWbC5glAOgQOXsQ+h/efZAeFVjG/GWg8C/4TQfTXh3QEqFCgq+AfZOXJe54yU4UKf+Uu3qwyGoLPk4rF3otsS1HJBqgf8AfVRoWvDQg6fsxNvaKuQUZkbyIJQEvsj6oTsQ4OkAd8j0iPAlLDYJK78LkUCBPcEAHBnEL+nb2xkAPvE107IikjEJpaSZjG88DYJpmGoL/QveQt58Vs9DoAqZlcHQZQqO0sAqDxSHGeTozWH6ZdF5QlzRVQzqaPGQLUN58KjYeMouDiWasG8ytVzNB2S3dNugBpy0TQCHjUr2qmT2MknfwIgIgC8CeYqXIbd+hWnNrX+VLFEiUW2TII50pZrFGYIRggqPxCJ90gOghicB/Tc8SYI4UIUBZZj6kwzrRwnEUL7fF/TCf0M90wTGwfCODJ3KExddf/w9v8dhfI99GtFvRAOPaoZ8mb6ZOpJ8FXByIvsfwFyGBWDjwfEzKnU8hwhCG+IIswBMCAaJEjlQ/UYZNH4IdOSOXUzMNAslSpTgfehDxMQmeccrEpXH+iHQJIHiuo5+j6vhFHJoKlAAUCLnTsE1tlKaOwILLomFWe6LBQ/U7WUBvbigdQYPSud0wjJBto0ZDIgS5s4wHUp95wXM0H3CeExleqzFpNLOW6qiMblO0lTYDl2Mgo28IBxgjfyEJLC7Zug0FKYD9QirrVTup9HnSTukh1CvlFPAfwgQFAYEoB2kV0Z6n11F29Ch3In7KgbC7gjyqFWPcOMI2WHYGgu4vHosm1QQqcKqqjmo4dZ7D/qALoTkJ3RYE+7Dki7JkhWAP6WiaBJbW6j/AAwCVIdQG0vIaUDCQK1nJSN6QtUSBR+VCMoUZiA7ABTWwqit7otTCI+hj/ldDgOLMul8u4FGFweonY4hyp3ri6hB7qAoPEEAcLaihFgBZae3uGh5VSxTgImg6pAvdSG3TCDkIoDur0RSNBaGrO6g6k2IBxzRbCsU8KYKgHZ2yP3AdtVB1kZs/IKYA30Xn28ZjLnA7vhkDtOz8ig4vNjdSqA+gUCOwvHX4lZkVc1yFyc/kJJ/uYVsFXMPxhFH2eLP0QlxUrPNfU+azUDyKKh6PERwve6/aQJbJYnQfmClAcB20O3HsmUcKqevoqoUKSvJgf8AFhR622CdWD5NVBiLmvIQ7DlnasGaGsG17YFJMTZc9y7cn6JMke9wZWCPmEyR7FTsRUYKuAqYZLQbBs4AB0kQ1owmGOBAHky8k4sVvzs6UBU5XikM4RHzUwggCizRtqG6CnWcIUhWJE2FPOZIEqjfcWHEdARZ2HQRcgum1PTb6Rlnzd9ORQkHJ+XugiSd3lKycM/fupLJ55aGrdG7uw837J3jcmzCFo91OoyBz5iBkZp29k8ONDWleYorPZFdySe6NjUir3R4z3I0EpQ3JUKoPLMC9i0A4BmNOIBLgrqH9VX0izqPgveiXUZjiCG2o+VISRFnVFWefB+MJnUlGQ8YUlQmcpXgwP8Aqvy8a0Uu4CwoCBaGz4SkFLrmE+G6YaQk6AY2z9SCmr0P3HqAqokQ4dwOuICBugS8p/gBo2QLvEUj0SiWMDP4CEVwhzvEHmpMkfaXERKO8c+w8kIPKTQPYEb16XK7iscsmXN2IKLAzUnoIScRtn+qOCcJ3AOGuChHotR0y+puBfzwTuo5GfpZRHQUjd90SzCTcav3Km/R15IFhimrHpqWkAwR+EWsNMkWSaYwg5kIBPdsoFIqEtS6sJ1D0t+qaLPCGGegwodhZIAqA7m7KboBQjYacTegUWCg+iHHAsfW8phxhQnAo4QVJ4nXXfH/AA6cW9LAnAKt12qAom0zPodQm4SXBpQIceZGA1AToRaK7V+yAAjQ0oHg9pU1zfLgmGXELmrMixZ6iJvywyk48Oo3xQ2jp1HA3PjKS1zJwF2APcvZQpnkDJMuedFc+ia670dKfJYtZBvdZim27Qn6NFAkJNBo8wgTAkoNNFihOogKB4Y0XKc0HpLFW7elk7pNGOuqmNQe08iawucp3Psjc9PtCKOXWfUwUyyWjIkF3nxCIQyhO+JpCpBWhnTYQyb8oqouMLZzNECBu7togbDKqLTp80YNhCsNUKnYWuUISEshzXc+k1AuwDUHIxyBRewn4HYIzIjc73dt3TQ61e46FkRPhu3u0ToF8XVRyucByyC2PF03JOFX0QKFCgqvCODeCg/6TyihIh4RD6pt8PpGtUILLrVcUFaAuailfV5nWvmBDpQfMSwVfmEvdQQ+AChScOSMFeNmQrdYHRhw51udUgk0LSb+gBTU9o19oaLaszgafAibYKhoxUdV8XYB4ZojOyLO88gfZF7GuOWldVo99KEJyIE6KRYkkDSCDu/VCuEeOqYVQOjPNEKpP2gGp8NB0dB2ObGtB4SqT4YtDoQpCZ0cfaaSQ55mqEHM9PnyFbDhmpaTAfwyi2mlyhzIZP3gj4R5zROyDDXGoH5tHVOARdXq0kZAlVaJzxpRp754bZTsmcv/AJhCHngZIceDzdd+EJuMnR+AhQqqvCOaqm5fs/429A4UFRuInBAOWO0coRoysdj0cz7rvgRmL6Wzv1FY0XdGPaC6A5MYxaGu8AdVRBIkHZPK4C6FAQFTFD8BGCHmQe+DU61pchX1B6FAE8RAOmHWoK/nT0RZsCH4WljCNRA88Ro2N0O5Dab9Eyh4cikt/CQjIGFQCAKIoLpg6nLBParl9ClUqrQn6RCTsGdto5IidFKyHsfhQuGAfqLb6p+9I06bBA+oaqQ9hCDE9UgcqM3livGG8qo+TD06JwMdXgVASTZjdAV8eLlpvkUHUaA6gkTRF6WXMYWDFxSCwNg/Apw3FAjpY3RtF2R6DEIQ14e5dUO8k7JkE5O4UMjBE0q6XMdVPKMD6PkrJuFsq6jhfd41TPwcL2T7/wAP82/2EniYUEOAdcoMPNkPaqyookpaCRObrbYFi/I5Jp0OLux4ADIiTQ59igANeSGAoPQYLizrEt1dKMRIYlk8cB4aOhD2i3WqIXqLC/N4JAqB28okjQjQIClxQAhnTAKn6SwQGiTcWe6RNF6AJATcamCMQfENvcgYUG/lk7Bkcx/qEzoFPAqMwcwL/wB5LXVgNvAVR0VbdWFwWBA6UKDkBL2edEI6wA3M5UDBoqYZpVTA63dLJ63CSfYIawCwfKS51Qj2F7+yHnBkdji1gDXCdcDWMDs+BP5mH/ifocMy7yQp+qB+cYfgTR6IDL+Fd5JTIJNTfjCnhBTaymdSqqTwqoUKq649n+j/AOHT06RX1LfKruGDquYJHg+0I6IDQAe5LCB5fArKGjvKjeACjTLEG1FGgQgV+DKQP7BHQjHxIk6qWLigTYlJAsHvQv8ASS81exIEVJEykKNyHcJ4cCm99AiXRDqQ+GQrBH23ex8EV6dp90IHRTyXC84uj5QwAL8ExJIbqzNxyhqnXaY7yiD4fWkpgIQ/wFC8YpsYTmDH5XQ2ATW0cgunPVzjy6BkcDqfoMVRd41qWHhKKRGiLtUT2QACOjufpdw/KbKoB5V3UcwWwTomYeAaIHsTQGEBVhMf1ZE9BmeSs8aVmOvgDoi7tUe8AQo39wDk6GF8pAkSZJ9HUFVUUuQ0GigaiTsMnRxwjg4KYFObKXUFV4V4RwZ4ORJfC8v6v2/i/fwSODxp6ul60Zw6FOhUOR0IcjoTxjhBk4UWwFXxqhQ2Zup+UUtQ43XjHBMZqCaVh1BURiCe8Lmi+uIaqhSe/wCF2a9BzIsk8HcXhZCsj/BCBd0+sDuOz777roN7aK41pEupEBDE5loZDIAJKpDWwUYF9kG1RZ841DxDaBIjpiMUwCNAZUe/VxB8E6Q3zqfkaGhINAAHi8PusWan80BIqPyayY9/MOwIzuhlOu4ICHsJbA7oAHfehe1sFvYuYCm4S86ovJJk1Hhu6eneV/UBYN14dM9wfs+ioDqxhlBctYVQgtN5FM8iyu+OSu4HxHd0DyQiZ/2svI+Fh4mJSZqwAC4F+ziF2b/O2VXhClsuyhVVUz8aeAQAGvA+hH+/C8v3jX9l/ZYuH/RYOq/vwcUaof0sSxMsXoANY0S4s2WD81T1QqSBCewC7aXtGsoIewEZelqaxULsQFCCjyEYOEIKCTgAN+UFWza1iqUBpRG+/GkY2CILAJIZC4/cy1KKyZriiAnkkTgEK2ybYVXDoUsceyUAflLLK0W/lerKkrTkMD4GTlSSbwZ/CnRo1B5TUFTnKmcm8fjflVBbY3UiqA6j/my3M+9WvkoBoh1XGhpqoOj+xyPp6HQhiKnJqPGEJIEtkzm2iLPQl5/XQHBDULzVU2QfmcolYchj4PyRXz7H5p5FPp7rEsCxJgAKRs9x0Y7iK0h2EEyWvTBNv8WHospjh1cKqvF86Cmw/VImpU36prFN00nehHyp3yUMur6QiXX9LJ4aLJ1fSyeGi8T4Q8Hwh4PhDxfCHk+EM+r6Q/p9IeD4Qt5NkPB8KHg6LwvheF8LA9f0goCqMkOk5kmj0Tm6B2rFNMAb7laXDwRcIr6NPsiLC0q5u1BDfRNkQumcZ73n4gjKGFd/DVDQTWiByRSmBROuGEkMxVz8QasHR1kfCGyizM78gG5DoQek1CKApQAF4Ju5JoyO5rFAPBjN2MEBhkkuQsYMAc9xMYNqNwyjUcs8iMhFuo5ZxsnJlEDUDlXzKEmWMeOT7IVAMIF+4QGNZ0fTM80IObW/6g1YUFnaPpaDSmhoUbEZ6K9bsMAno8oq+OofwojHwJCKAaZKahGkRYoHJfsr9lfsrHqfS8j4QBYR3MgzpWCNTym7ZtCuAcMIbvcgCVpa2PQPrhRw+U6W14WVeE8CzCsP1MjKl9VKfhrxGU3+J/yMdibtcum8L0JMrmCO6lJBeI7K+qYqP0gQWAbgQ5iUsThfgEGVGoqvPmp7AItl4dcTmUskg71p6mEOQGjBYxeCmRJFYxww/IpZ2OIOGSy87J8VI3TVFpEjNRCHl/ADoyw3MwIADCqZbp4DZHkMP4gEgTfkWiqMjWpCNSK6E7IcnUMnC2kpBJBobL4sbC62Bf2eBRA5OhhvVEQgS5BIvJ2OpB6geXKpLi79kbhQD+EOgm6MDADN0YSXg32XX0uZThuyCYTg1rcpClSxUqhSF8YLFlWHUAN2SUld5mQKYDbl8gVOVmE+EZAj2kIveRyEMuCwj9gDXhHCvByVEKeFdFB4WR0xwpy4hP8A4Z9Vv8RM9KA6unsW6czmZGpYwOwRVBBzvermDfoMbgQD8ZTQ0fdoCCJNEoRdbQgI2X8SuWQu3QcOaUElKAPhwmH61cSlJUiROwC0DKPkrELAmWHgSQuQCwkZN42Mt8oOCIz6aBQ/kCN5lIdKmHbhYumO5N3gq6A5Jc+iDtdD+DsoQcOEV2dxzUuNx5PyfImGBc17j4NETM4YpgIEcieycBD2Gh653KkTrQ+pUVcs8vnorA/YMLnCgnl8sMpxA7kdD0mqfQClm+p9Dvx0nOjKgiE7CQkMujCtIHOXynNZgled9FUBiPVUlGDFAsB/EFo65gTdro9UiQekIBCSBuUzPstR4meb3Db1QSdZ4VUHhVc5TspG4Ung6Pqbhp62/wAORQq8INl4BhmtlBU8yTnbcLUUrXiVcgfABAZrTo98FbgxI4bT42SJAQj1jUlV7D1AhuMXAQa5llewykfxEl/YBc2ViuDKRg+xCr/ey46ww9qqT81e8jQUGTqcE03SnQukQdESIDOljROZDr3fAj8QMWFaphCWPyf6RgEz3+SL0KD1/gM1EZuU8QfDKWTkYXGWRJLA0Nqid5TjZAzr2FYBVqZlPodiXIxNVJciHxch03ojhZUFn1w0903khG4AAo9MwsWa5ThorXtDFTk69lu7LJjq9qC+y0EztQp4eBiC5RKSVS9VcB4ITEnVse4KjjCqmNPxpKg8PJU/QTE3CVdNweeOnAehkPS6dZTIp1r1T7TVMDRR6LvB2bQVY3cCBAWUwUiBysCwh2PKgYCqbAYzO+oKEQbYCg8C0SsOABeTKSbgw+Z5hSgpLeSMkad9A6LLHQoaDGHRyCDZ4GgwQ1K+woFigiC8zKr+h8gGB8BligZDgsAW70Y20Tuy22iqwu+oP1WTo5Z05UMFnaigBg4moDyOwKbcWw7kdSylmJ65YhAGKlqvY9KoqBBi6K6Fw+DW7XNMqWK9UG9DDY/vqICr+8BEbnZDrG+RS0jo+SmpL51+kJyiMsZ9LlVKTvP1THwIzlkNQNcs5hzRzY6wmDVsqSk6g2QY4dPZvcJB4woTLzPCClSV6/JsmgXuffumHT3KZckDc0UXOUN9HWFfZaegqa6D1mEUtdp1FMPqaj/W22XfcE/nE7nYiN4azqAzHqTZcESTAQ0wZOQClLY/nEAJTyjqb3Mp1TG505qC+2IwGEY9wIbDm4uJOnCaFFBoCqFP2Hcsp7kcoHgWk/XxjoQvzJqaeFg90pverf8AkJYRhAqLMJI8Kwyo0xs5NpDTDVu6oFcXUwTgv8KuA1E90GDhbLksCrrcN1gkAOx8b4eZ/k10ZTuQdUJ5gTWOwRdh5cU2Ts8DB/UhxEnMT2+y1fgpyHNIDyyTq8QpRRnIRmQYIAa7gjy9UUJVjgwHHlU0cVVhs57k4Hls4yTcitrJ60qP16X4OpwhwhO7HugRm0WFF827hOLuU7eh+NUwUJ/RbiQxVaqfQ6YcGfcr3IcysGRAdhy2woHwkQB/fo+CkGF+9ELl+UeBoPCQJHgFSE/HO71oGcm5NPkAt7IyNyoyMjqqxOVLoQdWT3PtJKzkYLjmTQwosSovspkpFc3c97jSMnqPZs3u5AVcj8tLyoJXpaxqyiCTwUo424MDUohdWP1BVimTJ0xPFhXpBUKXJ4dPUcH4ONeLnQEbBSuqNTmZHjmEVOhMLbpooubIhUfcDMjumC0dyA10KrmtQJ2DhOAWpUX4CMTP1k0w5ql1IJy0q1emUwKk6lMnY6qnJg8F1KfgXvFFz1J+aUAJNJHYInbvQUOFOFGihckZEvwgoiRcpgS7VXQAmVQTqDqmDcIHByXytTGEVQSqBtt5b6G6BdKlgKabKeoMokDQj4nQCgfwiadBipQ/yU0GgTWNXSDeGYBbrZA9iLrelfGW3NKGNNlZIQToHiqQLvfUNCblyCzcISGa/bAwKil9geSZtoyHlmA6+SLH1BwKedKGKI4TLujaeyeAKcPwoeXCE6hs/C1InkmioPn6HqlN5jKKGZ4dy1hLPhURbw/NuPdGrkCBc25AQOXgZmSHXMQNQWolL80nYkVYEIVLuLKUNZqnMSErwgqE6QZyg6onJ4O0Hunco4DarqUW/ACn5VU3cfQ/hNwhNKo4zwnh24wg2F0uMJhqjjVUVFO4vETz+6u41sNBhupyGjBR+olKScA//ch3V0ELeAGi2uCAAp3Z/glskcnJTnVgnnnAIiOYR7SIgUjTcWn8gAKiFOphKPuzO2QgdWwfESZlIqy7XQJpw+UjViiMEWWQ/AIQKA3qjV+0XV+EYY8ddc+6YRKFWZ0/ChEVTcSdhVyd8RU/W5a54A+ps5t4Rim/TqtuY8GQbAIoHNUxCKhGvTBR5ZUQYRUr1WXgxvBhEx9zwOHXisoXYoKZSiAU5MBVAb3chKuZOjxBWd0MWOiqFXWPKvdUU8AgJ4u5z6Qpoyol0wXURxKdntI9NFKBNAEjQWWqy3Ce/BwMay1hRVMADEe0G+11KR8QkpkWjtHiB1C+L2Kuo5hPYNlkn5Cf+gSwR/gZFhTU1On1OMO7T0kHRvfkmeCkFkWCPtAFKsAkPfjCqMb1CWTKFvNiqoCbQsw0l29SNcbsN2YGRsAb0IEXJd1zAXZODZPwWU/Gd1lNwNnjLP8AYnveuiJcqIcTcRKh/o+0aDWeoXtlYFyHS3U6JYB+VUbBWg3fZRCUBPooKguLimDJy7UTugbqvhar3kc3AYl4Gs8v8GSFCup4mKFC7n7cGQRdXUTwoqKTurM6rJC3ebhsvJ0TqD+BEoQFtZHaQZwl5A1JlY+SDdRoO4BfNk/vIIVUsqxa+dFgj2ocpLILUCH7nQmkMg8gEHszGyaDq3g2KUETwQeQYYVVADhzUtNAPAPsroFUvANxKJkTlx4603SdsjhnqpDXB7JvLRONacer0BBEUHB+SZM9k8p9+EbTyKhzGFsPlGpOum9ZqAQd0yZVN1B6E5sRlQDFSYdXLgeapVlp8NSPe0n4omrs+Qr6rltUwTDdOVM2jUqEfFALkmNLyajzPByPwj7JkZ9MJwHNe/CE3CqooTBQOB7r4XwmgmIla0L+lXdMXsSDEy+VVyDAclZulF2Cj/cr5geqpixoP0O4VKAGXgkTwgiSv5zUaAoyKZFQXOi9pawMFSrbACA3roqFg+xW1UYast1JZYRigYsm4nNPOju8SRc7XUBgkCzMbmL10ACYMuxFDStU9h80zeLCNaKG0MSgWYDEjIOd7SkYKn8FUd+GE6rO/F29OMCjKijDxB3HqcsGXdBIsEaqPSbRHV2IAXKBZGPcD8KAhAzJENtaOTqiZCifcfIIWsQpHEF+DJTqnZS6bwJKbs3eFgo9nkrOAvaTsJK3eG1u3oueBWeCeDcX4U4PygpT+/BTZODzUDlwjgJ3XaLwWmAQmgCLKEEdFyynQChNcBaQMuUleUQqu+RlWRN/5HwKgfLI3ae45UpLCag+poPgaAObJXsTKUc4UTv5I9EBaCEXVyWxnJkcO5EjQTd9E18WFk7zCgeoo3jM9qblFq0ogQWRGUtwRcPoIrkO+0xsj7ruIbr7cYWFHBm08AdCNFFChZa6PsHdD1hsoQNiNampFkn0VQ197kshPIUQxYcmKMpgaxvOYsGu5+RwrxhP1KE5ZeJYRzrOtv2CdjE9f0U4PgZW9x9Ew2WeD/ChUTlQSU3BzzTngTSg4F1SFKfcXVWyp0R5R5FWUqCoUJzQyWt0DMklsXYLQIWQmj4EVnc5tc0MHjySkgk/s5Wqw71g1UnYh7jYd1RRTQdpBptuBKoSXFj3aDl17lDRPqGOBeLIUHIeQXxILA8tkJFWUTvtUCBgA3/TCksQsFSY8k0LcJqqbnTYcKx81hQZnPowmGrOcaQUboknrCTJ5lHTNy9Mpkx7jZLpwW3CYOfHQqzbo+FM1vv6XDYTcBtMCzJ1lhTogVTLO5ZFZ5R1uCMkdvQF3jorhQ/9UVOEcKpyTBFlXoDo0OvsgHvxTqIuNwTJNeDaoOpP15J4C04su3CiuiyqccIi5WVVRSpHBgU1uHRQLDg604NCDIX5evjoHuql2NCSrtbXIQhfxn71IJyNPPoloUUHoDQX5DBtEJP0HB+AuoIhQJYGKP8AQDShptYDtUeO4nObAIQdLISrvqa5lAElAHYCNTg0tZEULXUMvyJMVAqNOe09xF5zyPlqeQEHf1pjAdtaD6NgBbEGH6YR16W0SP8ATIUkqgy6R9y7zoUL9/mJgNQPZWTwDciapzhpT8HGVA2zu+l14dJ5FPK/YgEHiRoXXZciZ9OGEB3QoQglKUSQUTeqsDNROjmuVdOOb39FVBTvAXBQ9Rbm2DQhIVuVTkCV3WsR3NnMogTJqWpkpjwY6FXG/AlOTBqnUcKIEPdS6nynAa2UHZPz4GE8OjeWXNPwZqm5iedhq0HgAfdcstW6zKBo0XicI5AC2KCKAqQBisrT5HBsKY2LTcHbVl0i4oVVTdlFG+2CnukTlyITlbk+8pZUl1QKmgQt/ogHwKBFY1f2sCbOhpS0xw0SDn0EGhRWCZJHfBujpqCoKwFaYHWCq0PY/PAgoqgbD0+aoMg7M4MHY1TORr6LI61iW4lN7pt1NxAWOD4Y81UUogeaFED/ACFeCwFrWrjCqqqSdUQhcsm0EfJUwgSeOjkKOZvsLOiqnP8AHED1c8hwEnJ4MOICwrKAMH5qzUU7KpVdT7L2Uqg4MqicKQuhbITAlTkL5JhR3lTdCc1iCoGy+OHsKk/hkX7kQzXZSUbDZwghfBG3V2LXj5lSVG8NFEWNJfFErTVvMQtALYWLUMKpfiK+2NFJi/nXjmEIZtrW3OE6/qRg77iERwuLsJgwKH1XFFFcHkg85LteFtPlADmGXqckL8+eEEmatUqfIkAOWVZly3IKNj7rlKI3BMrXlQ29lJ4duAKYoLqXe74Te6b3AZvJWKKkOdL2TqycSgAD24VCaAxcxH2gU8iyezeX04Mb1rhS2e5ZFfQwJVeacsqtoHynqh5P3LWnt8A5ZOi8mAIeacL9ET3cLrvVM2CgJypRoDZ5hAnJ0lOXtZQ1Vk5VVA2JhvwB5VA7oKBy91FKOhTDKFpVN4wjpjSDo5seaWRKcmmKiCmonVge9SdCXuLIWfJi6InxynBv6UcoTUsFBQO7q2LBL5QUXTrmk4LzCpNwceyJQZaXYV/oROG9QWN3AmmWRXuYvGBdF/yK9KeQUIYYRJR3FCaTL98uUQjNoQLADQfNd0/ilOsETP66V2cHE8OyoBV9EKld0AwmfGD1TgZCDyqmLo4MxsjdWS1uA2KdioKIdF1MR4og7FGbY/aJYGuhWMK2rUyFig86In4IGLGuXmV9OfogqDzRJHEARrVyCu5ugLnohQB8qs8+BpLG2hVUzso3VlAMnI26IxsqaoEhPsVBIqQcBzCQca5Qt3x5h0NAjlUfYM7MUBLTMuTCiMpfgE4pCrFGlSVEqHody8ekJclzxDJ4JR24N/hrlZqQlEgCBww2dsRUIFc8TBfD4EGFAixAHNNA9kJ3QJp+sCEHMhqH2pVpVgLrE0JewHSl4oJQWQ/V3ad1Hox7QaFVE7MAvyQDPgxP0K4609IjYtiXQZZOH7Y8DKEpQzz1R2rf9lNsNd3ngQqTzg90wFaCaT4GWgKQcknPY3AQqOurp2Ij2aUiioO6NCRf0VcsymSDdBAJoH30nfEQvUIS7KtJpZMIoUGxrlk01odGGVGpZo1TZH9wUIBHFIKgjMfiCEjP0NfxVMvRZMGEP0hMbE/AZCNNkQJ0IatBQ1PiUy1K0zdBQZJ1kQ1UNFNQ6bACG1hQlECj0OjNUz3E56CghCMAOh4HJURvMHuHSO5aQHUxYCArTA2glwMJyAtYHI9gy6WI7XgC0Ji3e4TshyEFgqw69VRcopqLKIOOzCTc9hujEqTsElEwzU4SjQre5wHkFRa1gagUMLm6ZNwhVRJ4ge6Fa6pd8Jh4bdyCtwcsW9b4hMmOwUEhVTunRlQwAGG+1Xk6oDNAoAU3nUQRJgMGE1zlkXXyoIHIeCch3VMe7aZrTCNaJOsZBmwKmLO3La62XhH7Jwr2igXbS4hUUchllMqjYnNY+ainZRyoDYdANU/1WB3UuiqNrnoE+pQIhz0QoUL0Uw2DkGGWXi6LYwNR4obnTE73po7JVFeANlULwQCpjRXBxKcSBL+Bha1DJhp1TE0ZqgQngTEHOWAv8RQOvze4mHE/rCc8m0CeqgVl28rInzLpdKvJVUOc5U+KyEc46fgqqM+qa+Ud8xydSD993IccvQw+Tq0KY1EEvIU2djUBn1UISF0BEbrlmQav63QE2RCDeLpw1VPE0I2LahcVtVyA0boa2hAqIA/ImEImrVQ0RlWudwEP3MLYBApU8BFym4QX8BH5JiJXBkZ8KIsPMWSYkqqIqQaVm6valaGXDoUoZ9hDgCHZaVCJ5B4AuypIHVzsFiidU3MiXqYmQWyUWabxGXC+4CwUVCjyEBb18BO20bdLHB5FCwGndS2hBQcN8HrkFy36CEMWqH1mMmRP0AqjxFzX5XgkWysJOd7PRcB2OL8XIUItap4jQBmIe6aAk+/7oEUc58aiohS3MEUHVHcNwc91dEpmBcxFllBpUAc1R9UQpuQM9oDVQf6yFuahb8BzlwkgtMXIPcoAzgE+R3XNxj2pXQunmVNHRrLUkWfIo6JEwHkC3wFQkgQUYEw2IxQ/S20EYCS9yq0QD/Aa68A2Y9L9IG5EiOQkmBp+sni2E841wTAAYFRurIUkG/gknoJlRnyIObOEQiyUyzIUH4L+FkYrljkI2Iqpu1wpxYG/LVcitb7BROkIN6cuEU4iNbO+BWgCwMbInLOBzRXLDqDRN9DVt0FLrCtRpsY9kJyGSgvFgeflJqhHU2CYbPVHhVQ70fySiwi5WJkOsmZj1Z/dPRBCskAaDkDHugRsH9FA6jzuiMIHWVkeIArFvBhJ3+QUVeQ9gA6oWTYL7QiAqKdm0hAzIPt4mHUTimzRtC05374qsuZqCEJtgN16x5iMmxWK3lnDoRG6TBNYH6IuVT13YrZ+Uyq3HV4NDp1WzMUeiGgYy2pH6ESMFrErwylIU6vIMIUOk7tASfKssLycVeABZaqg2bUsJ0DorUEbxVFa8EiAFIv7GTboZJWYErfHjSqpmIEnTCGup2Pj3KM78cD1RSBCWpNeBOv5h7vamjKZdqKD3MFZ1Aa9lHZUyhOzX4E0WWkMlUwdREwgENUFoWAhylDdifOEDY5RfyCNlELm0DsCA3Gtyoaao2e0kHyAurf61TIgEJwmh3igI1J7AMvSgpWFU3tkjOsZB5JgtX2juK5LKk946zZPlDhh0GlUzBbHIH3Ls0d7+oqs3SWb7GBYWRGeoAAl3Q+65iRE16NapP1G8mtiypyWUScdLKydIWJ5mso7kOiFmKEx6GjW6gBhwfI20IODUAJ1RMBlBYdTNXoj4qAnM0GGhGqSoFbShmFO/aKCZISXc0QnUZdAeyo5dPAoWkBr/ASqeqmb80wUlz0HoCeMlXNG/wBVCvQen9qL7ALebWwvcmBn/UWUbyDEptMeic3ihh5AJmiRZTlBW4sAwdIYM/5DmEL3D3QXAQBVgMohKUYSex2VEA25RO/wLCdPG9zKKpPgKWpbrKpNoVcHcTJhEez+oTbO+N4DkOYokFcyMkWQhRTgaG0yAx/0jGu7+yOynPXQgDqT0k8HalWkYF/JYx12QBaaD4FWJp85oGKJw2aLdkwQ6fs4hWN/oqlcHyqIYlNi8iUYGV9lzEFGyjOhjG4vwlSU5B6W+pzKzA3zKJ6u1iw8cF4aVL8yqVB0CJcEntCmaB4TsqCsqdA5Tuw550CnwHYo3a1fe7RAFgeZFpOwCtShTgP1ECkhJS6Bch+huAwiJWLw7mu7mgKgSHevfIdRH5kXR0qgd/uJPNjPcchSq5XgsIADVM8Ll0reEYaYNzJMMQqVVW+boAC4FtiHMshXTApERIV1RBiAg509s4gAC0s2lOKyRl0uMlAXII7pGGqTsAujojoAJvR8nKA5YEs+EMR5PdwwRy7zkwfVCCUcz3PIg1mqTyFeUSQqS3iFKsMRgWmwqkwH6BsHVCEZEMG0SjOrJotGioqPQAfCqsLBI5vHTdk+Bk7Eu6DbBMtD2KMS5djAeaIKA8hpUI651g1GSo1sug3iK1TyhA3qQumYEQ5gQSnAH44Wu+VzIVKJQBdBfX0HSGoKJx5yEHW5Ru8ofMa3dYhNWGmRkyD4xOB9idJGTkkSZioDYIlh5UTk3U6kXEHI7p3Tx8xLU52U7ah0iqY7p0oabgizmW+MfXmWUP1T3AG6RlEj+elJcDRWTs2NgYbvdAlSuocxPsm1hYDvYZgX2hUxXVJ2w0q6SVEOd068dkUefW34gB/+EaIBLAcf1oVkqqqtsSsT/P1lfhqbuiWucaUAdFKOG+mPy6BAVgADkqOhF/sF1MKC2WU9FUqpTMXTkYksla5zY4O5tV0VEGcy5CnEj9TqKsqPHUHZrXKoRC0d4nuO42yDFmfJb56ahLeMsw6JgANjgkhM7LjkyGxgg1/TEdwFHmgYAxHMpIbUikC6Ak0zEdicfdcjiZUaDKIgMPnUIQBSMD61YMotKEMcw+IlE3L4/WFx0FJWBb2o7l7ygPlGhIJA72AaFDbF9Z05i6gNjQ5y6BcOVEM/EVbGSgQ6d3bGDMN/EAhqA5Gz2UYoyqhXBGRa8VOYjqtMSg+aAMaQLS+VG7CNA3JNdkIIUb7VURk7n4RUTn4suWhHLFXd7lV6CUYdQBFWJL1HI6sCT2wYGr4pALASjQRN4EQSLbKKR7j3TpAhtKI3CoSD3NKMmOURFQaoPXRzCQ3ApzIQz06qgwDg7sdELIWlFy0S+VnbByHPZdGTKmDaNFkNdpHUfdVkyPBvG55QiAXYCZ1ZNlinUHPvA5zUA1clc6Eh0LIpNBYg8wKY5CDdqj1Xly6Q66VV1wEPaaKFCG3MEHXMgNGJe0EmR5ZkuxG7klMUeLosXJ9kTcggwucA/wA8EWVhh5IoNRAhRoOgFuoQNm4g8yFMcO0AWcN+SlD5AU8/nizYTyj3QOZTlk5bEBAkyQJaBP8Aayh45KQeqYbEqZTgxIrYCcZ9yiIt+RUMOYQc3ADUrI0uu2wkW5ig5QDsi1C0yU3IsCVXPCbMQxg/AEioh6a9RXQQ3KlLPnGy2dMcACmougM3AX5iHN3TsKTukYsEVgeHYtBVoSzhPRQdE/MiyJALkMAAJHK6XtAYchJppYdw7DCGSm4HD5zAjLfGZU1PuJe6NzApjUn8DzqocfZCJegmnqQ3C0KrWTDgEKexZOnCoZcSOSFLPtHcpL0hOGHlJhZKdQQQQImfwLDCewvzKCMCwoVJ3dNYLAoZpqXEqYaQf6aYLQjarZVTYkAWoGCQHYQi8CUcTA2S8MfYUqw3yDuSv7GKQgSXmdQ7AqJFkV+gPKqPyTIuHyJQK4o+BWSd2LAyqrP5cJzDudXSYC2ff5aQ5BHklQ6XfusEYKFoGqdSFIKGEOg0OmcGzIqOaxZ1HkGgNa30hAA7PPtmxCoKj4qVTzDAH7shcQgbMgwECaExO5uvRalbAIF0FExdZFCS5B4gbAAQtBtNqI1DIZWRX2NUxZVtmJqhnoFbIsw5z5gurqeqLbDJWQgKEQY0dVDZ/wAsMarAXZXAiSycgSiBPNjQppWd3XU+Bp9TAeZDWLYAZwFVBapRIgXd7qiYcvKLnkESKSLFZ58FXE/DmY5onKx672TBDWQoRwGFXhAc6o2lM48lSR5wh4qfZSzKgvrEMKvZQ9Nd2s11oQ37cFCYGhPcHuLOQTdKVdwQ4QtEIg/Ub1SMbzstvcL610LBkQEoOOIUwgSjHGiSBUdRxdCou71IUihTKTAqVbJXFUDYD163tMUpLYgMCZg2oUjKTL2GpMyRqfuCdQ+B2snAIFcsqw5m+jrTcYJOYUDBgA/ZiBZMIxHSEiQjNQI78ThABonoKhmNFoqY9yNCrOKQ8YLzVZwM+AIHDB5aWlNknvmHygMQGZwGdSfjtEFoPchQYk1CigBtBqZ1CLRYZbVgLKojClE2ucxdDlaRV0obDg8AUAElrGiTooAqsMMkQ98Sz2cqpOPe4eohRx57mZqzWQZhDxBCIzobLVhOYLcgsYpkXZ3RpuqYjk8vUKFelWNYbWXKUjY94P0rqtytDNCS08mqXQvyJzsaOAMqFUN3XMxQqIGzooLi1p43TDUPgRe0iLqgSAv5DoQgwRRGwM05JD4N1GoZhK6hAid75BwFBDqqO5X3DUvsRVURVAS6AQmt3eQnYONSBOdyi0BWpGQES1gEqBDdVtPcqjM05/Nrr6JnwLR4RFSW71U+IAl4YHdZ1C3TnE1hhYwgruCskzUA7gcspFfYnKh8DWq0F7mTHzrwgd3NPHZW8lR2UlCWqK/BB8aK6AKImDeFi25ox5MjhSWUe6LxEy71WVThwrFsHOHKzl9h74CDq9RCLrqAsEGGCPOYyIOaIFoDQkDP9QIoFtrGJuzBkoLHe2meQQxxnB8WsAhfyQ/UAdSrq/QqKEYR9CPJhSJY2tscPgTbBd6ZyXJ9Ap/kIx1eW/Ap0RwonR/AMr9skaFRnRRtphuj2CmseBoQJWrqi0lMpQ30C9XoEXm84Oyj8LEQVUoFsp+bI6CbkwD1DERvE3QFgNkHRpNNU8quyKAPYj3ALZU7BGDdKUYq8GzmguDiMnkOhb0dk0d04Sk6vEkAa2SJ341Q5I3DBJtSEHCneTXKY5CRsjmri3wKDV4WycAnURO2CHhw1y6tEMxKI85lVnoPtVi8i1yawjlq7NwQo9XwZqgi5mSOyCnJMBYIJX3NifwzoyMGDXQi6c/RAzEOh7EK+DyGCz1xo8ADWsBCE83lKsSlhRwvrhCW0ToGs80LnNVRiDANwRpqVI5kn3C0ED4rS0nSY3iLhIUgpKKFAJ0XTFrcJmBsTnGMzKTeEIOffKInBB1FLLRsJQPg6Wg6QTSIz2W7iZEvsUZk8NUR7w0+RYn3Ixe+mCOzgaCZrRfJ6IMVFgZNCBkdxlQIfhXv2E7uTlEbpxfDIDmmA1Rf8Hqi1NHK6DRRoEWGxQNp/RQK4B1oMmULAIfhfJ/dRB4aHIAPqWCTI3OuoIXA9IJqHUUeSX3KqjeyxhLQMiEpt+AKQYFAmiZE/nNKHmjs+QcCqXhFOBGgygZvUmRakFa1BcbGEDBIrUDAICgfcKpdYdBUS26IXJIIe4isad/VLCLhRIbgaGmhcKdi6OBY5Au0SRUG4UikqJTMOpHtXpOOrEFIlCOpiVx/qLq20oIjkNC5aNIVRwDzOTvdBY3ZwGPdHqnIWXAeCUXaKonQasLJ+KzXofmUGwWEsxhrhDqbrJMHtEA7Qweo5I4KRc2ompQIDgJpuA+Zco96wYJd08INm1LAYlKE7o7SzYQaECcwkGOE2aoeIWUXPdSFyPJDGCNu9ybmR8QXNWqj0CITzAj3IGey8tqFwiHcwmVKAp2YmdAtsrmIBcSQaxJLgT7gYHsU1T3gDkXF4fQjXRBr+GTuRFlQQKAC2PyU5/oEhSGjVMSKhReMgBWiIN3usJ7wIQkFQPzqGhCd/oyI6usg74I1Ai06EzaiVFCb7FDJXLKFyiQBB1SCug+QlRgPYv8AAiPeZJLONpYgPFDz4RSgV/yCrzhbz4cBeqTp++hbQN38ckXyvEJVBE3LgJxfWj8g5RBqAaBVSM1Q2XaqYjv3TMosKQHqOqbcrqLnZahYbmAjZoxABklVRdwvN3mrIrVOTqj1xbw9zCbQhTY0MMKFmqoeOfOUNyTi8i3nSqETWTQA4NiUDkSRi5vBQWOroANBkOFQ2HnUW67KuDq/mR4feTUBY2dORolrs3jM4Vxp5kAJdAtwAmxQmSpb1QGk+Wf4EQFXEo6sDwgaQv0xRdP4Cx60gFL7Fr80z0EvCiucB2FHgFM2kHJSMj7IjsBQ6ME8iPZaoVGzd1vLhrmhIYIP2AMGU91Ku2ItEI0KTINSCFBTcZ3MjCYxxjTLrwmq14Bb7JJCzBlmdyeDmPwZinjBgTndMPJgVqMCMC56pxESd/AIeZiZRODcNCh9vKayqMyAVyHqix26sb3KH7gxD+1yJk6AtDsR2H3ThodVahUhF5UVUqT4dzQJyPgp5YUIl4Vo7BSSEG0L1Gosi1qM7vlQn4nIwGAGw6cXPVBYsPVe7qWAgEjAyGmBuUgyvZsAcEjUJ+YEQL2a0xCzx1u5LkDZVs6OuCyBsVqRQPcMFBQe8z6UL/lnB0EbcZ8uAPQJdHO8BtU6hRWOaka8gZDgYmhNXGXEnUXsCc5nMhcSYhAABJqU0uVcjYYZbKFoWkzEIudQdnTIyhoOooqlhO6N3vM8jhJV/copwyR2J31hUC6oXWjOnGiYJxNnbktKC7X+leQ9JtW4cJ5516bVLp9B4Cc0n4F6PLeYQDDbjEIeGkYgQETzl7UrfIqpCQSWg6HcvHWBZYIcbdzoBqIC4FOMHC8A9yBuKGy3CHTbPx0CEaiGIHEnMhRrsQHUHVQ1IfE+lAoZBuL55/RSq830agsjgK81iuRGeUqKUvFUJkHJD4YQbIy9C9n3hC6cBEEyIPFlaJ+IA8AZErAjgsTxDZWqVHzDBVQHTyfIIGnncz7VOd+HGO4pNb7gHQvdSTfLZF7mpOpXKhCOFQEpWRkT1QNkIJFRI3+RRJskjYM6JoxZtJfqAEU+T8qO5zcOY6a6bBnJ/E+KVSHGuyAGzUNVDWWCsKZBQRnBhqh7dTsVc266KIfWgwGOYo+RvLbJ5IczQPJMHKASb1tBFo0iCKcKfTgJ2G44xyqyGmKfpgc/VQxBedS6UQqhvskDQtJJJQ5kwQjQUOaK5ATu2rQYQuVABNWAApxrADKEjcCddSA+IQxTOfIiphhGom27GCB/ogscBkBQ0A3CaUMTzawwi2hXBJDBPFZAk5nog7/G0ERt4AwYBuRKcUaCprKhUqAkGAPiW3AG6AbkzlZc4c30h7UreXREjfE2R2KqhIOyByrHC1t7HJSNuE6CiqFjJgC5LcoGqYEXohsBlyk5SfdPLA/AkoahII2GYwd8lydBHqNsnYynMLnDwFScsaQpbJDuRsFBvSYABWvPQAQFkrjYAS+QQ5ahbo5WjqATmijgegkJbUK5qqJzEvOgNAljkrCSqoM8BY7mfyUIR/4kBBnOfckIR3BIBbRtaEzWw95WLUClqc3ltggdfiUNJoe0E9ysC+q7KUkkKrI89vEm2MeYIOgtqGUqxhORtmNxQJxUrGSgZPZoIGJ9HI/A7LTmKCka3vFABHS6oACWtYI1LjEh7CyDsqQphD1HwGCcE64ih6PnVPJQhtT+jCEggbX+xNiSyH4CbI44dC8jOiHA12uIZzTQIArVUS1ZVSmid+5FXM7hPAkFaW6Zrr3WnH7VkI7meZoLlhQX0hSKuqEZhwxlExInc/I9RsyKpB/YnoCdSEg0D8mSWREM4s1IC5GgCsVuA7J1iPG+gXV4AQj5hdklzXIrUXP2Ki7RTETHdRLZjLu3aOkKVGr7C4gb6kaAxKtoC8FHoJMUk64hQgY87pAidaaeYAisELk8h2CiB6De1W2IKTe7aKo402f7SnieWAGiy8QGZ1E/wTqFLoZcTjcE9wOJpRZB1B2dc01gi+50H96UG26lOVEneq0qDIDzuoZQkGvii7HMprfxXymdggCqblBnohZDHzurp+KAd04cpgUd8i8vxFBBxf4ACiRT2RgYBEhP1FgsFUxV5pYAEcYsMqApJWdQFkCAgInB1XaNVtLq0aR3fqTPAGM5EVP2CcOq8sg+sMLdnipSjHdpM8GbpUn6UfXYKl0U5AlBsKYj+vW6XTYQuNADEHr1glmNUJVHmBdAUlSiGDoA7YIjkHMJuByPcGQ24iJ5GSKzHBVHsQmpeaULw1RpNWD89VX+3hgGB6FCYemXg3UYG8cZZ5AryTrFz8QisuCIVal0ChgdlRiK+HA3URieGonCTwrLQCiWIJYyvyCjHd0TUSyAl7SI7A9ugQMasOboxH1I/A6M2DVqnyWIdTwZRsza2u42iIDaC09QCMoEEmZpVGCAxTJOuDYUVkiI5n7p74umiJFcG/ITpeDRshRiX2Nq6FXdB/WLvVXVcWZaoDoDAjbkDGDpJ0qFBsEoZExE7xshRsF++YdDkd0jxX6dfkD7ckFEsT7IcAcgQ2yXRpn750JgLYoC1XNI4t+xRHWdaUNal2Q0kzr8uBbyrA5vyKFZCoYhsPyRHPOgWgEKMIpdgiuC8xOyn4AHZEzqanN0R7fkFBJOociOlUTwdxGYO/yEJqY+sQcUiVVoD7M+FYL2rLOE2w/CBhR9KvfhjYK57E1Tm9FjCq7J1G0CFBsnYUKPC0ALttRclLVMCfIhQM2spQyTTcDqISqqe/YhfKI3EOUFtBYIV6IpPAjYaqYB6zINFgX9RuB8JVJh3EAE25cKnexHzIh0qgbUVjYCtk2/oOrBaVQFQiRa5DUyj4znILJhHgt0CEBPy9lQA50NJNajUfskyT/In4CGUCAY+siDV3g0q5UC+VjhEH0WCFDNbwOgxK/VwuntqnLtka0bzkmq6lRFp7+rZtzJhQfMFK8iGODGc6rq9FcIbRXsEBMWEAomHUhZIGEMDbka88sfsyAbmFFFmRR3H4J9Ae4hDm1iDoYhg2Kqx42AISfg51rnlBU64Yf0KTQ4+QCBS0EvSn8IbIgnwKXjwW8CgYFYJmyydUuRLah2N07m1gW64IA9AeM1BGDh5DkdXVa8uQynTKOhOhCjDIPNlswlnCAgZzL6gsMpWKlogBDWwKcEdBVK0EnmluQUjoMX8zHQV3VTMWD4XT7qiNfZR7eYJ1Mjm1Upwd80aQhQTHnq3cgBUTV4DNDxPUuXQVHUsgYpEluxSTdSDuRNhUK/4RlRAH7Qqmm25qEkCcfJoqELl6QiYYxYfdtQsIG8Tt02IlO1g+yEHvQgRKv29UH5BA83oiXBM+lE825p/q554NVnhFPYmWndNGiIsqxLvwJE30UokEUSrWgKyJyPB7ijjLxMBlBlMRMldDUafyrYydLDkNztw0mbDOjCEcVwEKo7FeSArg5B3J6LWkNIEAOKlGYMyhCRzv8ABGaBBkjFHmaEEDJNZZzD0RMNzTm80ZN3YiwDJHIRCmyhJKchVn7nAx4Cu7SOSSzZCmqR/GgeqKQM4C+wACG2kMt56iHe3ALFEqvD7DQGSP8AEFFhBXrRxwGirIwRodlX9qHXR7uzKiSfCfnT0LmnQrt4tcSQ0ml0G44+NJv51o1+IbyDIMaZALQtWqpF3K/KiCxo/PpSOQuroPYnIFEYGZKCZ0BohA2oqzWBkUQEyaoVmhVUsP4MfpFdpQbC163WUnRJvr6FbI7gchtuVMDZJtrv2WG9QursN0+k1XYfCU8vWTcNy9kWvsDkuzuoYmqkqfaixtbdAD/S820dwZaaDeWBYO6g60Kkq+9TQ9vsCfmKATsVSXik2OQlCx+FICAm6NmLzVzQneeaQywhAqSFCAOXOAHN7guaCTIUKdqEDL2FOdUQbB+LJK1XvKF2NUZBVztLygP0ipBrp2YAQA10UULVFgaBPTXYU91BQh0EUNzbWgQMnMWhGJiG90GicxPra+vQnWlhbfQI7I1+8ORBDKK+fuBkcFcBJ4AJlYGFXqe0s4WDmtQHg5qeGqPRx5OPNAnaEJY9lA6phJsfmi5zTwmombU3KcI+xXv9/icLk9D7VUJMWbOizqEByBQ8A65oEzkBR9b/AHbqNCUZxA9SvFHvpS6Cy4ZkcQISMt5dkjOkNg2kEDUvQgZK3j1gmwtS4Ud2FVFogrA6iic588iHYM5V/sPNFaGyWVUYOdkEVUkj0JIhvJzAxufUi0DtdVdd3UgbYv6Z9uh1sGkYsBkrULc60yh7KGbdohZFSPauZDcIOq1SNcnIhQoL8oDllMw9RRWE2ZK4KeBfyBGZUg5M6as2V1t8MYCP5bKAkoZYIxf09RDrFNUZs0tBqosguuztTqIhHyBBda1Qj1n9QJXQIBBv1CR1wZHJXI9kk4I4U0jDZEToJn8GGJUBB+gSVWQAo/AT6jxG6HoDVWXYhyVkq1dR7gWBsQF+gCqQh5A3pUZI9RAIFVhWhtKgjdUsuHsYwyuI+lCtw6I+8rLNozsIhlkaL7ApzCN4lTqzjC4WA2KTV4zoh3zSLTIkX9wOmaOxRUUk6uxBVP0AU8iRaqDIEAjmyGgiNv8At0hkgXtZu3E0v0FUPpUYTOTvUgIb+ScmKY3Anyx4Ge5IYdKCRcNYCyeSHFOZcInzEb4AaqnbhiklQhdcuQWYcfd/sUgIP4IQEG4iZtXD7XD0fpdJqEIK5J8kiVqRPnLgACSYASYAk9kasJ7A8Ih4yt12CfqHayLam3AYJyAz/U7k3onD0Z5QL7AWVcz7prgOi5CmanRjXAAfEdikhcgdklOlilTO9t3IsiUAJD0B3GFsQDkTuhOQywSR6u6lMPMNRiYwhk4g95D2L2SN4qs5lO/gMB0J39MhHzAvuqBQAqrdBDZdQJURegZkc9ik6iZCnKZl2LUqzmEx5wYBUlgsXTBNTJhQU1lv7BUmESdy5ExNM4SGpO5FvGg/+DgIm2eqtLbnpUcI83IC7dRZspuu3KwINKJmOoBPnwTSUhG/TXQZxojxSPc3E0R/sPgNQqOuCzatLOr/AMI/uSqRl6Mj3Q5XPZCyLtCaoHJsFEM10gup6lp9RBYfJYqIgq/FdP1FHOgr8qQSMersLGWhckXzBkRXFUMYw8UrdYrLsMhYjXI7uiNSrsLjY8FHxvdF1mTPDmAg1Xogc+od86QV0sdgnnAOZThNQYZIKA6bC5keoyWguB7Su7kyg9Bsy5ODZ+eBYrUFgBgPEiwz+77mmbV7iTvaVeWT/cC/CIw3KsMFWqncKs9EpMEmzUSjuDlHItq/hopOcn6LE4fViyu+4MVpAOtn7NI5VFSwY4uh1JtSxuRuSUxRnyS6YCPIZqK/gnRZu6eQB/cjvJsWC1gnRdJXZUCc8BoBYAWIKgMu+9SGESUpSnfAAixzalBUIts7ZDsQELfxCG3CS2T6BbsqlOycqS8lBuqB5w6ujqAdhMTnhLOL8goOElYxWIlOqYiM06rxdX7B6yZlmiFhhc5tdh1QZDGvoCwcn1QaGPd7SpIKaFi4yUqNVkg7hURUJxlAjsyibGP4guX0Rlzs+1/gQngQAA4xvUvzZkZhmWBoUU+a7jZQ27p2iYMH9BUkjTRhnqaugxNMaIiyZQADJlDUalh3aKcvqh7aVdhIjBode6QBPwMncoCagxXgn7RQIl8hZUrSAYIQBNgxIGRl4ZIzPTFwgw2V4xV5EIYROBdrp2pZFmwWGebnZi9GFsRdRYwm053PVMlti0O4gnEuAAYVG6Inaio87oyGavdDOyeyEGm0ctCqLyDsQbQiQlj+AhNRwHdUlDRtDwUQrdZYVZoIgnlFu5OcpMS9Tl26FiwTG5n4RjMeT9Bl+CBoQwLQgY7oBu7VDBOtfKSiPHKBLsmiEz7oEipG6WhDL3QgZGkQVYbVhQgy48mU3K/ov1PdWreIKmv+FVr1vn2VFPEpeI2FBYq8jhrHZ5WXX5bdkkMUYaAxrUSaLugr15SRGuIMrcF0csKABBOP1FS8cY44ZAR3GE4EOWVTXQUxcMQ0PchvKl/TG4FRCyE4jagUVgtzmdCpoFAM9wjkp+l6TzYw76pogL68pe6Pc4c5CJG6KyMEcUxoDYqdXmlAv//aAAgBAhEDPxClifCjDGJ038msN/8AhzSK3rfBHkJ8VCIeKCegvMLw+RrxbeXU+MhCw5eQeF4njWwhC2FsLYQhbCELY4w3/wCVGC5n/wAh+bjzOfiL/wAxH/Dv4nNOTk5Qt8MHCH3jC9pHuHsyM7Co9n2Ht7D3D3HI5HI5HI4+Th4LY+a5hnI+n8ORzHuJmEpWxxxhHt7qSDZaaNM5HvgY9zmvJyc05Y9xPwG8lPQ6RlCRbGZf0WCKXltFvGnHVHfU+/KhuJKOb3JfohHmBWdXkVovwRmWARdX3H4gaWLUbGhTk7jsJ3EtO5sdzQD2F3vJKOpQYBQMkG1IMqsY6MdHiZ2X7dixrY8aJaj4Gg+m+WEFqqbg6gIMChk2PyPoF+tiQFgrYlYW2OT0L+Abc25CSqGXIa9AksRbDvipST2PUsLH9/4xFQQhbCQiwhM4FgSETNnlQh73pYzprSCQF8xLf9GYTmzvSVNy2ATqYgMeBUa5McUgaOKKiFtTivAhE9Uy/Q/pL4xG8l6/pHugZNqJkhQOhg7PF7jGPxp+uxMf6SHeawylIqt9T3fgTO2SohPVY+47quzrOAYxjHQx4mMZq7gRiOUR21vcvYRHyPu/Rqvrofc/At3clPiuK+zAEJtqHQMI8tr6PQ4ptohNXCOFDdNwQVAgtneothDg4Mplc9AD2PhVtPo9STrU6jE0NjNjNlDGMYxj2HgEqwfcKgQgQtxBBUCKzDehpH3dBZ9ZKmdLD3OcDaGwY6EaC2ODg4FsLYWwnoLallLQcvRE98AVJvmRQ4eVmRmhPIvc0l+BzdLJ5biSWPJFhmXMxFtLLjXEsZHT2j3h+3BBMkZmSRgkSP6xj3H9Y/BvSyiShpm8yQnUdTqeQS2b/WTldw2NlbNDJKUta1zMd128j0ATy+RRaoUsWO+NGn+m8Nu51MSVI2NOGdzA4eYtZ9dh26tcVlE2hdbl2pZvglS1Xeg4lnL9RTKyuYmZK+SP6WN4S5Bu/iSKbl2O6IS9x6XCthkv8lPZo7BYzPp3ovt4p+uZGmtmAzWMbdxYZz4ew9hbW65GRXT9BzSyjCmzEsRnm+B3MHsQslbEyhzMyNeuOXlFa5cYsMaKbrJR+SxTZZll6kndwSzLmGHWgCHUjkqe7WXBCOjIvOeMYiERJQ07NCc6ksizaDdtiAV7jISySNClnexKs1v1Gmi+lGZeaJuw9B2wyQmoMzqlTI7Fj6Gg7/4Vj9nFF+Cw+/Vg89euV+ogkjmltX76H1B9nAE/2KJMLyQdwZlb3CzrMLO0Zn6otbbQSSunUsouS+56yxlcRq5+wmcCwveifvyH0tjsG49o5qsJmyaGdASC7M3ft/RE4svF0iAT60Zm1F79sBBC2KloG5sRNuzH0dywbF3NJrixBlYkgvTYHz+RNl6mZs962O9E/bmj7WioL9H50XlB3BAtvdC291+xbe6/YvrX7O+dUZudhqp2PgUEWN6g/NFzu1HCH2eDtUaeYpshWMT4FJe7ckDgQYIu0nWodN1VS9L5a0ZStWdOdN/rV3ewhDb1OH0p3ZUvQy9KbIY/sP6j+g/uP7hP2D/uFD+40ID1CaeoBwLRoJk7FGjL0RJnk10FVJvs6GfeXZmp8IhYhCEsO+YlQlSxcgZKzkWQkNnI0LYUOyoJ8T4MyTYNg2DYobDYbDYbDYbDYbCalW1LBDtyTjbAIBEdija4+j0FszyhuNIW1CIm8S6F0XNxLVCSdDJFizLkp+pm0pn+VLqxPjyUvV7Dv70cI+owhiDPoyY1LGch6OS4LazQhV7WgS3MOc9VQWZct0EECGR66l04T6XftSl6CNCfItoZqfdQTQcklM5/XWlJn2inYMx9Z+wkk5uiZT1LOwXihz2Yx7wayEhGofChmXLbIIhX9xKya31GELKQn2b6upB4pnjjxFDNu2SjN/qkJwpe29CTXSNaeS3oQn0G0xbR8ET1obgZ7fUaWgLlNxnJetRSSuSJDQNppF0i5ET7H0fqyEuKZmZnjS69e1zdPBfRffX9CoXQm5o0JnPIseXYLMyR3LaqgLD7Mh9INA2Znu6lyF0UFPoNBGQP0/GIM8Uxtr09bJc9iyJIJ7Zrweu2KEvXI0QlSRTE6mQ3FFWFuhlm1bEMErsCcRqELccPRVGZchM9iXZWIEBBJFCErbUHzqWpbDKBZr/fv7Ub68Lohtd0Xwi58UmzDf1LCw2sjUElkeZm20IfQNTKSbh2ji5FqXJD2YhWk3DyWT0M7sviy2CWrSsAfRu6OhvV2RlThlhs9cd6FZ9LDtWgfAhUC6kZELFlUxNNMUqLpMBSuzefGK1ejjN7Frvgu9H0tq2+bboFzI+S1+JGe9FkR4d1Q/Ykhh19TOBfA1B8D8guAMcG9yVVJbGddBwYTdimyjwIOgLH1tq6pwbuSBLxt/TodiqIHNGFYQmG24zRgEnPRZIhhPoOELtjcFnNJLYbV7n8YIpOLKl8WH0ckriohZhs0Iog2YJtuJXM5SLLSKX8MCWbFuLfFlj+5sdwWksyIWF471vW+M3GR8wRJud6zLyMu9Vd9D9iV1gjB0BUXN0cUY6MY8M4ri1L4EhurT+SBKoZgXRpmo4RIvrxtgmsjooYa8AJuwhGK6t6JFLvrmf6fw3froQcOubvxTgnQ/Ke5i3pHlpLYc6Mxl6Yv6GSzuflihajsWqyLEeGhCF47SzY5Ea27ByDTwEn8m/oZuL+AlEihpSyxBMKy6CC5NLXRfkY2m024AmwAEoB7oT+Dd7UlkWZsNhsOGLmZkiWYrlMjSHF/Q2Z/ufLPyZd4GS+oY1qYgfMdQv1f8R7n+4dOPEA+v5/hcbOFd3iBspuXF4zoJbDaBdBsCZFsm0bVBs5t0x/oL+mABWrKnAthbC2w5mVmS234EgabNIT3oifmB+nNO3zQOI0FHN3EN9XCUPGWBCeXhTlsSkTTk5OTk5ORUNoaA+iKNw60RmCfjQAOkLVK+Eqkx3k3zeQ2o3qW5R3aO6b5vm+b5vG+b5vm+b/AIP6q+1KG8MffvBsX05Nq7Db7Db7DZ74ckdhTbzBI/THLwG6yx01/Dy8E+BYWRtB3JyXjYYqXr8PID3o2CYB7eAzoiA9VZCHmtcJYlq/DxoSN4CIvAPeSKRc/osexcjBDF65+LfyQsYDdmgzV6mrGz8gs3x/PJL4YJkWasWO7XbBbyK7yLKVdFM40eRW8i5uKLjWbCveg2g7dECPAz89fAdlPUkSeTkWcWQntMF8CUm4QheaVhDCoQiyY74p8OfCdjwIVfacgTyw5k+bWxt6zTf9UJ6j6dMNfzdsBhQonOKubelPv9OvKAd3giCeta2BbOxw7H+B/hQf4H+B/hQf4eIEU0OgcBwuxwqArK7QbMB9VCANf199q5l3ghN6/hT1wQqT6vH+R7BP1aEEMTJTg+BNTRrYsy9bEabY1oX8d2nZRH1aFsDgxOJP6KggsXr2eHn4zs4R7UHeH1xjb44SXfwc/H71PthuaRSEdofDOa86qZCpet+mZMjZuBTbDHgT4PzPv1Lda/ODNEcHbueuLvge4gTAbmtPo0pCVZC3PaENazMJcnO/3oO/BruaQH3PZT6DyG+8Du7eGEAj1L8m9GwstH8ofgfdiPV9RKXSk+tuw2oY7XSuZqy6XLxtRsijXjo6BHQGgD6sY9FAGl+00/uwcI8BguvL8jGf5UP0OgfBLG76dMQIHsoWdYnZb1pniDy7A+n8oB8KiFb6HR9dyESbbj96HOvgARveR6/yGPyNOR7A+nc3l3SwD5wACAfAegBBJFMvU6WrOw+kcx9HUAr0BXwBEzGBoTtFQ+uoE1H84IEN6/2ll9+2fW5rekOgxQAxP7fSqGtL9LknND2qQ5UGxZIytyR9uoQRhBmAqmL6G5n960Ntxsqf5OyPptQXuF8kgfgol/Q/cfmgndQGSzA/b8BNIJEKkLswG8tJIlUTg6qL8Cn0kagBegKH4iOlCi9HWS+nUh1fvgifv4JoEHwh9dCH5h3Pn+ogW6lCv0B7N6jJAev7zNFykez6ypbGQ5LfphYkMOUdQDuMKsNDkcaE4g9mT8UeOVJuWcCDkaN7qfapARQHsYQa6DWmlYl0jA3lrS6h90rB9fv6Pv8A3R7oe9gMSfkh/RRaUAamB8OVaP4BWPWx0vv14QsaFTTEtSVD6fygHcwkhC0H0PWhahD7H+j6zTADkNFAZPWgGg0BZkvHBYlvF7g6J9GAQe1Q+n7IvUHIdiUn0cUI6n80vf5JiIVP/9oACAEDEQM/EJ8NeJPk3WMN6sfhR5mP+PHj2/8ALxjSEIQhCEIQhCotxbiohCELcW4hC3FTk5ORbi3FuIW4heBfycaHBONj8jfyTJxR5O1LvxmW87al340kUy87d+Pvn/zr+fvi4o9hj2HsxkUU458xfE0SNvsbZt9jbNsWhvwJaFb4kFsLY2Gw2GwWxsFsLYWwthbGwWwtiMdyKQW8A7rw2pPlSk+lvhtS9NKnrsK52F75B04QOE2uhukXLdsLNS3gLwXn0EntivSKRdFyH+JDgbK2qMbOxcsaks0pbyKVzbQnYUZ4L4SOTLBCKWrdlI1cosIbEYxjGMYx4GMcyRcYiI5L+hoIu3QuDuxC+A5Ng2aVhUmnJyc1e5zSKTrXnGXMiH1UnB9RakyFsSdQ8HtnE6ZeTzHV1Q11RD98N6Wo6iatnsClQParZW1LUQhCEKhCFRCFQjIIO53r4Jqg7xA3eocnI1hCKByckaiVJ6G43UInBoYnU5IZjEks6fSPpHLsP+h7B7B7B7B7D/A93ahj3Huco3Csk9G2BdQqFuLcW4txbi3FuLcW4txbioQtxV9MeAHsPYYx7GwYxjOMAaS+p9G+BYcj3HuPc3VN1G43G83G4TU3G43G43G7C67iTkckN1UURbXIRNLeov6r4wWg08sShZkj+AWzsL+Av4Ctli9J8C+JNX0OTQU3L4J0sTGiwU+kfOt0K4XhzYetfaqJhKBRaneuRNLYLlzMknIsTkTBrGRL4UypajbWsOeCTsntYN161txLAZlkzI9qplRB1rYCoJ21wLjWeQrNxL6DeQmkbHFh3eWlMqLUgkiD2HtV5Fjn4F3T/Cjh4Lo+Iwynv8AchES9C1Vy4l2zWRNxokQ70RXIsWIZNJSJRwdhHsr73w8QMr+pfpRel/Wjt4iUZCequboa00QPOpFnGZH5LSZx0j1plSBcqWJEQj05Eu+FNi5HX/B7C3UPdT5dzul/QNsafyW9hCEdAipGiBIzHKRqEpM2De1LnmNGVF6ZidsJWpNUFuWEsjNxB8VXc7hd9EW6me5HfED5L247V7KnabRdC4J6Ay5ePcn8k0ONZO+B1QroTr1CNFyC42by9MsbhDNMyKZFiSGPiWUXFsuwqGhH0ZUQSxl9MjYX2zNotizNgaJGyp9M/wBBs0jUUnL+Yvehqd5iKT9DVWD2ydk2cG5cXLck3sdEo3HdZllhj3MqWUzE3KMsEdGbxNKR7lOdGpuSsN43jeN43MNVvG8b1YhYuZkZTkHfNHYzUNkCZmbkuLkXFIeUkpMHrElLuJ3sTGlLliC1l6kxKFQspe0zrfx1cxJJnFgNGLIdV6WDMuJDiUrltQd4Yil0WoaXdUQE8KXpVhyRS/jpGhAjoLVblyQ5NZJJQxjS0uRLT6oTdEl0WoyjsaLMaXdL349r/glsEF/IRSxYyDEly5KgWHo6DhtM5EzFozL2vNxPpvS6LF4mmtdCXe8kOFbqZknSO5frgyLrEpP0FB+rwYF6m1IJoeVL0lbodteohHIh2wzuRIomT4LliWW4rGuRkvuSvcJ3yIXFlheay5pQa0ZsPNiUt0XTBrKspmR1pcvRg1PBMenYjAxM9hGka0uqiNMU0OBqxC2w11TKv+Cus4JPQrl6GRhue+O4uhUFlMxmSfjgtuQWOw6V6p7G2gzPdLVvTKkvgzjzXp7qZ831GRg33zPgeIink6SuMzLQSGQuWouP4RJ2NDpdFqXQ0NMV6XQkpaNluT0OxWTI/I2LHGbLjerM/KG68eDBrf8AJcifg/Qb+hDMRwrDWSquWpPhQMbp2K73NlA2T4sv1Z8kVpTEn6ll+pGQnNc8UYsq9irwOi8Kxt+BZ9RetVgWTURsJ+PlgE1yEbhyHtGCVWcOTpRf498eVfYqnmooyybXYW1Ei1m38Gw2DaIyIzJfBNWhIoI5xcHBxhvisZVt0K2dGxHq33EJFw3nNJKUaE3rNFJuEsgtyncbzeb/ACL/ANjKvZVmsmjnMgnWnD7l6mYb4pHoMeFjIHgY8eZYypahSWxhKUaDwl5WxN2Z2F1LT0QRfII5siQ9YoHQx0li7LZFjuhdTczd4EEFvoC/sP8AdHMfX9Fi1cjmnaKm43s54rFk2Jq6NPoQF/eT+uDX6gTCOgghMSbDdA/4CZKIuVN5/wBHzV3FtDWEogar53oMHcNw3B82Nw3jezcMkbvaT7Q+0PtDeuwbZj3HuO2YznFnZEUjEmE9Vmfpa/Inzgw2Pk/wcmQlL2azomGomIQvKxiMLTDxV0bhdV2/o83qg3ZA+Ow9zcOQ010/p/h/Rf4/p9L+n0v6crs/2f4/02+xt9j/ACpr4KNpHpYiNH/kf+B/5H/k+1htZnmxsiaTbNs2zZNs2zbNk2TZNg2DZNk2TZNk2RdJsm2bZtm2bB+VBmwWHilqztG1j4VefBeB05Iw81L9M/Al1jHbzUoIR4FnggY8Fyyrl5B7Y0rs18CzpGBeMORnTLwdsMxBYwvfwLmm+GHS2DIzpliyJxx8jmT0eFdYMvFlPJpbxzS5csv+CsR4S5L8jfyV2GSMFi/hx5hakOnh3o2bDYOpsNlDGMexHkdSYGZBG2S758C1Mqz4UUjyKCXX0LX7oXKlO/QaxWw28W3j+xOWCyNHY1IzaYS2GPNahseoSqstEUmseHzTk5Zy+5y+5yxci57i5I8Jmxah1pJZcET0up1JE47rDL4obztesE0heQ95Z0wRAh+kmmCMEWpfDCxWHq58j73yX9MEkRt1HeiVSVivhm3mb9R7KRg6q/cikofpScOZakGvmLl+o9pGEmg4FnM/6Oi63grYIGlZSW8WPC7ixEV5qthtJtVhVm9JnBxke168Yci/gxQsUIzExLU+8ENgRAsULHP56Fj2H6PS/wAE+58H4RKC/g3fbl2W0E2nqfokR94od1Yw3rLwxTPscZwep73Fj4+TjY/R9cF/c9AnpoPjPHd11Olti3rF9anxJ+HfAVPse+HikEvwsj9ljOnwPmneN+wjLSzH7fo+Fke1GPgVC4ngPdg9/kQtLHsfyqw3LUgWSv8ADNOx+j5PcfNHuYz2HyPY6Pr0o+NhHwfgadUfgy/pHYsLej7mXK9y3U1+yffkn08CFSETfAVipMjIP2RHcg9lXI+CPrMyPZA4XQ+C5lyP3EJcj2evJHtRn1p9j9/uqO57C8G5Yti0LOzwxOBex8Ct3o+sj2UyParj6j2Ue5fxpIwwa0ikwa8meL2GRGF/0Z+RQ5LeuGfCyLT4HAiT2xZnxQj1wZ9KamXD+TZmkzuc7+PdEIvJfBl40YrUn0HT/9k=") !important;
                background-size: cover !important;
                background-position: center !important;
                background-repeat: no-repeat !important;
                min-height: 100vh;
            }
            [data-testid="stAppViewContainer"]::before {
                content: "" !important;
                position: fixed !important;
                inset: 0 !important;
                background: linear-gradient(160deg, rgba(30,92,53,0.6) 0%, rgba(20,60,35,0.65) 100%) !important;
                z-index: 0 !important;
                pointer-events: none !important;
            }
            [data-testid="stMainViewContainer"] { background: transparent !important; }
            .main .block-container { padding-top: 0.5rem !important; }
            div[data-testid="stForm"] {
                background: rgba(255,255,255,0.08) !important;
                border: 1px solid rgba(255,255,255,0.18) !important;
                border-radius: 24px !important;
                padding: 2rem 1.8rem !important;
                box-shadow: 0 20px 60px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.15) !important;
                backdrop-filter: blur(20px) !important;
            }
            div[data-testid="stForm"] label {
                color: rgba(255,255,255,0.9) !important;
                font-weight: 600 !important;
                font-family: 'Inter', sans-serif !important;
            }
            div[data-testid="stForm"] input {
                background: rgba(255,255,255,0.12) !important;
                border: 1px solid rgba(255,255,255,0.25) !important;
                color: #ffffff !important;
                border-radius: 12px !important;
            }
            div[data-testid="stForm"] input::placeholder { color: rgba(255,255,255,0.45) !important; }
            div[data-testid="stForm"] input:focus {
                border-color: rgba(255,255,255,0.6) !important;
                box-shadow: 0 0 0 3px rgba(255,255,255,0.15) !important;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
                background: rgba(255,255,255,0.22) !important;
                color: #fff !important;
                border: 1px solid rgba(255,255,255,0.35) !important;
                border-radius: 14px !important;
                font-size: 1rem !important;
                font-weight: 700 !important;
                padding: 14px !important;
                box-shadow: 0 4px 16px rgba(0,0,0,0.2) !important;
                transition: all 0.3s ease !important;
                backdrop-filter: blur(8px) !important;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
                background: rgba(255,255,255,0.32) !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 24px rgba(0,0,0,0.3) !important;
            }
            </style>
        """, unsafe_allow_html=True)

        st.markdown("<br><br><br>", unsafe_allow_html=True)
        _, col_center, _ = st.columns([1, 1.2, 1])

        with col_center:
            photo_b64 = db.get_preference('profile_photo_b64')
            photo_mime = db.get_preference('profile_photo_mime', 'image/jpeg')

            if photo_b64:
                avatar_html = (
                    f"<img src='data:{photo_mime};base64,{photo_b64}' "
                    f"style='width:100%;height:100%;object-fit:cover;border-radius:50%;'/>"
                )
            else:
                avatar_html = "<span style='font-size:3rem;line-height:80px;'>🩺</span>"

            attempts = st.session_state['login_attempts']

            st.markdown(f"""
                <div style="text-align:center;margin-bottom:1.8rem;">
                    <div style="
                        width: 80px; height: 80px;
                        background: linear-gradient(135deg, rgba(255,255,255,0.15), rgba(255,255,255,0.05));
                        border: 1px solid rgba(255,255,255,0.25);
                        border-radius: 24px;
                        display: flex; align-items: center; justify-content: center;
                        margin: 0 auto 1.2rem auto;
                        box-shadow: 0 12px 32px rgba(0,0,0,0.2);
                        backdrop-filter: blur(12px);
                        overflow: hidden;
                    ">{avatar_html}</div>
                    <h1 style="font-size:2.2rem;font-weight:800;margin-bottom:0;letter-spacing:-1px;
                               color:#fff;font-family:'Inter',sans-serif;">Gestão Clínica</h1>
                    <p style="color:rgba(255,255,255,0.6);font-size:0.85rem;font-weight:600;
                              letter-spacing:1.5px;text-transform:uppercase;
                              font-family:'Inter',sans-serif;margin-top:4px;">Portal Administrativo</p>
                </div>
            """, unsafe_allow_html=True)

            st.markdown(f"<div style='color:rgba(255,255,255,0.85);font-weight:600;margin-bottom:0.8rem;font-family:Inter,sans-serif;'>Acesse sua conta</div>", unsafe_allow_html=True)

            with st.form('auth_form', clear_on_submit=False):
                user = st.text_input('👤 Usuário', placeholder='Digite seu usuário...')
                pwd  = st.text_input('🔑 Senha', type='password', placeholder='Digite sua senha...')
                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button('Entrar Seguramente ➔', type='primary', use_container_width=True)

                if submitted:
                    admin_user = (db.APP_ADMIN_USER or "").strip()
                    admin_pass = (db.APP_ADMIN_PASS or "").strip()

                    if not admin_user or not admin_pass:
                        st.error("Credenciais não configuradas no sistema.")
                    elif user == admin_user and pwd == admin_pass:
                        st.session_state['user_authenticated'] = True
                        st.session_state['user_name'] = user
                        st.rerun()
                    else:
                        st.session_state['login_attempts'] += 1
                        if st.session_state['login_attempts'] >= 5:
                            st.session_state['lockout_time'] = datetime.now()
                        st.error('Credenciais inválidas.')

            st.caption(f"🔒 Acesso seguro  •  Tentativas: {attempts}/5")

            st.markdown(
                """
                <div style="text-align:center;margin-top:1.6rem;">
                    <div style="width:44px;height:44px;margin:0 auto 8px auto;
                                background:linear-gradient(135deg,#4DA768,#2ecc71);
                                border-radius:14px;display:flex;align-items:center;justify-content:center;
                                box-shadow:0 8px 20px rgba(0,0,0,0.25);">
                        <span style="font-size:1.4rem;">🩺</span>
                    </div>
                    <p style="color:rgba(255,255,255,0.45);font-size:0.72rem;margin:0;
                              font-family:'Inter',sans-serif;letter-spacing:0.5px;">
                        MVP de Psicologia • Portal Administrativo v1.0</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

class ClinicalManagementApp:
    def __init__(self):
        pass
    def run(self):
        # Inicialização do DB e temas (não bloquear a UI se o banco estiver offline)
        db_ok = False
        try:
            db_ok = DatabaseManager.initialize_database()
        except Exception:
            db_ok = False
        if not db_ok and st.session_state.get('user_authenticated', False):
            st.warning("Banco de dados indisponível no momento. Você ainda pode fazer login e acessar Configurações; demais páginas exigem conexão.")
        # Autenticação: por padrão, EXIGE login. Para liberar sem login, defina APP_REQUIRE_AUTH=false nos Secrets.
        require_auth = db.APP_REQUIRE_AUTH
        if not require_auth:
            # Considera usuário autenticado automaticamente
            if 'user_authenticated' not in st.session_state or not st.session_state['user_authenticated']:
                st.session_state['user_authenticated'] = True
                st.session_state['user_name'] = st.session_state.get('user_name', 'guest')
        
        # Carregar preferências de UI do Banco de Dados (Persistência Permanente)
        if 'accent_color' not in st.session_state:
            st.session_state['accent_color'] = db.get_preference('accent_color', "#4DA768")
        if 'card_text_color' not in st.session_state:
            st.session_state['card_text_color'] = db.get_preference('card_text_color', "#ffffff")
        if 'main_bg_color' not in st.session_state:
            st.session_state['main_bg_color'] = db.get_preference('main_bg_color', "#73C883")
        if 'card_bg_hex' not in st.session_state:
            st.session_state['card_bg_hex'] = db.get_preference('card_bg_hex', "#ffffff")
        if 'premium_dark_mode' not in st.session_state:
            saved_dark = db.get_preference('premium_dark_mode', 'false')
            st.session_state['premium_dark_mode'] = (saved_dark == 'true')

        # Carregar tema premium salvo (paleta pronta aplicada sobre as cores individuais)
        if 'premium_theme' not in st.session_state:
            saved_theme = db.get_preference('premium_theme', '')
            st.session_state['premium_theme'] = saved_theme if saved_theme in PREMIUM_THEMES else ''
        
        # Carregar foto de perfil do banco (apenas uma vez por sessão)
        if 'profile_photo_b64' not in st.session_state:
            try:
                saved_photo = db.get_preference('profile_photo_b64')
                saved_mime = db.get_preference('profile_photo_mime', 'image/jpeg')
                if saved_photo:
                    st.session_state['profile_photo_b64'] = saved_photo
                    st.session_state['profile_photo_mime'] = saved_mime
            except Exception:
                pass
            
        is_dark = st.session_state.get('premium_dark_mode', False)
        accent = st.session_state.get('accent_color', '#4DA768')
        txt_color = st.session_state.get('card_text_color', '#ffffff')
        main_bg = st.session_state.get('main_bg_color', '#73C883')
        card_bg_hex = st.session_state.get('card_bg_hex', '#ffffff')
        
        # Lógica de transparência para o fundo do card (Glassmorphism se for branco)
        card_bg_css = "rgba(255, 255, 255, 0.15)" if card_bg_hex.lower() == "#ffffff" else card_bg_hex
        
        apply_custom_css(dark_mode=is_dark, primary_accent=accent, card_text_color=txt_color, main_bg_color=main_bg, card_bg_color=card_bg_css)
        apply_plotly_theme(dark_mode=is_dark)
        if st.session_state.get('user_authenticated', False):
            with st.sidebar:
                u_name = st.session_state.get('user_name', 'Admin')
                # Card de perfil premium
                photo_b64 = st.session_state.get('profile_photo_b64', '')
                photo_mime = st.session_state.get('profile_photo_mime', 'image/jpeg')
                if photo_b64:
                    avatar_html = (
                        f"<div style='width:40px;height:40px;border-radius:50%;overflow:hidden;"
                        f"border:2px solid rgba(255,255,255,0.5);flex-shrink:0;"
                        f"box-shadow:0 2px 8px rgba(0,0,0,0.2);'>"
                        f"<img src='data:{photo_mime};base64,{photo_b64}' "
                        f"style='width:100%;height:100%;object-fit:cover;'/></div>"
                    )
                else:
                    avatar_html = (
                        "<div style='width:40px;height:40px;"
                        "background:linear-gradient(135deg,#ffffff33,#ffffff22);"
                        "border:2px solid rgba(255,255,255,0.4);border-radius:50%;"
                        "display:flex;align-items:center;justify-content:center;"
                        "font-size:18px;flex-shrink:0;'>&#128105;&#8205;&#9877;&#65039;</div>"
                    )
                # Avatar com foto ou ícone padrão
                if photo_b64:
                    avatar_inner = (
                        f"<img src='data:{photo_mime};base64,{photo_b64}' "
                        f"style='width:100%;height:100%;object-fit:cover;border-radius:50%;'/>"
                    )
                else:
                    avatar_inner = "<span style='font-size:22px;line-height:44px;'>&#128105;&#8205;&#9877;&#65039;</span>"

                st.markdown(
                    f"""<div style='background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.18);
                    border-radius:16px;padding:14px 16px;margin-bottom:8px;
                    display:flex;align-items:center;gap:12px;backdrop-filter:blur(8px);'>
                        <div style='width:44px;height:44px;border-radius:50%;overflow:hidden;
                            border:2px solid rgba(255,255,255,0.4);
                            box-shadow:0 2px 8px rgba(0,0,0,0.2);
                            display:flex;align-items:center;justify-content:center;
                            background:rgba(255,255,255,0.15);flex-shrink:0;'>
                            {avatar_inner}
                        </div>
                        <div>
                            <div style='font-weight:700;font-size:0.88rem;color:#fff;letter-spacing:0.2px;'>{u_name}</div>
                            <div style='font-size:0.72rem;color:rgba(255,255,255,0.6);letter-spacing:0.5px;text-transform:uppercase;font-weight:600;'>Administradora</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True
                )

                # Uploader de foto compacto direto na sidebar
                sidebar_photo = st.file_uploader(
                    "📷 Trocar foto",
                    type=["jpg", "jpeg", "png", "webp"],
                    key="sidebar_photo_upload",
                    label_visibility="collapsed"
                )
                if sidebar_photo:
                    photo_bytes = sidebar_photo.getvalue()
                    if len(photo_bytes) > 2 * 1024 * 1024:
                        st.error("❌ Máx 2MB")
                    else:
                        b64 = base64.b64encode(photo_bytes).decode('utf-8')
                        mime = sidebar_photo.type or 'image/jpeg'
                        st.session_state['profile_photo_b64'] = b64
                        st.session_state['profile_photo_mime'] = mime
                        try:
                            db.save_preference('profile_photo_b64', b64)
                            db.save_preference('profile_photo_mime', mime)
                            st.toast("Foto atualizada!", icon="✅")
                        except Exception:
                            pass
                        st.rerun()

                st.markdown(
                    """<div style='font-size:0.7rem;font-weight:700;letter-spacing:2px;
                    text-transform:uppercase;color:rgba(255,255,255,0.5);
                    margin:4px 0 6px 4px;'>Menu</div>""",
                    unsafe_allow_html=True
                )

                pages = {
                    "⌂ Dashboard": "dashboard",
                    "👥 Pacientes": "patients",
                    "🏢 Empresas": "companies",
                    "📅 Agenda": "agenda",
                    "⦿ Atendimentos": "appointments",
                    "📋 Docs Clínicos": "clinical_docs",
                    "📑 Laudos": "laudos",
                    "🤖 IA": "ia",
                    "💰 Financeiro": "finance",
                    "🔐 Segurança": "security",
                    "🛠️ Extras": "extras",
                    "☰ Relatórios": "reports",
                    "📝 Editor Docs": "docs_editor",
                    "↑ Upload": "upload",
                    "⚙ Configurações": "settings"
                }
                selected_page = st.radio("Selecione a página", list(pages.keys()), index=0, key='nav_radio', label_visibility="collapsed")
                page_key = pages[selected_page]

                st.divider()
                st.markdown("### 💬 IA Assistente")
                answer = ""
                user_msg = st.text_input("Pergunte sobre seus dados...", key="ai_chat_input", placeholder="Ex: Resumo de hoje")
                if user_msg:
                    with st.spinner("IA processando..."):
                        from ai_manager import AIManager
                        appts = DatabaseManager.get_all_appointments()[:100]
                        import json
                        context = json.dumps(appts, default=str)
                        answer = AIManager.chat_with_data(user_msg, context)
                if answer:
                    st.info(answer)
                
                # Logout - Versão Estável (Sem wrappers HTML quebrados)
                st.divider()
                if st.button('🚪 Encerrar Sessão', use_container_width=True, key="logout_btn_sidebar"):
                    security.log_access('AUTH_LOGOUT', f"Usuário {u_name} deslogado")
                    st.session_state['user_authenticated'] = False
                    st.session_state['user_name'] = ''
                    st.rerun()
        else:
            page_key = "dashboard" # Fallback para AuthPage.render() disparar no bloco abaixo
        if page_key == "dashboard":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                DashboardPage.render()
        elif page_key == "patients":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                PatientsPage.render()
        elif page_key == "companies":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                CompaniesPage.render()
        elif page_key == "agenda":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                AgendaPage.render()
        elif page_key == "clinical_docs":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                ClinicalDocsPage.render()
        elif page_key == "laudos":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                LaudosPage.render()
        elif page_key == "ia":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                AIPage.render()
        elif page_key == "finance":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                FinancePage.render()
        elif page_key == "security":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                SecurityPage.render()
        elif page_key == "extras":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                ExtrasPage.render()
        elif page_key == "appointments":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                if 'app_filters' not in st.session_state:
                    st.session_state['app_filters'] = {}
                AppointmentsPage.render(st.session_state['app_filters'])
        elif page_key == "reports":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                ReportsPage.render()
        elif page_key == "docs_editor":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                DocsEditorPage.render()
        elif page_key == "upload":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                UploadPage.render()
        elif page_key == "settings":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                SettingsPage.render()

        # Rodapé com dicas rápidas sobre DB
        if st.session_state.get('user_authenticated', False):
            try:
                st.divider()
            except Exception:
                st.markdown("---")
        conn_ok = verificar_conexao()
        if not conn_ok and st.session_state.get('user_authenticated', False):
            with st.expander("Ajuda rápida: conexão com PostgreSQL", expanded=False):
                st.markdown(
                    "- Em produção (Streamlit Cloud): use um host público (Neon/Render/RDS) e defina Secrets: `DATABASE_URL=postgresql://usuario:senha@host:5432/gestao_clinica`\n"
                    "- Em desenvolvimento local (Windows): abra services.msc e inicie o serviço `postgresql-x64-18`\n"
                    "- Se o banco não existir, crie `gestao_clinica` no pgAdmin/psql\n"
                    "- Verifique usuário/senha e privilégios (pode usar um usuário app de menor privilégio)"
                )

if __name__ == "__main__":
    ClinicalManagementApp().run()