import streamlit as st
import streamlit.components.v1 as components
import db
import os
import base64
import pathlib
import urllib.parse
from datetime import datetime, date, time
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
    def initialize_database():
        try:
            # Cria tabelas no Postgres conforme metadata do db.py
            db.create_tables_if_needed()
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
        
        /* ── BASE ── */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
        [data-testid="stMainViewContainer"] {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            background-color: {bg_main} !important;
        }}
        * {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}

        /* ── CONTAINER ── */
        .main .block-container {{
            padding-top: 1.8rem;
            max-width: 1280px;
        }}

        /* ── SIDEBAR ── */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {bg_sidebar} 0%, {bg_sidebar}cc 100%) !important;
            box-shadow: 6px 0 24px rgba(0,0,0,0.15);
            border-right: 1px solid rgba(255,255,255,0.1);
        }}
        [data-testid="stSidebar"] * {{ color: #ffffff !important; }}
        [data-testid="stSidebar"] .stRadio label {{
            font-weight: 500 !important;
            font-size: 0.92rem !important;
            letter-spacing: 0.2px !important;
            padding: 2px 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stTextInput"] input {{
            background: rgba(255,255,255,0.12) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            border-radius: 10px !important;
            color: #ffffff !important;
            font-size: 0.88rem !important;
        }}

        /* ── TÍTULOS ── */
        h1 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 800 !important;
            font-size: 2rem !important;
            letter-spacing: -0.8px !important;
            background: linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.75) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        h2, h3 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 700 !important;
            color: #ffffff !important;
            letter-spacing: -0.4px;
        }}
        h4, h5, h6 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 600 !important;
            color: rgba(255,255,255,0.9) !important;
        }}
        p, span, div, label {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }}

        /* ── CARDS DE MÉTRICAS ── */
        [data-testid="stMetric"] {{
            background: {card_bg} !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.22);
            border-radius: 20px !important;
            padding: 22px 24px !important;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.15) !important;
            transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-5px) scale(1.01);
            border-color: rgba(255,255,255,0.4);
            box-shadow: 0 16px 48px rgba(0,0,0,0.14), inset 0 1px 0 rgba(255,255,255,0.2) !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: {card_text_color} !important;
            font-weight: 600 !important;
            font-size: 0.72rem !important;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            opacity: 0.8;
        }}
        [data-testid="stMetricValue"] {{
            color: {card_text_color} !important;
            font-weight: 800 !important;
            font-size: 2rem !important;
            letter-spacing: -1px;
        }}
        [data-testid="stMetricDelta"] {{ color: {card_text_color} !important; }}

        /* ── TABELAS ── */
        .stDataFrame, [data-testid="stTable"] {{
            background: {"#1e1e1e" if dark_mode else "white"};
            border-radius: 16px;
            overflow: hidden;
            border: none;
            box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        }}

        /* ── INPUTS ── */
        .stTextInput input, .stSelectbox select, .stTextArea textarea, .stDateInput input {{
            border-radius: 12px !important;
            border: 1.5px solid rgba(255,255,255,0.2) !important;
            padding: 10px 16px !important;
            background: rgba(255,255,255,{0.08 if dark_mode else 0.92}) !important;
            color: {"white" if dark_mode else "#1a1a1a"} !important;
            font-size: 0.92rem !important;
            font-weight: 500 !important;
            transition: border-color 0.2s ease !important;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus {{
            border-color: {primary_accent} !important;
            box-shadow: 0 0 0 3px {primary_accent}33 !important;
        }}

        /* ── STATUS BADGES ── */
        .status-badge {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 50px;
            font-size: 0.72rem;
            font-weight: 700;
            color: white !important;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}
        .status-agendado {{ background: linear-gradient(90deg,#3498db,#2980b9); }}
        .status-atendido {{ background: linear-gradient(90deg,#2ecc71,#27ae60); }}
        .status-concluido {{ background: linear-gradient(90deg,#1e8449,#145a32); }}
        .status-cancelado {{ background: linear-gradient(90deg,#e74c3c,#c0392b); }}

        /* ── BOTÕES ── */
        .stButton > button {{
            width: 100%;
            border-radius: 12px !important;
            background: linear-gradient(135deg, {primary_accent} 0%, {primary_accent}bb 100%) !important;
            color: white !important;
            font-weight: 700 !important;
            font-size: 0.88rem !important;
            letter-spacing: 0.3px !important;
            padding: 10px 24px !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px) scale(1.01) !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.18) !important;
            border-color: rgba(255,255,255,0.3) !important;
        }}
        .stButton > button:active {{ transform: translateY(0px) scale(0.99) !important; }}

        /* ── EXPANDER ── */
        .stExpander {{
            border: 1px solid rgba(255,255,255,0.12) !important;
            background: rgba(255,255,255,0.08) !important;
            border-radius: 16px !important;
            backdrop-filter: blur(8px);
            margin-bottom: 1rem !important;
        }}
        .stExpander > div > div > div > div > p {{
            font-weight: 600 !important;
            font-size: 0.9rem !important;
        }}
        .stExpander * {{ color: white !important; }}

        /* ── DIVIDER ── */
        hr {{
            border-color: rgba(255,255,255,0.15) !important;
            margin: 1.2rem 0 !important;
        }}

        /* ── ALERTS / INFO ── */
        [data-testid="stAlert"] {{
            border-radius: 14px !important;
            border: none !important;
            backdrop-filter: blur(8px);
        }}

        /* ── SCROLLBAR ── */
        ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
        ::-webkit-scrollbar-track {{ background: rgba(0,0,0,0.05); border-radius: 10px; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.25); border-radius: 10px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,0.5); }}

        /* ── LOGIN ── */
        [data-testid="stForm"] {{
            background: rgba(255,255,255,0.07) !important;
            border: 1px solid rgba(255,255,255,0.16) !important;
            border-radius: 24px !important;
            padding: 2.5rem !important;
            backdrop-filter: blur(24px) !important;
            box-shadow: 0 20px 60px rgba(0,0,0,0.12) !important;
        }}
        [data-testid="stFormSubmitButton"] button {{
            background: linear-gradient(135deg, {primary_accent} 0%, {primary_accent}99 100%) !important;
            color: white !important;
            border-radius: 14px !important;
            font-size: 1rem !important;
            font-weight: 700 !important;
            padding: 0.7rem 2rem !important;
            border: none !important;
            box-shadow: 0 6px 24px rgba(77,167,104,0.35) !important;
            letter-spacing: 0.3px !important;
            transition: all 0.3s ease !important;
        }}
        [data-testid="stFormSubmitButton"] button:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 10px 32px rgba(77,167,104,0.5) !important;
        }}

        /* ── CAPTION / SMALL TEXT ── */
        .stCaption, [data-testid="stCaptionContainer"] {{
            font-size: 0.78rem !important;
            opacity: 0.72;
            letter-spacing: 0.1px;
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
            background: rgba(255,255,255,0.1) !important;
            border: 1px solid rgba(255,255,255,0.22) !important;
            border-radius: 10px !important;
            color: rgba(255,255,255,0.85) !important;
            font-size: 0.78rem !important;
            font-weight: 600 !important;
            padding: 7px 12px !important;
            letter-spacing: 0.3px !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
            margin: 0 !important;
        }}
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] > button:hover {{
            background: rgba(255,255,255,0.2) !important;
            border-color: rgba(255,255,255,0.4) !important;
            color: #fff !important;
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
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, 'Relatório de Atendimentos', 0, 1, 'C')
            self.ln(5)
            self.set_font('Arial', 'I', 10)
            self.cell(0, 10, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF('L', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    # Columns to export
    cols = ["Empresa", "Nome", "Modalidade", "Data", "Hora", "Status"]
    
    # Column widths adjusted for A4 Landscape (~277mm usable width)
    # Total width: 70 + 70 + 45 + 25+ 22 + 40 = 272
    widths = [70, 70, 45, 25, 22, 40] 

    # Header
    pdf.set_font("Arial", 'B', 10)
    for i, col in enumerate(cols):
        pdf.cell(widths[i], 10, col, 1, 0, 'C')
    pdf.ln()

    # Rows — font size 8 for data to ensure text fits inside fixed-width columns
    pdf.set_font("Arial", size=8)
    
    def safe_cell_text(text):
        try:
            return str(text).encode('latin-1', 'replace').decode('latin-1')
        except:
            return str(text)

    for index, row in df.iterrows():
        try:
            # Fixed width cells with safe truncation (28 chars max for 70mm at 8pt)
            empresa_txt = safe_cell_text(str(row['Empresa']).strip()[:28])
            nome_txt = safe_cell_text(str(row['Nome']).strip()[:28])
            modal_txt = safe_cell_text(str(row['Modalidade']).strip()[:20])
            data_txt = safe_cell_text(str(row['Data']).strip())
            hora_txt = safe_cell_text(str(row['Hora']).strip())
            status_txt = safe_cell_text(str(row['Status']).strip())

            pdf.cell(widths[0], 8, empresa_txt, 1, 0, 'L')
            pdf.cell(widths[1], 8, nome_txt, 1, 0, 'L')
            pdf.cell(widths[2], 8, modal_txt, 1, 0, 'L')
            pdf.cell(widths[3], 8, data_txt, 1, 0, 'C')
            pdf.cell(widths[4], 8, hora_txt, 1, 0, 'C')
            pdf.cell(widths[5], 8, status_txt, 1, 0, 'C')
            pdf.ln()
                
        except Exception:
            pass

    return pdf.output()

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
        render_page_header("🩺 Gestão Clínica", "Dashboard Executivo — Indicadores e métricas principais do sistema", inverse=True)
        conn_ok = verificar_conexao()
        st.info(f"🗄️ Status do Sistema: {'Conectado ao Postgres' if conn_ok else 'Desconectado'}")
        st.caption("PostgreSQL | IA Assistente | Gestão Clínica")
        st.divider()
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
            st.info("✨ Painel vazio. Cadastre seu primeiro atendimento para ver a mágica acontecer!")
        
        if stats.get("modalidades") and total_appointments > 0:
            vals = list(stats["modalidades"].values())
            labels = list(stats["modalidades"].keys())
            fig = px.pie(values=vals, names=labels, title="Distribuição por Modalidade", 
                         color_discrete_sequence=['#1E5631', '#2D7D32', '#388E3C', '#43A047', '#4CAF50'])
            fig.update_traces(textposition="inside", textinfo="percent+label", marker=dict(line=dict(color='rgba(255,255,255,0.2)', width=2)))
            fig.update_layout(legend_title_text="Modalidade", height=420, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)

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
            with st.form("appointment_form_new", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    empresa = st.text_input("🏢 Empresa/Organização", max_chars=100).strip()
                    # Modalidades padronizadas (ignoramos outras entradas do DB)
                    modalidade = st.selectbox("🧾 Modalidade", [m.value for m in ModalidadeAtendimento])
                    data_sel = st.date_input("📅 Data", value=date.today(), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
                with col2:
                    nome = st.text_input("👤 Nome do Paciente", max_chars=100).strip()
                    hora_sel = st.time_input("⏰ Horário")
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
                observacoes = st.text_area("🗒️ Observações", value=initial_obs, placeholder="Observações adicionais ou notas da IA...")
                
                c_act1, c_act2 = st.columns([1, 1])
                with c_act1:
                    submitted = st.form_submit_button("💾 Salvar", type="primary")
                with c_act2:
                    if st.form_submit_button("🧹 Limpar Notas IA"):
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
                                data=data_sel, # Passar objeto date diretamente
                                hora=hora_sel, # Passar objeto time diretamente
                                laudo_pdf=laudo_path,
                                avaliacao_pdf=avaliacao_path,
                                observacoes=security.sanitize_input(observacoes)
                            )
                            if DatabaseManager.add_appointment(novo_atendimento):
                                security.log_access("ADD_APPOINTMENT", f"{nome} - {empresa}")
                                
                                st.toast("Atendimento cadastrado com sucesso!", icon="✅")
                                # Limpar notas IA após sucesso
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
                    st.warning("Nenhum atendimento encontrado para essa busca.")
                else:
                    st.success(f"{len(resultados)} atendimento(s) encontrado(s).")
                    for r_edit in resultados:
                        aid_e = r_edit[0]
                        lbl = f"#{aid_e} — {r_edit[2]} | {r_edit[1]} | {r_edit[3]}"
                        with st.container(border=True):
                            st.markdown(f"**{lbl}**")
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
            st.info("Nenhum atendimento encontrado.")
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
                st.info("Nenhum atendimento na tabela.")


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
            st.session_state['accent_color'] = '#4DA768'
            st.session_state['card_text_color'] = '#ffffff'
            st.session_state['main_bg_color'] = '#73C883'
            st.session_state['card_bg_hex'] = '#ffffff'
            st.session_state['premium_dark_mode'] = False
            # Limpar do banco
            for key in ['accent_color', 'card_text_color', 'main_bg_color', 'card_bg_hex', 'premium_dark_mode']:
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
                if DatabaseManager.initialize_database():
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

class ReportsPage:
    @staticmethod
    def render() -> None:
        render_page_header("📊 Relatórios", "Análises e Exportações")
        col1, col2 = st.columns(2)
        with col1:
            periodo = st.selectbox("Período", ["Últimos 7 dias", "Últimos 30 dias", "Ano atual", "Tudo"])
        with col2:
            formato = st.selectbox("Formato", ["CSV", "Excel"])
        appointments = DatabaseManager.get_all_appointments()
        if not appointments:
            st.info("Sem dados para relatório.")
            return
        df = pd.DataFrame(appointments, columns=[
            "ID", "Empresa", "Nome", "Modalidade", "Data", "Hora",
            "Laudo PDF", "Avaliação PDF", "Status", "Observações"
        ])
        st.markdown("### 🧾 Resumo")
        total_atendimentos = len(df)
        total_empresas = df["Empresa"].nunique()
        total_modalidades = df["Modalidade"].nunique()
        cards = [
            {"icon": "📋", "title": "Total Atendimentos", "value": total_atendimentos},
            {"icon": "🏢", "title": "Empresas", "value": total_empresas},
            {"icon": "🧾", "title": "Modalidades", "value": total_modalidades},
        ]
        display_cards(cards)
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

        # Layout centralizado e minimalista
        _, col_center, _ = st.columns([1, 1.4, 1])

        with col_center:
            st.markdown("## Gestão Clínica")
            st.caption("Portal Administrativo")
            st.markdown("")

            with st.form('auth_form', clear_on_submit=False):
                user = st.text_input('Usuário', placeholder='Digite seu usuário...')
                pwd = st.text_input('Senha', type='password', placeholder='Digite sua senha...')
                st.markdown("")
                submitted = st.form_submit_button('Entrar', type='primary', use_container_width=True)

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

            st.caption(f"🔒 Acesso seguro  •  Tentativas: {st.session_state['login_attempts']}/5")

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
                    "⦿ Atendimentos": "appointments",
                    "☰ Relatórios": "reports",
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