import streamlit as st
import streamlit.components.v1 as components
import db
import os
import base64
import pathlib
import urllib.parse
import html
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
    page_icon="🩺",
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
        f"<span style='display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:999px;"
        f"font-size:0.72rem;font-weight:700;letter-spacing:0.3px;"
        f"background:{style['bg']};color:{style['fg']};"
        f"border:1px solid {style['fg']}55;"
        f"box-shadow:0 1px 6px rgba(0,0,0,0.06);'>"
        f"<span style='width:7px;height:7px;border-radius:50%;background:{style['fg']};box-shadow:0 0 0 2px {style['fg']}22;flex-shrink:0;'></span>{status}</span>"
    )

def empty_state(icon, title, message):
    """Empty state premium: ícone em chip vidrado + texto acolhedor."""
    st.markdown(
        f"""<div style="text-align:center;padding:3.5rem 1.5rem;margin:0.75rem 0;
            background:rgba(255,255,255,0.05);
            border:1.5px dashed rgba(255,255,255,0.22);
            border-radius:26px;
            box-shadow:inset 0 1px 0 rgba(255,255,255,0.06);">
    <div style="width:88px;height:88px;border-radius:28px;margin:0 auto 1.1rem auto;
                background:linear-gradient(135deg,rgba(255,255,255,0.14),rgba(255,255,255,0.04));
                border:1px solid rgba(255,255,255,0.18);
                display:flex;align-items:center;justify-content:center;
                font-size:2.6rem;box-shadow:0 10px 30px rgba(0,0,0,0.12);">{icon}</div>
    <div style="font-size:1.15rem;font-weight:800;color:rgba(255,255,255,0.94);">{title}</div>
    <div style="font-size:0.85rem;color:rgba(255,255,255,0.6);margin-top:5px;max-width:480px;
                margin-left:auto;margin-right:auto;line-height:1.5;">{message}</div>
</div>""",
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
    def get_all_appointments(limit: int | None = None, offset: int = 0):
        try:
            # limit None = compat (carrega tudo) para Dashboard; _render_table passa limit=page_size para paginacao DB
            if limit is not None:
                return db.listar_atendimentos(limit=limit, offset=offset)
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

def display_cards(cards, style="default"):
    if style == "minimal":
        accent = st.session_state.get('accent_color', '#4DA768')
        metric_items = []
        for idx, card in enumerate(cards):
            icon = card.get('icon', '📋')
            title = card.get('title', '')
            value = card.get('value', 0)
            acc = card.get('acc', accent)
            border_style = "border-right:1px solid rgba(255,255,255,0.08);" if idx < len(cards) - 1 else "border-right:none;"
            metric_items.append(
                f"""<div class="metric-card-minimal" style="{border_style}">
    <div class="metric-card-content">
        <div style="
            width: 38px;
            height: 38px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.08rem;
            background: linear-gradient(135deg, {acc}, {acc}cc);
            color: #fff;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
            flex-shrink: 0;
        ">{icon}</div>
        <div style="display:flex; flex-direction:column; min-width:0; flex:1;">
            <div style="
                font-size: clamp(1.5rem, 1.9vw, 2.05rem);
                font-weight: 800;
                color: #ffffff;
                line-height: 1.02;
                letter-spacing: -0.08em;
            ">{value}</div>
            <div style="
                font-size: 0.67rem;
                font-weight: 700;
                letter-spacing: 0.12rem;
                text-transform: uppercase;
                color: rgba(255,255,255,0.72);
                margin-top: 6px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            ">{title}</div>
        </div>
    </div>
</div>"""
            )

        st.markdown(
            f"""<style>
.metric-row-minimal {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    width: 100%;
    gap: 0;
    margin-bottom: 18px;
}}
@media (max-width: 860px) {{
    .metric-row-minimal {{
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }}
}}
@media (max-width: 540px) {{
    .metric-row-minimal {{
        grid-template-columns: 1fr !important;
    }}
    .metric-row-minimal > div {{
        border-right: none !important;
        border-bottom: 1px solid rgba(255,255,255,0.05) !important;
    }}
    .metric-row-minimal > div:last-child {{
        border-bottom: none !important;
    }}
}}
</style>
<div class="metric-row-minimal">
    {''.join(metric_items)}
</div>""",
            unsafe_allow_html=True
        )
        return

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
            acc   = card.get('acc', accent)

            delta_html = ""
            if delta is not None:
                sign  = "▲" if str(delta).startswith('+') or (isinstance(delta, (int,float)) and delta > 0) else "▼"
                color = "#4ade80" if sign == "▲" else "#f87171"
                delta_html = f"<div style='font-size:0.72rem;font-weight:600;color:{color};margin-top:2px;'>{sign} {delta}</div>"

            st.markdown(
                f"""<div style="
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
        color:{txt};opacity:0.75;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    ">{title}</div>
    <div style="
        font-size:2rem;font-weight:800;
        color:{txt};letter-spacing:-1px;line-height:1;
    ">{value}</div>
    {delta_html}
</div>""",
                unsafe_allow_html=True
            )


def render_page_header(title, subtitle, inverse=False):
    st.markdown(
        f"""<div class="page-header">
    <div class="page-header-copy">
        <div class="page-header-kicker">Gestão Clínica</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
</div>""",
        unsafe_allow_html=True
    )
    st.divider()

def section_title(emoji, text, sub=None, accent=None):
    acc = accent or st.session_state.get('accent_color', PRIMARY_ACCENT)
    sub_html = f"<div style='font-size:0.8rem;color:rgba(255,255,255,0.6);font-weight:400;margin-top:4px;letter-spacing:0.2px;'>{sub}</div>" if sub else ""
    st.markdown(
        f"""<div style='display:flex;align-items:center;gap:12px;margin:28px 0 14px 0;'>
    <div style='width:38px;height:38px;border-radius:12px;flex-shrink:0;
        background:linear-gradient(135deg,{acc},{acc}99);
        display:flex;align-items:center;justify-content:center;font-size:1.1rem;
        box-shadow:0 4px 14px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.35);'>{emoji}</div>
    <div style='min-width:0;flex:1;'>
        <div style='font-size:1.05rem;font-weight:800;color:#fff;letter-spacing:0.2px;font-family:\"Plus Jakarta Sans\",sans-serif;'>{text}</div>
        <div style='height:3px;width:64px;border-radius:99px;margin-top:5px;
            background:linear-gradient(90deg,{acc},{acc}00);'></div>
        {sub_html}
    </div>
</div>""",
        unsafe_allow_html=True
    )

def apply_custom_css(dark_mode=False, primary_accent="#4DA768", card_text_color="#ffffff", main_bg_color="#73C883", card_bg_color="rgba(255, 255, 255, 0.15)"):
    # Paleta Dinâmica — usa variáveis já existentes
    bg_main = "#121212" if dark_mode else main_bg_color
    # Sidebar usa verde escuro #1E7A46 conforme spec Streamlit Cloud (confiável)
    bg_sidebar_top = "#1a1a1a" if dark_mode else "#1E7A46"
    bg_sidebar_bottom = "#1a1a1a" if dark_mode else "#155c33"
    card_bg = "rgba(255, 255, 255, 0.05)" if dark_mode else card_bg_color

    # 1. GOOGLE FONTS via <link> separado (confiável no Cloud, não usa @import)
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">', unsafe_allow_html=True)

    st.markdown(
        f'''<style>
        /* ── 3. FUNDO PRINCIPAL (.stApp) + TIPOGRAFIA (h1,h2,h3,p) ── */
        .stApp {{
            background-color: {bg_main} !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}
        h1 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 800 !important;
            font-size: 2.15rem !important;
            letter-spacing: -1px !important;
            line-height: 1.15 !important;
            background: linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.75) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        h2, h3 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 700 !important;
            color: #ffffff !important;
            letter-spacing: -0.5px;
        }}
        p {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            line-height: 1.6;
        }}
        /* Labels uppercase 1.2px */
        .stTextInput label, .stSelectbox label, .stTextArea label, .stDateInput label {{
            font-weight: 700 !important;
            font-size: 0.72rem !important;
            text-transform: uppercase !important;
            letter-spacing: 1.2px !important;
            opacity: 0.85;
        }}

        /* ── ANIMAÇÃO FADEIN 0.45s + FUNDO GLOBAL EM TODAS AS PÁGINAS ── */
        @keyframes appFadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .stApp {{
            animation: appFadeIn 0.45s ease;
            background-color: {bg_main} !important;
        }}
        /* Garante que Dashboard, Atendimentos, Upload, Laudos, Extras, Relatórios, Docs e Config herdam o mesmo CSS */
        .stApp * {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}

        /* ── 4. SIDEBAR PREMIUM — refinamento SaaS sem trocar paleta #1E7A46/#155c33 ── */
        section[data-testid="stSidebar"] > div {{
            background: linear-gradient(180deg, {bg_sidebar_top} 0%, {bg_sidebar_bottom} 100%) !important;
            padding-top: 10px !important;
            position: relative !important;
        }}
        section[data-testid="stSidebar"] > div::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 12px;
            right: 12px;
            height: 1px;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.16), transparent);
            pointer-events: none;
        }}
        section[data-testid="stSidebar"] * {{
            color: white !important;
        }}
        /* Esconde bolinha nativa do radio */
        section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {{
            display: none !important;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] {{
            display: flex;
            flex-direction: column;
            gap: 6px !important;
            padding: 0 10px !important;
            margin-top: 4px !important;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
            padding: 11px 14px !important;
            margin: 0 !important;
            min-height: 44px !important;
            border-radius: 14px !important;
            cursor: pointer;
            transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
            background: transparent !important;
            border: 1px solid transparent !important;
            font-weight: 600 !important;
            font-size: 0.875rem !important;
            letter-spacing: 0.2px !important;
            line-height: 1.35 !important;
            position: relative !important;
            overflow: hidden !important;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
            background: rgba(255,255,255,0.08) !important;
            border-color: rgba(255,255,255,0.10) !important;
            transform: translateX(2px) !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08) !important;
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:active {{
            transform: translateX(1px) scale(0.99) !important;
        }}

        /* ── 5. CARDS GLASSMORPHISM via .stMetric ── */
        .stMetric {{
            background: {card_bg} !important;
            backdrop-filter: blur(20px) !important;
            -webkit-backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255,255,255,0.18) !important;
            border-radius: 20px !important;
            padding: 22px 20px 18px 20px !important;
            box-shadow: 0 4px 24px rgba(0,0,0,0.07), inset 0 1px 0 rgba(255,255,255,0.18) !important;
            transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
        }}
        .stMetric:hover {{
            transform: translateY(-6px) scale(1.02) !important;
            border-color: rgba(255,255,255,0.28) !important;
            box-shadow: 0 12px 36px rgba(0,0,0,0.14), inset 0 1px 0 rgba(255,255,255,0.22) !important;
        }}
        .stMetric label, [data-testid="stMetricLabel"] {{
            color: {card_text_color} !important;
            font-weight: 700 !important;
            font-size: 0.72rem !important;
            text-transform: uppercase !important;
            letter-spacing: 1.2px !important;
            opacity: 0.85;
        }}
        [data-testid="stMetricValue"] {{
            color: {card_text_color} !important;
            font-weight: 800 !important;
            font-size: 2rem !important;
            letter-spacing: -1px !important;
        }}

        /* ── 4. TABELA/DATAFRAME ── */
        .stDataFrame {{
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 18px !important;
            overflow: hidden !important;
            box-shadow: 0 8px 28px rgba(0,0,0,0.08) !important;
        }}
        .stDataFrame thead tr th {{
            background: rgba(255,255,255,0.06) !important;
            font-weight: 700 !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.5px !important;
            text-transform: uppercase !important;
            color: rgba(255,255,255,0.85) !important;
        }}
        .stDataFrame tbody tr {{
            transition: background 0.15s ease !important;
        }}
        .stDataFrame tbody tr:hover {{
            background: rgba(255,255,255,0.05) !important;
        }}

        /* ── 5. BOTÕES (.stButton > button) ── */
        .stButton > button {{
            width: 100%;
            background: linear-gradient(135deg, {primary_accent} 0%, {primary_accent}D9 100%) !important;
            color: white !important;
            font-weight: 700 !important;
            font-size: 0.92rem !important;
            letter-spacing: 0.4px !important;
            border-radius: 14px !important;
            padding: 11px 22px !important;
            border: 1px solid rgba(255,255,255,0.20) !important;
            border-top: 1px solid rgba(255,255,255,0.28) !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.20) !important;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        }}
        .stButton > button:hover {{
            transform: translateY(-3px) !important;
            box-shadow: 0 12px 28px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.28) !important;
            filter: brightness(1.05);
        }}

        /* ── 9. INPUTS confiáveis ── */
        .stTextInput > div > div > input {{
            border-radius: 14px !important;
            border: 1.5px solid rgba(255,255,255,0.15) !important;
            background: rgba(255,255,255,{0.05 if dark_mode else 0.95}) !important;
            color: {"white" if dark_mode else "#1a1a1a"} !important;
            padding: 12px 16px !important;
            font-size: 0.92rem !important;
            font-weight: 500 !important;
        }}
        .stTextInput > div > div > input:focus {{
            border-color: {primary_accent} !important;
            box-shadow: 0 0 0 4px {primary_accent}25 !important;
            outline: none !important;
        }}
        .stSelectbox > div > div {{
            border-radius: 14px !important;
            border: 1.5px solid rgba(255,255,255,0.15) !important;
            background: rgba(255,255,255,{0.05 if dark_mode else 0.95}) !important;
        }}
        .stSelectbox > div > div:focus-within {{
            border-color: {primary_accent} !important;
            box-shadow: 0 0 0 4px {primary_accent}25 !important;
        }}

        /* ── 7. TABS (.stTabs) ── */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px !important;
            background: rgba(255,255,255,0.07) !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 16px !important;
            padding: 5px !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 11px !important;
            padding: 9px 16px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            color: rgba(255,255,255,0.75) !important;
            border: none !important;
        }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background: linear-gradient(135deg, {primary_accent} 0%, {primary_accent}CC 100%) !important;
            color: #fff !important;
            box-shadow: 0 4px 14px rgba(0,0,0,0.14) !important;
        }}
        .stTabs [data-baseweb="tab-highlight"] {{
            background: transparent !important;
        }}

        /* ── EXPANDERS (.stExpander) ── */
        .stExpander {{
            border: 1px solid rgba(255,255,255,0.10) !important;
            background: rgba(255,255,255,0.04) !important;
            border-radius: 18px !important;
        }}

        /* ── 8. FILE UPLOADER esconde instruções, mostra só botão ── */
        [data-testid="stFileUploaderDropzoneInstructions"] {{
            display: none !important;
        }}
        [data-testid="stFileUploaderDropzone"] {{
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 12px !important;
            background: rgba(255,255,255,0.04) !important;
        }}

        /* ── GLOBAL / HEADER ── */
        .page-header {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 18px;
            margin: 0 0 20px;
            padding: 6px 0 18px;
            border-bottom: 1px solid rgba(255,255,255,0.14);
        }}
        .page-header-kicker {{
            color: {primary_accent};
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.14rem;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .page-header h1 {{ margin: 0 !important; }}
        .page-header p {{
            color: rgba(255,255,255,0.72);
            font-size: 0.9rem;
            margin: 8px 0 0;
        }}

        /* ── METRIC CARDS ── */
        .metric-row-minimal {{ align-items: stretch; }}
        .metric-card-minimal {{
            min-height: 122px;
            padding: 16px 18px;
            background: linear-gradient(145deg, rgba(255,255,255,0.16), rgba(255,255,255,0.06));
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 16px;
            box-shadow: 0 10px 26px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.16);
            transition: transform 0.22s ease, box-shadow 0.22s ease;
        }}
        .metric-card-minimal:hover {{
            transform: translateY(-3px);
            box-shadow: 0 16px 30px rgba(0,0,0,0.16), inset 0 1px 0 rgba(255,255,255,0.22);
        }}
        .metric-card-content {{
            display: flex;
            align-items: center;
            gap: 12px;
            min-height: 90px;
        }}
        .metric-card-content > div:first-child {{ border-radius: 12px !important; }}

        /* ── AI ASSISTANT / FILTERS / CHARTS ── */
        .ai-insight-card {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 20px 22px;
            border: 1px solid {primary_accent}66;
            border-radius: 16px;
            background: linear-gradient(135deg, {primary_accent}2a, rgba(255,255,255,0.07));
            box-shadow: 0 12px 28px rgba(0,0,0,0.10);
        }}
        .ai-insight-card .ai-label {{
            color: {primary_accent}; font-size: 0.68rem; font-weight: 800;
            letter-spacing: 0.14rem; text-transform: uppercase; margin-bottom: 7px;
        }}
        .dashboard-filter {{
            padding: 10px 14px 2px;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 14px;
            background: rgba(0,0,0,0.10);
            margin-bottom: 12px;
        }}
        .chart-panel {{
            padding: 8px 12px 2px;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 16px;
            background: rgba(0,0,0,0.12);
            min-height: 390px;
        }}
        .ranking-table {{
            width: 100%; border-collapse: collapse; margin-top: 8px;
            color: rgba(255,255,255,0.9); font-size: 0.86rem;
        }}
        .ranking-table th {{
            padding: 10px 8px; color: rgba(255,255,255,0.58);
            font-size: 0.68rem; letter-spacing: 0.09rem; text-align: left;
            text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.14);
        }}
        .ranking-table td {{ padding: 11px 8px; border-bottom: 1px solid rgba(255,255,255,0.08); }}
        .ranking-table tr:last-child td {{ border-bottom: 0; }}
        .ranking-rank {{ color: {primary_accent}; font-weight: 800; width: 38px; }}
        .ranking-share {{ color: rgba(255,255,255,0.62); text-align: right; }}

        /* ── SIDEBAR / BUTTONS / RESPONSIVE ── */
        section[data-testid="stSidebar"] .stDivider {{ opacity: 0.5; }}
        section[data-testid="stSidebar"] [data-testid="stRadio"] {{ margin-top: 4px; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
            background: linear-gradient(135deg, rgba(123, 211, 137, 0.24), rgba(255,255,255,0.06)) !important;
            border-color: rgba(168, 235, 177, 0.42) !important;
            box-shadow: inset 3px 0 0 #8ee39a, 0 4px 16px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.10) !important;
            font-weight: 700 !important;
            transform: translateX(1px) !important;
        }}
        /* ── SIDEBAR PREMIUM — logout e uploader refinados (isolado, só sidebar) ── */
        section[data-testid="stSidebar"] .stButton > button {{
            background: rgba(255,255,255,0.06) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            color: rgba(255,255,255,0.92) !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            letter-spacing: 0.2px !important;
            border-radius: 12px !important;
            padding: 10px 14px !important;
            transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: none !important;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: rgba(255,255,255,0.10) !important;
            border-color: rgba(255,255,255,0.18) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] {{
            background: rgba(255,255,255,0.09) !important;
            border: 1.5px solid rgba(255,255,255,0.20) !important;
            border-top: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 0 0 18px 18px !important;
            padding: 10px 14px 12px !important;
            margin-top: -1px !important;
            margin-bottom: 10px !important;
            transition: all 0.22s ease !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.06) !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stFileUploader"]:hover {{
            border-color: rgba(255,255,255,0.22) !important;
            background: rgba(255,255,255,0.11) !important;
        }}
        /* Botão interno do uploader — pill premium usando só branco translúcido (mesma paleta) */
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {{
            background: rgba(255,255,255,0.10) !important;
            border: 1px solid rgba(255,255,255,0.14) !important;
            color: #fff !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.78rem !important;
            padding: 6px 12px !important;
            transition: all 0.22s ease !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] button:hover {{
            background: rgba(255,255,255,0.16) !important;
            border-color: rgba(255,255,255,0.22) !important;
            transform: translateY(-1px) !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stFileUploader"] small {{
            color: rgba(255,255,255,0.62) !important;
            font-size: 0.68rem !important;
            letter-spacing: 0.3px !important;
        }}
        .stDateInput > div > div {{ border-radius: 12px !important; }}
        @media (max-width: 860px) {{
            .metric-row-minimal {{ gap: 10px; }}
            .metric-card-minimal {{ border-right: none !important; }}
            .page-header {{ padding-bottom: 14px; }}
        }}
        @media (max-width: 540px) {{
            .page-header {{ margin-bottom: 14px; padding-top: 0; }}
            .page-header h1 {{ font-size: 1.72rem !important; }}
            .page-header p {{ font-size: 0.82rem; }}
            .metric-row-minimal {{ gap: 8px; }}
            .metric-card-minimal {{ min-height: 104px; padding: 12px; }}
            .metric-card-content {{ min-height: 76px; gap: 9px; }}
            .metric-card-content > div:first-child {{ width: 32px !important; height: 32px !important; font-size: 0.9rem !important; }}
            .chart-panel {{ min-height: 0; padding: 4px; }}
            .ranking-table {{ font-size: 0.78rem; }}
            .ranking-table th, .ranking-table td {{ padding: 9px 5px; }}
        }}

        /* ── DIVIDER sutil ── */
        hr {{
            border: none !important;
            height: 1px !important;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.15), transparent) !important;
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
        render_page_header("⌂ Dashboard", f"{saudacao} • {data_pt} • {hora_pt} • {status_label}")
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
        total_pacientes = 0
        try:
            total_pacientes = len(db.listar_pacientes(limit=None)) if hasattr(db, "listar_pacientes") else 0
        except Exception:
            total_pacientes = 0
        # Fallback: se pacientes 0 mas atendimentos tem dados (compat schema), conta distintos via atendimentos
        if total_pacientes == 0 and total_appointments > 0:
            try:
                # tenta via DISTINCT nome dos atendimentos (evita mostrar 0 no dashboard do print)
                with db._connection_scope(commit=False) as _conn:
                    _cur = db._get_cursor(_conn)
                    _cur.execute("SELECT COUNT(DISTINCT nome) AS cnt FROM atendimentos WHERE nome IS NOT NULL AND nome <> ''")
                    _row = _cur.fetchone()
                    if _row and _row.get("cnt"):
                        total_pacientes = int(_row["cnt"])
            except Exception:
                pass
            if total_pacientes == 0:
                # último fallback: conta distintos em memória dos appointments já carregados
                try:
                    total_pacientes = len(set(str(a[2]).strip().lower() for a in appointments if len(a) > 2 and str(a[2]).strip()))
                except Exception:
                    pass

        total_documentos = 0
        try:
            total_documentos = len(db.listar_arquivos()) if hasattr(db, "listar_arquivos") else 0
        except Exception:
            total_documentos = 0

        total_faturas = 0
        try:
            empresas_all = db.listar_empresas(limit=500) if hasattr(db, "listar_empresas") else []
            for empresa in empresas_all:
                try:
                    total_faturas += len(db.listar_faturamento_empresa(empresa["id"]))
                except Exception:
                    continue
        except Exception:
            total_faturas = 0

        cards = [
            {"icon": "👥", "title": "Pacientes", "value": total_pacientes, "acc": accent},
            {"icon": "📋", "title": "Atendimentos", "value": total_appointments, "acc": accent},
            {"icon": "📄", "title": "Documentos", "value": total_documentos, "acc": accent},
            {"icon": "📝", "title": "Avaliações", "value": avaliacoes_enviadas, "acc": accent},
        ]
        display_cards(cards, style="minimal")

        if total_appointments > 0:
            section_title("🧠", "Insights da IA Assistente", "Análise automática dos seus atendimentos", accent=accent)
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
                st.markdown(
                    f"""<div class="ai-insight-card">
    <div style="font-size:1.55rem;line-height:1;">🤖</div>
    <div style="min-width:0;flex:1;">
        <div class="ai-label">IA Assistente · Insights do período</div>
        <div style="color:rgba(255,255,255,0.92);line-height:1.65;font-size:0.95rem;">{html.escape(str(dicas))}</div>
    </div>
</div>""",
                    unsafe_allow_html=True
                )
        else:
            empty_state("✨", "Painel vazio", "Cadastre seu primeiro atendimento para ver a mágica acontecer.")
        
        if total_appointments > 0:
            section_title("📊", "Distribuição por Modalidade & Empresa", "Use o calendário para escolher o período e ver quantos atendimentos cada empresa teve.", accent=accent)

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
                    fig = px.pie(values=vals, names=labels, hole=0.58,
                                 color_discrete_sequence=['#164B2A', '#24753D', '#379451', '#58B86A', '#8DDB98'])
                    fig.update_traces(textposition="inside", textinfo="percent",
                                      marker=dict(line=dict(color='rgba(255,255,255,0.18)', width=2)),
                                      hovertemplate="%{label}<br>%{value} atendimentos (%{percent})<extra></extra>")
                    fig.update_layout(showlegend=True, height=350, margin=dict(l=8, r=8, t=12, b=12),
                                      legend=dict(orientation="h", yanchor="bottom", y=-0.16, xanchor="center", x=0.5),
                                      annotations=[dict(text=f"{sum(vals)}<br><span style='font-size:11px'>total</span>",
                                                        x=0.5, y=0.5, showarrow=False, font=dict(size=22, color="#FFFFFF"))],
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      font=dict(color="#FFFFFF", family="Plus Jakarta Sans"))
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            with col_p2:
                if contagem_empresas:
                    st.markdown("#### 🏢 Atendimentos por Empresa")
                    empresa_df = pd.DataFrame(sorted(contagem_empresas.items(), key=lambda item: item[1], reverse=True),
                                              columns=["Empresa", "Atendimentos"]).head(10)
                    fig = px.bar(empresa_df.sort_values("Atendimentos"), x="Atendimentos", y="Empresa",
                                 orientation="h", color="Atendimentos",
                                 color_continuous_scale=["#B7E8BF", "#24753D"])
                    fig.update_traces(hovertemplate="%{y}<br>%{x} atendimentos<extra></extra>")
                    fig.update_layout(showlegend=False, coloraxis_showscale=False, height=350,
                                      margin=dict(l=8, r=18, t=12, b=12),
                                      xaxis=dict(title=None, showgrid=True, gridcolor="rgba(255,255,255,0.10)",
                                                 zeroline=False, tickfont=dict(color="rgba(255,255,255,0.7)")),
                                      yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      font=dict(color="#FFFFFF", family="Plus Jakarta Sans"))
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            if contagem_empresas:
                with st.expander("🏆 Ranking por Empresa", expanded=False):
                    ranking = sorted(contagem_empresas.items(), key=lambda item: -item[1])
                    total_v = sum(value for _, value in ranking)
                    rows_html = [
                        '<table class="ranking-table"><thead><tr><th>#</th><th>Empresa</th><th>Atendimentos</th><th class="ranking-share">Participação</th></tr></thead><tbody>'
                    ]
                    for pos, (emp, qtde) in enumerate(ranking[:10], start=1):
                        participacao = (qtde / total_v * 100) if total_v else 0
                        rows_html.append(
                            f"<tr><td class='ranking-rank'>{pos}</td><td>{html.escape(str(emp))}</td>"
                            f"<td>{qtde}</td><td class='ranking-share'>{participacao:.1f}%</td></tr>"
                        )
                    rows_html.append('</tbody></table>')
                    st.markdown("".join(rows_html), unsafe_allow_html=True)
                    st.caption(f"🏢 {len(ranking)} empresa(s) — {total_v} atendimento(s) no período.")
            else:
                empty_state("📅", "Nada por aqui", "Não há atendimentos no período selecionado. Ajuste o calendário acima.")

def _pac_initials(nome: str) -> str:
    partes = [p for p in str(nome or "").strip().split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


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
            # ─── Integração Pacientes: seletor de paciente já cadastrado (pré-preenche o nome) ───
            try:
                pacientes_existentes = db.listar_pacientes(limit=100) or []
            except Exception:
                pacientes_existentes = []
            opcoes_pac = {"➕ Digitar novo paciente": None}
            for _p in pacientes_existentes:
                _p_tel = str(_p.get("telefone") or "").strip()
                _p_label = str(_p["nome"] or "").strip()
                if _p_tel:
                    _p_label += f" — {_p_tel}"
                if _p_label and _p_label not in opcoes_pac:
                    opcoes_pac[_p_label] = _p["id"]
            sel_pac = st.selectbox("👤 Paciente (selecione se já estiver cadastrado)", list(opcoes_pac.keys()), key="new_apt_pac")
            if opcoes_pac[sel_pac] is not None:
                _pac_info = db.obter_paciente(opcoes_pac[sel_pac])
                if _pac_info:
                    st.session_state["new_apt_nome"] = str(_pac_info.get("nome") or "")

            with st.container(border=True):
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
                            # ─── Integração Pacientes: garante que o paciente apareça na página Pacientes ───
                            try:
                                dups = db.buscar_pacientes_duplicados(nome)
                                if dups:
                                    st.toast(f"Paciente já cadastrado (#{dups[0]['id']}) — reutilizado automaticamente.", icon="ℹ️")
                                else:
                                    novo_pac_id = db.inserir_paciente({"nome": nome, "ativo": True})
                                    if novo_pac_id:
                                        st.toast(f"Paciente cadastrado automaticamente (#{novo_pac_id}) — já aparece na página Pacientes!", icon="✅")
                            except Exception:
                                pass
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
        AppointmentsPage._gestao_pacientes()

    @staticmethod
    def _render_table(filters):
        # limit 1000 para nao carregar 5000 como antes no Next.js
        appointments = DatabaseManager.get_all_appointments(limit=1000)
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

        # ── Lista moderna (app, não planilha) ──
        for _, r in page_df.iterrows():
            pid = r["ID"]
            # initials
            nome = str(r["Nome"])
            initials = "".join([p[0].upper() for p in nome.split()[:2]]) if nome.strip() else "?"
            st.markdown(
                f"""<div style="display:flex;align-items:center;gap:14px;
                    background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);
                    border-radius:18px;padding:14px 16px;margin-bottom:10px;
                    transition:all 0.2s ease;box-shadow:0 4px 14px rgba(0,0,0,0.08);">
    <div style="width:42px;height:42px;border-radius:50%;flex-shrink:0;
        background:linear-gradient(135deg,#4DA768,#1E7A46);
        display:flex;align-items:center;justify-content:center;
        color:#fff;font-weight:800;font-size:0.85rem;">{initials}</div>
    <div style="min-width:0;flex:1;">
        <div style="font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{nome}</div>
        <div style="font-size:0.78rem;color:rgba(255,255,255,0.6);">{r["Empresa"]} · {r["Modalidade"]} · {r["Data"]} {r["Hora"]}</div>
    </div>
    <div style="flex-shrink:0;">{status_badge(r["Status"])}</div>
    <div style="display:flex;gap:6px;flex-shrink:0;">
        <span style="font-size:0.7rem;padding:4px 8px;border-radius:999px;background:rgba(59,130,246,0.12);color:#93c5fd;border:1px solid rgba(59,130,246,0.25);">Laudo: {r["Laudo"]}</span>
        <span style="font-size:0.7rem;padding:4px 8px;border-radius:999px;background:rgba(168,85,247,0.12);color:#c4b5fd;border:1px solid rgba(168,85,247,0.25);">Aval: {r["Avaliação"]}</span>
    </div>
</div>""",
                unsafe_allow_html=True,
            )

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

    @staticmethod
    def _gestao_pacientes() -> None:
        section_title("👥", "Gestão de Pacientes", "Prontuário eletrônico, anamnese e evolução clínica — integrado ao Atendimento")

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

                pacientes = db.listar_pacientes(busca or None, ativos_apenas=so_ativos, limit=100)
                if not pacientes:
                    st.info("Nenhum paciente encontrado.")
                else:
                    card_cores = [
                        ("#1E7A46", "#4DA768"),
                        ("#1D5FA8", "#5FA8D3"),
                        ("#6C3FA8", "#9B7BD6"),
                        ("#8A1F3D", "#C24A6B"),
                    ]
                    cards_html = ['<div style="display:flex;flex-wrap:wrap;gap:14px;margin-top:6px;">']
                    for i, p in enumerate(pacientes):
                        nome = html.escape(p["nome"] or "")
                        ini = html.escape(_pac_initials(p["nome"]))
                        c1, c2 = card_cores[i % len(card_cores)]
                        ativo = bool(p["ativo"])
                        status = "Ativo" if ativo else "Inativo"
                        st_cor = "#22C55E" if ativo else "#EF4444"
                        st_fundo = "rgba(34,197,94,0.14)" if ativo else "rgba(239,68,68,0.14)"
                        contatos = []
                        if p.get("telefone"):
                            contatos.append(f"📞&nbsp;&nbsp;{html.escape(str(p['telefone']))}")
                        if p.get("email"):
                            contatos.append(f"✉️&nbsp;&nbsp;{html.escape(str(p['email']))}")
                        if p.get("cpf"):
                            contatos.append(f"🪪&nbsp;&nbsp;{html.escape(str(p['cpf']))}")
                        contatos_html = "".join(
                            f"<div style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{c}</div>"
                            for c in contatos
                        ) or "<div style='color:rgba(255,255,255,0.35);font-style:italic;'>Sem contato cadastrado</div>"
                        cards_html.append(f"""<div style='flex:0 1 282px;min-width:250px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:18px;padding:16px 18px;
    transition:transform 0.2s ease, box-shadow 0.2s ease;
    box-shadow:0 4px 14px rgba(0,0,0,0.10);'>
    <div style='display:flex;align-items:center;gap:12px;'>
        <div style='width:46px;height:46px;border-radius:50%;flex-shrink:0;
            background:linear-gradient(135deg,{c1},{c2});
            display:flex;align-items:center;justify-content:center;
            color:#fff;font-weight:800;font-size:0.95rem;
            box-shadow:0 3px 10px rgba(0,0,0,0.2);'>{ini}</div>
        <div style='min-width:0;'>
            <div style='font-weight:700;font-size:0.94rem;color:#fff;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{nome}</div>
            <div style='font-size:0.7rem;color:rgba(255,255,255,0.5);font-weight:600;
                letter-spacing:0.4px;'>PACIENTE #{p['id']}</div>
        </div>
    </div>
    <div style='margin-top:12px;font-size:0.78rem;color:rgba(255,255,255,0.78);
        display:flex;flex-direction:column;gap:5px;'>
        {contatos_html}
    </div>
    <div style='margin-top:14px;display:flex;align-items:center;justify-content:space-between;'>
        <span style='background:{st_fundo};color:{st_cor};
            border:1px solid {st_cor}55;border-radius:999px;
            padding:4px 12px;font-size:0.72rem;font-weight:700;'>{status}</span>
        <span style='font-size:0.7rem;color:rgba(255,255,255,0.45);'>📂 Prontuário</span>
    </div>
</div>""")
                    cards_html.append('</div>')
                    st.markdown("".join(cards_html), unsafe_allow_html=True)
                    st.caption(f"{len(pacientes)} paciente(s) encontrado(s). Abra a aba 📂 Prontuário para ver o prontuário completo.")

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
            pacientes_todos = db.listar_pacientes(limit=200)
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

                def _chip_pac(icone, valor):
                    if not valor:
                        return ""
                    return (f"<div style='display:inline-flex;align-items:center;gap:6px;"
                            f"background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.14);"
                            f"border-radius:12px;padding:7px 12px;font-size:0.8rem;font-weight:600;"
                            f"color:rgba(255,255,255,0.92);"
                            f"box-shadow:0 2px 8px rgba(0,0,0,0.06);'>"
                            f"<span style='opacity:.85'>{icone}</span> {html.escape(str(valor))}</div>")

                nasc_c = _chip_pac("🎂", (f"{dt_nasc or '—'}" + (f" ({idade})" if idade else "")) if dt_nasc else "")
                chips_parts = (
                    _chip_pac("🪪", pac.get("cpf"))
                    + _chip_pac("🆔", pac.get("rg"))
                    + nasc_c
                    + _chip_pac("📞", pac.get("telefone"))
                    + _chip_pac("✉️", pac.get("email"))
                    + _chip_pac("🏠", pac.get("endereco"))
                )
                if pac.get("ativo"):
                    status_chip = ("<span style='background:rgba(34,197,94,0.15);border:1px solid #22C55E55;"
                                   "border-radius:99px;padding:7px 14px;font-size:0.78rem;font-weight:800;"
                                   "color:#22C55E;display:inline-flex;align-items:center;gap:6px;'>🟢 Ativo</span>")
                else:
                    status_chip = ("<span style='background:rgba(239,68,68,0.15);border:1px solid #EF444455;"
                                   "border-radius:99px;padding:7px 14px;font-size:0.78rem;font-weight:800;"
                                   "color:#EF4444;display:inline-flex;align-items:center;gap:6px;'>🔴 Inativo</span>")
                st.markdown(
                    f"""<div style='display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;'>
                        {chips_parts}<span style='width:100%;'></span>{status_chip}
                    </div>""",
                    unsafe_allow_html=True,
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
                    # Histórico moderno (cards, não planilha)
                    for a in atts:
                        aid, emp, _, mod, dt, hr, _, _, stt, _ = a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9] if len(a)>9 else ""
                        st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:10px 14px;margin-bottom:8px;">
    <span style="font-size:0.75rem;font-weight:700;color:rgba(255,255,255,0.5);">#{aid}</span>
    <span style="font-weight:600;color:#fff;">{mod}</span>
    <span style="color:rgba(255,255,255,0.6);font-size:0.85rem;">{emp} · {dt} {hr}</span>
    <span style="margin-left:auto;">{status_badge(stt)}</span>
</div>""", unsafe_allow_html=True)
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

        pacientes = db.listar_pacientes(limit=200)

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
                for t in triagens_hoje:
                    grav = t["gravidade"] or "Normal"
                    grav_c = {"Normal":"#22C55E","Prioritário":"#F59E0B","Urgente":"#EF4444"}.get(grav, "#22C55E")
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;background:rgba(255,255,255,0.06);
                        border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:10px 14px;margin-bottom:6px;">
                        <span style="font-weight:700;color:#fff;">{str(t["hora"])[:5]}</span>
                        <span style="color:rgba(255,255,255,0.7);font-size:0.85rem;">{t["medico"] or ""} · {t["peso"] or "—"}kg · {t["pressao"] or "—"} · FC {t["freq_cardiaca"] or "—"}</span>
                        <span style="margin-left:auto;padding:3px 8px;border-radius:999px;font-size:0.7rem;font-weight:700;background:{grav_c}22;color:{grav_c};border:1px solid {grav_c}55;">{grav}</span>
                    </div>""", unsafe_allow_html=True)

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
                    st.markdown(f"""<div style='display:flex;align-items:center;gap:10px;background:{cor};
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
                for t in teleconsultas:
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:10px 14px;margin-bottom:6px;">
    <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#5FA8D3,#1D5FA8);
        display:flex;align-items:center;justify-content:center;color:#fff;">🎥</div>
    <div style="min-width:0;flex:1;">
        <div style="font-weight:600;color:#fff;font-size:0.9rem;">{t.get("paciente_nome") or f"#{t['paciente_id']}"} · {t["medico"]}</div>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.6);">{t["data"]} {str(t["hora"])[:5]} · {t["plataforma"]}</div>
    </div>
    <div>{status_badge(t["status"] or "")}</div>
</div>""", unsafe_allow_html=True)

class ClinicalDocsPage:
    @staticmethod
    def render() -> None:
        render_page_header("📋 Documentos Clínicos", "Prescrições, atestados e encaminhamentos")

        tab1, tab2, tab3 = st.tabs(["💊 Prescrições", "📄 Atestados", "➡️ Encaminhamentos"])

        pacientes = db.listar_pacientes(limit=200)
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
                # Prescrições — cards modernos
                for p in prescricoes:
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:12px 16px;margin-bottom:8px;">
    <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#4DA768,#1E7A46);
        display:flex;align-items:center;justify-content:center;color:#fff;">💊</div>
    <div style="min-width:0;flex:1;">
        <div style="font-weight:700;color:#fff;">{html.escape(p["paciente_nome"] or "")} <span style="color:rgba(255,255,255,0.5);font-weight:400;font-size:0.8rem;">#{p["id"]} · {p["data"]}</span></div>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.6);">{html.escape(p["medico"] or "")} · {html.escape(p["status"] or "")} {"· ✍️ ass." if p["assinatura_digital"] else ""}</div>
    </div>
    <div>{status_badge(p["status"] or "")}</div>
</div>""", unsafe_allow_html=True)

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
                for a in atestados:
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:12px 16px;margin-bottom:8px;">
    <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#C24A6B,#8A1F3D);
        display:flex;align-items:center;justify-content:center;color:#fff;">📄</div>
    <div style="min-width:0;flex:1;">
        <div style="font-weight:700;color:#fff;">{html.escape(a["paciente_nome"] or "")} <span style="color:rgba(255,255,255,0.5);font-size:0.8rem;">#{a["id"]} · {a["data"]}</span></div>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.6);">{html.escape(a["tipo"] or "")} · CID {html.escape(a["cid"] or "—")} · {a["dias_afastamento"] or 0}d · {html.escape(a["medico"] or "")}</div>
    </div>
</div>""", unsafe_allow_html=True)
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
                for e in encaminhamentos:
                    urg = "⚠️ Urgente" if e["urgente"] else ""
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:12px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:12px 16px;margin-bottom:8px;">
    <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#9B7BD6,#6C3FA8);
        display:flex;align-items:center;justify-content:center;color:#fff;">➡️</div>
    <div style="min-width:0;flex:1;">
        <div style="font-weight:700;color:#fff;">{html.escape(e["paciente_nome"] or "")} <span style="color:rgba(255,255,255,0.5);font-size:0.8rem;">#{e["id"]} · {e["data"]}</span> <span style="color:#f87171;font-size:0.8rem;">{urg}</span></div>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.6);">{html.escape(e["especialidade"] or "")} → {html.escape(e["profissional_destino"] or "—")}</div>
    </div>
    <div>{status_badge(e["status"] or "")}</div>
</div>""", unsafe_allow_html=True)
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

            empresas = db.listar_empresas(busca or None, ativas_apenas=so_ativas, limit=100)
            if not empresas:
                st.info("Nenhuma empresa encontrada.")
            else:
                # Empresas — lista moderna
                for e in empresas:
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:14px;background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:12px 16px;margin-bottom:8px;">
    <div style="width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,#1D5FA8,#5FA8D3);
        display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;">🏢</div>
    <div style="min-width:0;flex:1;">
        <div style="font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{html.escape(e["nome"] or "")} <span style="font-weight:400;color:rgba(255,255,255,0.5);font-size:0.8rem;">#{e["id"]}</span></div>
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.6);">{html.escape(e["cnpj"] or "sem CNPJ")} · {html.escape(e["responsavel"] or "—")} · 👥 {e["quantidade_funcionarios"] or 0}</div>
    </div>
    <div style="text-align:right;">
        <div style="font-size:0.8rem;color:rgba(255,255,255,0.7);">{e["plano"] or "—"}</div>
        <div>{status_badge("Ativa" if e["ativo"] else "Inativa")}</div>
    </div>
</div>""", unsafe_allow_html=True)
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
            empresas_todas = db.listar_empresas(limit=200)
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
            empresas_todas = db.listar_empresas(limit=200)
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

        pacientes = db.listar_pacientes(limit=200)
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

        # ── Callback OAuth (fallback) ──
        # Handler principal agora em ClinicalManagementApp.run() (global, antes do roteamento).
        # Este bloco é fallback: se o usuário ainda chegar aqui com ?code=, concluir corretamente.
        # Ordem: detectar code/error -> validar state -> trocar por tokens -> confirmar salvamento -> limpar query -> rerun.
        try:
            def _qp_str_fallback(v):
                if v is None:
                    return ""
                if isinstance(v, (list, tuple)):
                    return str(v[0]) if v else ""
                return str(v)
            qp2 = None
            try:
                qp2 = st.query_params
            except Exception:
                qp2 = None
            has_pending = bool(st.session_state.get("google_pending_code"))
            # Se há ?code na URL e ainda não está em pending, mover para pending (sem limpar ainda)
            if qp2 is not None and "code" in qp2 and not has_pending:
                try:
                    raw_code2 = _qp_str_fallback(qp2.get("code", ""))
                    raw_state2 = _qp_str_fallback(qp2.get("state", ""))
                    if raw_code2:
                        st.session_state["google_pending_code"] = raw_code2
                        st.session_state["google_pending_state"] = raw_state2
                        has_pending = True
                except Exception:
                    pass
            # Detectar erro do Google (ex: access_denied, redirect_uri_mismatch)
            if qp2 is not None and "error" in qp2:
                err2 = _qp_str_fallback(qp2.get("error", ""))
                desc2 = _qp_str_fallback(qp2.get("error_description", ""))
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.error(f"Google retornou erro: {err2} {desc2}".strip())
                try:
                    print(f"[oauth editor fallback] error: {err2}")
                except Exception:
                    pass
                has_pending = False
                st.session_state.pop("google_pending_code", None)
                st.session_state.pop("google_pending_state", None)
            if has_pending and st.session_state.get("google_pending_code"):
                _fb_success = False
                _fb_error = None
                with st.spinner("Conectando ao Google..."):
                    try:
                        code_to_use = st.session_state.get("google_pending_code", "")
                        state_to_use = st.session_state.get("google_pending_state", "")
                        if not code_to_use or not str(code_to_use).strip():
                            raise ValueError("Código de autorização vazio.")
                        creds_tmp = gdocs.exchange_code(str(code_to_use).strip(), expected_state=str(state_to_use or ""))
                        if not creds_tmp or not getattr(creds_tmp, "token", None):
                            raise RuntimeError("Google não retornou credenciais válidas.")
                        if not db.obter_google_tokens():
                            raise RuntimeError("Não foi possível salvar a autorização do Google no banco de dados.")
                        _fb_success = True
                    except Exception as e:
                        _fb_error = e
                if _fb_success:
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    st.session_state.pop("google_pending_code", None)
                    st.session_state.pop("google_pending_state", None)
                    st.toast("Conta Google conectada!", icon="✅")
                    st.rerun()
                elif _fb_error is not None:
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    st.error(f"Falha ao conectar com o Google: {_fb_error}")
                    try:
                        print(f"[oauth editor fallback] falha: {type(_fb_error).__name__}: {_fb_error}")
                    except Exception:
                        pass
                    st.session_state.pop("google_pending_code", None)
                    st.session_state.pop("google_pending_state", None)
        except Exception:
            pass

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
        else:
            # ── Conectado ──
            st.success(f"✅ Conectado: {gdocs.account_info() or 'Google Docs'}")
            if st.button("🔌 Desconectar", key="gdocs_disconnect"):
                gdocs.disconnect()
                st.rerun()

            st.markdown("---")
            st.markdown("### 🚀 Preencher modelo de laudo no Google Docs")
            pacientes = db.listar_pacientes(limit=200)
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
            pacientes = db.listar_pacientes(limit=200)
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
                empresas_fin = db.listar_empresas(limit=200)
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
                empresas_nf = db.listar_empresas(limit=200)
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
            pacientes = db.listar_pacientes(limit=200)
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
            pacientes2 = db.listar_pacientes(limit=200)
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
            pacientes_w = db.listar_pacientes(limit=200)
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
                ("👥 Pacientes", "Cadastro, prontuário, anamnese e evolução clínica — disponível dentro de Atendimentos."),
                ("📅 Atendimentos", "Cadastro de atendimentos, pacientes vinculados automaticamente, anexos e PDFs."),
                ("📋 Docs Clínicos", "Prescrições, atestados e encaminhamentos com geração de PDF."),
                ("📑 Laudos", "Modelos de laudos, emissão com código de autenticação e histórico de versões."),
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
                empresas_fat = db.listar_empresas(limit=200)
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
                    if file_id:
                        try:
                            reg = db.obter_arquivo_por_id(int(file_id))
                            if reg and reg.get("content") is not None:
                                content = reg["content"]
                                # psycopg2 pode retornar memoryview
                                if isinstance(content, memoryview):
                                    content = content.tobytes()
                                st.download_button(
                                    label="⬇️ Baixar",
                                    data=content,
                                    file_name=reg.get("filename","arquivo.pdf"),
                                    mime=reg.get("content_type","application/pdf"),
                                    key=f"download_data_{file_id}",
                                    use_container_width=True
                                )
                            else:
                                st.caption("Sem conteúdo")
                        except Exception as e:
                            st.caption(f"Erro ao carregar: {e}")
        else:
            st.info("Nenhum arquivo no banco ainda.")


class AuthPage:
    @staticmethod
    def render():
        """Página de autenticação Premium — estética máxima."""
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

        # ── CSS ULTRA PREMIUM — estética máxima (glass + mesh + orbs) ──
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');
            [data-testid="stHeader"], footer, #MainMenu { display: none !important; }
            [data-testid="stAppViewContainer"] {
                background: #07130d !important;
                background-image:
                    radial-gradient(at 20% 15%, rgba(77,167,104,0.22) 0px, transparent 50%),
                    radial-gradient(at 90% 85%, rgba(46,204,113,0.18) 0px, transparent 50%),
                    radial-gradient(at 50% 50%, rgba(30,122,70,0.10) 0px, transparent 60%),
                    linear-gradient(180deg, #0b1e14 0%, #07130d 100%) !important;
                min-height: 100vh;
            }
            [data-testid="stAppViewContainer"]::before {
                content: "" !important;
                position: fixed !important;
                inset: 0 !important;
                background:
                    linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
                background-size: 48px 48px;
                mask: radial-gradient(ellipse at center, black 40%, transparent 75%);
                pointer-events: none !important;
                z-index: 0 !important;
            }
            [data-testid="stAppViewContainer"]::after {
                content: "" !important;
                position: fixed !important;
                width: 680px; height: 680px;
                left: -160px; top: -180px;
                background: radial-gradient(circle, rgba(77,167,104,0.28), transparent 70%);
                filter: blur(40px);
                pointer-events: none !important;
                z-index: 0 !important;
            }
            [data-testid="stMainViewContainer"] { background: transparent !important; }
            .main .block-container { padding: 1.2rem 1rem 1rem !important; max-width: 1120px !important; }
            @keyframes authIn { from { opacity:0; transform: translateY(14px) scale(0.98); } to { opacity:1; transform: translateY(0) scale(1); } }
            .auth-shell { position: relative; z-index: 1; display: flex; align-items: center; justify-content: center; min-height: 88vh; padding: 18px 0; }
            .auth-card {
                width: 100%; max-width: 980px;
                display: grid; grid-template-columns: 1.05fr 1.15fr;
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 32px;
                overflow: hidden;
                box-shadow: 0 32px 80px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.12);
                backdrop-filter: blur(28px); -webkit-backdrop-filter: blur(28px);
                animation: authIn 0.7s cubic-bezier(0.16,1,0.3,1);
            }
            @media (max-width: 860px) { .auth-card { grid-template-columns: 1fr; max-width: 520px; } .auth-brand { padding: 28px 24px !important; } }
            .auth-brand {
                padding: 36px 32px; position: relative;
                background:
                    radial-gradient(at 30% 20%, rgba(77,167,104,0.18), transparent 55%),
                    linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
                border-right: 1px solid rgba(255,255,255,0.08);
                display: flex; flex-direction: column; justify-content: space-between;
            }
            .auth-brand-badge {
                display: inline-flex; align-items: center; gap: 8px;
                padding: 7px 12px; border-radius: 999px;
                background: rgba(77,167,104,0.14); border: 1px solid rgba(77,167,104,0.28);
                color: #a8e8b7; font: 700 0.68rem 'Inter',sans-serif; letter-spacing: 0.9px; text-transform: uppercase;
            }
            .auth-title {
                font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; letter-spacing: -1.2px; line-height: 0.95;
                font-size: clamp(1.9rem, 3.2vw, 2.6rem); color: #fff; margin: 18px 0 10px;
            }
            .auth-title span { background: linear-gradient(135deg, #7bd391 0%, #4DA768 55%, #2ecc71 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
            .auth-sub { color: rgba(255,255,255,0.62); font: 500 0.92rem/1.6 'Inter',sans-serif; }
            .auth-feature { display: flex; gap: 12px; align-items: flex-start; margin-top: 18px; }
            .auth-feature-ic { width: 36px; height: 36px; border-radius: 12px; display: grid; place-items: center; flex-shrink: 0;
                background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.10); font-size: 1.02rem; }
            .auth-feature b { color: #fff; font: 700 0.88rem 'Inter',sans-serif; display: block; }
            .auth-feature span { color: rgba(255,255,255,0.58); font: 0.82rem/1.5 'Inter',sans-serif; }
            .auth-stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin-top: 22px; }
            .auth-stat { background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 12px 10px; text-align: center; }
            .auth-stat strong { color: #fff; font: 800 1.05rem 'Plus Jakarta Sans',sans-serif; display: block; }
            .auth-stat em { color: rgba(255,255,255,0.55); font: 600 0.68rem 'Inter',sans-serif; letter-spacing: 0.7px; text-transform: uppercase; font-style: normal; }
            .auth-form-wrap { padding: 32px 28px 24px; background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)); position: relative; }
            .auth-form-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
            .auth-form-head h3 { margin: 0; color: #fff; font: 800 1.15rem 'Plus Jakarta Sans',sans-serif; letter-spacing: -0.4px; }
            .auth-secure { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px;
                background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.09); color: rgba(255,255,255,0.72);
                font: 600 0.70rem 'Inter',sans-serif; letter-spacing: 0.5px; }
            div[data-testid="stForm"] {
                background: rgba(0,0,0,0.22) !important;
                border: 1px solid rgba(255,255,255,0.10) !important;
                border-radius: 20px !important;
                padding: 18px 16px 14px !important;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 12px 32px rgba(0,0,0,0.22) !important;
                backdrop-filter: blur(18px) !important;
            }
            div[data-testid="stForm"] label { color: rgba(255,255,255,0.88) !important; font: 700 0.72rem 'Inter',sans-serif !important; letter-spacing: 0.9px !important; text-transform: uppercase !important; }
            div[data-testid="stForm"] input {
                background: rgba(255,255,255,0.07) !important; border: 1px solid rgba(255,255,255,0.14) !important;
                color: #fff !important; border-radius: 14px !important; padding: 13px 14px !important; font: 500 0.95rem 'Inter',sans-serif !important;
                transition: all 0.22s ease !important;
            }
            div[data-testid="stForm"] input::placeholder { color: rgba(255,255,255,0.42) !important; }
            div[data-testid="stForm"] input:focus {
                border-color: rgba(123,211,145,0.55) !important; background: rgba(255,255,255,0.09) !important;
                box-shadow: 0 0 0 4px rgba(77,167,104,0.18) !important;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
                background: linear-gradient(135deg, #4DA768 0%, #3a9a5c 55%, #2ecc71 100%) !important;
                color: #fff !important; border: 1px solid rgba(255,255,255,0.18) !important; border-top: 1px solid rgba(255,255,255,0.28) !important;
                border-radius: 14px !important; font: 800 0.98rem 'Inter',sans-serif !important; letter-spacing: 0.3px !important;
                padding: 14px 18px !important; box-shadow: 0 12px 28px rgba(77,167,104,0.32), inset 0 1px 0 rgba(255,255,255,0.22) !important;
                position: relative; overflow: hidden; transition: all 0.28s cubic-bezier(0.16,1,0.3,1) !important;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button::after {
                content: ""; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
                transform: translateX(-100%); transition: transform 0.6s ease;
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
                transform: translateY(-2px) !important; box-shadow: 0 18px 36px rgba(77,167,104,0.38) !important; filter: brightness(1.04);
            }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover::after { transform: translateX(100%); }
            div[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:active { transform: translateY(0) scale(0.98) !important; }
            .auth-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
            .auth-attempts { color: rgba(255,255,255,0.55); font: 600 0.72rem 'Inter',sans-serif; letter-spacing: 0.4px; }
            .auth-version { color: rgba(255,255,255,0.38); font: 500 0.70rem 'Inter',sans-serif; letter-spacing: 0.5px; }
            .auth-divider { height: 1px; background: linear-gradient(to right, transparent, rgba(255,255,255,0.10), transparent); margin: 14px 0 0; }
            </style>
        """, unsafe_allow_html=True)

        photo_b64 = db.get_preference('profile_photo_b64')
        photo_mime = db.get_preference('profile_photo_mime', 'image/jpeg')
        if photo_b64:
            avatar_html = (
                f"<div style='width:84px;height:84px;border-radius:22px;overflow:hidden;flex-shrink:0;"
                f"border:1.5px solid rgba(255,255,255,0.18);box-shadow:0 12px 28px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.18);'>"
                f"<img src='data:{photo_mime};base64,{photo_b64}' style='width:100%;height:100%;object-fit:cover;'/></div>"
            )
            avatar_small = (
                f"<img src='data:{photo_mime};base64,{photo_b64}' style='width:100%;height:100%;object-fit:cover;border-radius:50%;'/>"
            )
        else:
            avatar_html = "<div style='width:84px;height:84px;border-radius:22px;display:grid;place-items:center;flex-shrink:0;background:linear-gradient(135deg,rgba(255,255,255,0.12),rgba(255,255,255,0.04));border:1px solid rgba(255,255,255,0.14);box-shadow:0 12px 28px rgba(0,0,0,0.22);font-size:2.2rem;'>🩺</div>"
            avatar_small = "<span style='font-size:1.35rem;line-height:1;'>🩺</span>"

        attempts = st.session_state['login_attempts']
        try:
            _total_pac = len(db.listar_pacientes(limit=1000)) if hasattr(db, 'listar_pacientes') else 0
        except Exception:
            _total_pac = 0
        try:
            _total_apt = len(db.listar_atendimentos(limit=1000)) if hasattr(db, 'listar_atendimentos') else 0
        except Exception:
            _total_apt = 0

        st.markdown('<div class="auth-shell"><div class="auth-card">', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="auth-brand">
                <div>
                    <div class="auth-brand-badge">● Sistema em produção • Seguro & LGPD</div>
                    <div style="display:flex;gap:16px;align-items:center;margin-top:18px;">
                        {avatar_html}
                        <div style="min-width:0;">
                            <div style="color:#fff;font:900 0.82rem 'Inter',sans-serif;letter-spacing:0.6px;text-transform:uppercase;opacity:0.9;">MVP Psicologia</div>
                            <div style="color:rgba(255,255,255,0.55);font:600 0.72rem 'Inter',sans-serif;letter-spacing:1.2px;text-transform:uppercase;margin-top:2px;">Gestão Clínica Premium</div>
                            <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
                                <span style="padding:6px 9px;border-radius:999px;background:rgba(77,167,104,0.14);border:1px solid rgba(77,167,104,0.22);color:#b7e8c3;font:700 0.66rem 'Inter',sans-serif;letter-spacing:0.6px;">✓ Criptografia</span>
                                <span style="padding:6px 9px;border-radius:999px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.09);color:rgba(255,255,255,0.72);font:700 0.66rem 'Inter',sans-serif;">LGPD</span>
                            </div>
                        </div>
                    </div>
                    <div class="auth-title">Gestão<br><span>Clínica</span></div>
                    <div class="auth-sub">Agenda, prontuário e laudos com IA — projetado para psicologia, com estética de SaaS premium e dados 100% seguros.</div>
                    <div class="auth-feature">
                        <div class="auth-feature-ic">⚡</div>
                        <div><b>Fluxo em 1 clique</b><span>Atendimentos, evoluções e documentos sem fricção.</span></div>
                    </div>
                    <div class="auth-feature">
                        <div class="auth-feature-ic">🔒</div>
                        <div><b>Segurança LGPD</b><span>Trilha de auditoria, consentimentos e backup.</span></div>
                    </div>
                    <div class="auth-feature">
                        <div class="auth-feature-ic">🤖</div>
                        <div><b>IA assistente</b><span>Resumos clínicos e insights de gestão.</span></div>
                    </div>
                </div>
                <div>
                    <div class="auth-stats">
                        <div class="auth-stat"><strong>{_total_pac}</strong><em>Pacientes</em></div>
                        <div class="auth-stat"><strong>{_total_apt}</strong><em>Atendimentos</em></div>
                        <div class="auth-stat"><strong>24/7</strong><em>Disponível</em></div>
                    </div>
                    <div style="margin-top:14px;color:rgba(255,255,255,0.38);font:500 0.70rem 'Inter',sans-serif;letter-spacing:0.4px;">© {datetime.now().year} MVP Psicologia • v3.0</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="auth-form-wrap">', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="auth-form-head">
                <h3>Acesse sua conta</h3>
                <span class="auth-secure">🔒 Acesso seguro</span>
            </div>
            <div style="display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:16px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);margin-bottom:14px;">
                <div style="width:42px;height:42px;border-radius:50%;overflow:hidden;flex-shrink:0;display:grid;place-items:center;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.10);">{avatar_small}</div>
                <div style="min-width:0;flex:1;">
                    <div style="color:#fff;font:700 0.88rem 'Inter',sans-serif;">Portal Administrativo</div>
                    <div style="color:rgba(255,255,255,0.55);font:500 0.72rem 'Inter',sans-serif;">Use suas credenciais seguras</div>
                </div>
                <div style="width:10px;height:10px;border-radius:50%;background:#4ade80;box-shadow:0 0 0 6px rgba(74,222,128,0.18);flex-shrink:0;"></div>
            </div>
        """, unsafe_allow_html=True)

        with st.form('auth_form', clear_on_submit=False):
            user = st.text_input('👤 Usuário', placeholder='julianafeitosa')
            pwd  = st.text_input('🔑 Senha', type='password', placeholder='••••••••')
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button('Entrar com segurança  →', type='primary', use_container_width=True)

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

        st.markdown(f"""
            <div class="auth-foot">
                <span class="auth-attempts">Tentativas: <b style="color:#fff">{attempts}/5</b> • Protegido por rate-limit</span>
                <span class="auth-version">v3.0 • #1E7A46</span>
            </div>
            <div class="auth-divider"></div>
            <div style="text-align:center;margin-top:12px;display:flex;align-items:center;justify-content:center;gap:8px;color:rgba(255,255,255,0.42);font:500 0.70rem 'Inter',sans-serif;">
                <span style="width:28px;height:28px;border-radius:9px;display:grid;place-items:center;background:linear-gradient(135deg,#4DA768,#2ecc71);box-shadow:0 6px 16px rgba(0,0,0,0.22);font-size:0.95rem;">🩺</span>
                MVP de Psicologia • Design premium
            </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

class ClinicalManagementApp:
    def __init__(self):
        pass
    def run(self):
        # Google Fonts confiável no Streamlit Cloud (separado, antes do CSS)
        st.markdown('<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">', unsafe_allow_html=True)
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

        # ── CALLBACK GLOBAL GOOGLE DOCS OAUTH (corrigido) ──
        # Deve rodar EM TODA RERUN, antes do roteamento de páginas, para capturar ?code=... independente da página atual.
        # Ordem correta: detectar code/error -> validar state -> trocar por tokens -> confirmar salvamento -> limpar query_params -> rerun.
        try:
            # Helper para extrair string de query_params (compatível list/str)
            def _qp_str(val):
                if val is None:
                    return ""
                if isinstance(val, (list, tuple)):
                    return str(val[0]) if val else ""
                return str(val)
            qp = None
            try:
                qp = st.query_params
            except Exception:
                qp = None
            if qp is not None:
                # 1) Detectar erros retornados pelo Google (ex: access_denied, redirect_uri_mismatch)
                if "error" in qp:
                    err = _qp_str(qp.get("error", ""))
                    desc = _qp_str(qp.get("error_description", qp.get("error", "")))
                    # Limpar para não ficar em loop
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    st.error(f"Google retornou erro: {err} {desc}".strip())
                    try:
                        print(f"[oauth global] error: {err}")
                    except Exception:
                        pass
                elif "code" in qp:
                    raw_code = _qp_str(qp.get("code", ""))
                    raw_state = _qp_str(qp.get("state", ""))
                    if raw_code:
                        # Evitar reprocessar mesmo code em loop (Streamlit pode rerun)
                        import hashlib
                        h = hashlib.sha256(raw_code.encode()).hexdigest()[:16]
                        last_h = st.session_state.get("google_last_code_hash")
                        if last_h == h:
                            try:
                                st.query_params.clear()
                            except Exception:
                                pass
                        else:
                            st.session_state["google_last_code_hash"] = h
                            # Só processar se autenticado (Editor requer login) ou se config presente
                            try:
                                import gdocs as _gdocs_global
                                if _gdocs_global.configurado():
                                    _oauth_success = False
                                    _oauth_error = None
                                    with st.spinner("Conectando ao Google..."):
                                        try:
                                            creds = _gdocs_global.exchange_code(raw_code, expected_state=raw_state)
                                            _oauth_success = True
                                        except Exception as e:
                                            _oauth_error = e
                                    # Fora do spinner para evitar removeChild (bug frontend)
                                    if _oauth_success:
                                        try:
                                            st.query_params.clear()
                                        except Exception:
                                            pass
                                        st.toast("Conta Google conectada!", icon="✅")
                                        st.rerun()
                                    elif _oauth_error is not None:
                                        try:
                                            st.query_params.clear()
                                        except Exception:
                                            pass
                                        st.error(f"Falha ao conectar com o Google: {_oauth_error}")
                                        try:
                                            print(f"[oauth global] exchange falhou: {type(_oauth_error).__name__}: {_oauth_error}")
                                        except Exception:
                                            pass
                                else:
                                    # Não configurado, apenas limpar para não poluir URL
                                    try:
                                        st.query_params.clear()
                                    except Exception:
                                        pass
                            except Exception as _e:
                                try:
                                    st.query_params.clear()
                                except Exception:
                                    pass
                                st.error(f"Erro no fluxo OAuth: {_e}")
        except Exception:
            pass
        # ── FIM CALLBACK GLOBAL ──

        if st.session_state.get('user_authenticated', False):
            with st.sidebar:
                u_name = st.session_state.get('user_name', 'Admin')
                # Marca / logo — refinamento premium (mesma paleta #1E7A46, só proporção e espaçamento)
                st.markdown(
                    """<div style='display:flex;align-items:center;gap:14px;padding:6px 10px 18px;'>
                        <div style='width:48px;height:48px;border-radius:16px;flex-shrink:0;
                            background:linear-gradient(135deg,#ffffff42,#ffffff14);
                            border:1.5px solid rgba(255,255,255,0.38);
                            display:flex;align-items:center;justify-content:center;
                            font-size:23px;box-shadow:0 6px 16px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.22);'>🩺</div>
                        <div style='min-width:0;flex:1;'>
                            <div style='font-weight:800;font-size:1.06rem;color:#fff;line-height:1.15;letter-spacing:0.15px;white-space:nowrap;'>Gestão Clínica</div>
                            <div style='font-size:0.60rem;font-weight:700;letter-spacing:2.8px;text-transform:uppercase;
                                color:rgba(255,255,255,0.62);margin-top:3px;white-space:nowrap;'>MVP Psicologia</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True
                )
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
                    f"""<div style='background:rgba(255,255,255,0.13);border:1.5px solid rgba(255,255,255,0.20);
                    border-radius:18px 18px 0 0;padding:16px 16px 14px;margin-bottom:0;
                    display:flex;align-items:center;gap:14px;backdrop-filter:blur(12px);
                    box-shadow:0 8px 24px rgba(0,0,0,0.14), inset 0 1px 0 rgba(255,255,255,0.10);
                    transition: all 0.28s ease;'>
                        <div style='width:46px;height:46px;border-radius:50%;overflow:hidden;position:relative;
                            border:2.5px solid rgba(255,255,255,0.45);
                            box-shadow:0 3px 12px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.20);
                            display:flex;align-items:center;justify-content:center;
                            background:linear-gradient(135deg,rgba(255,255,255,0.18),rgba(255,255,255,0.08));flex-shrink:0;'>
                            {avatar_inner}
                            <div style='position:absolute;bottom:-1px;right:-1px;width:13px;height:13px;background:#8ee39a;border:2.5px solid rgba(255,255,255,0.95);border-radius:50%;box-shadow:0 2px 6px rgba(0,0,0,0.18);'></div>
                        </div>
                        <div style='min-width:0;flex:1;'>
                            <div style='font-weight:700;font-size:0.92rem;color:#fff;letter-spacing:0.15px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{u_name}</div>
                            <div style='font-size:0.70rem;color:rgba(255,255,255,0.62);letter-spacing:0.9px;text-transform:uppercase;font-weight:600;margin-top:2px;'>Administradora</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True
                )

                # Uploader acoplado ao mesmo card do perfil (mesma identidade visual #1E7A46)
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
                    """<div style='display:flex;align-items:center;gap:12px;margin:14px 10px 10px;'>
                        <div style='flex:1;height:1px;background:linear-gradient(to right, transparent, rgba(255,255,255,0.14), transparent);'></div>
                    </div>""",
                    unsafe_allow_html=True
                )

                pages = {
                    "⌂ Dashboard": "dashboard",
                    "⦿ Atendimentos & Pacientes": "appointments",
                    "📋 Docs Clínicos": "clinical_docs",
                    "📑 Laudos": "laudos",
                    "🛠️ Extras": "extras",
                    "☰ Relatórios": "reports",
                    "📝 Editor Docs": "docs_editor",
                    "↑ Upload": "upload",
                    "⚙ Configurações": "settings"
                }
                selected_page = st.radio("Selecione a página", list(pages.keys()), index=0, key='nav_radio', label_visibility="collapsed")
                page_key = pages[selected_page]

                st.divider()
                st.markdown(
                    """<div style='display:flex;align-items:center;gap:8px;margin:6px 0 10px 0;'>
                        <div style='width:30px;height:30px;border-radius:10px;flex-shrink:0;
                            background:linear-gradient(135deg,#4DA768,#4DA76899);
                            display:flex;align-items:center;justify-content:center;font-size:0.95rem;
                            box-shadow:0 4px 12px rgba(0,0,0,0.2);'>🤖</div>
                        <div style='font-weight:800;font-size:0.92rem;color:#fff;'>IA Assistente</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
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
                # Página de Pacientes removida — cadastro/atendimento gerencia pacientes
                pass
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