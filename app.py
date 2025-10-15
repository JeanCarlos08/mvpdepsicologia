import streamlit as st
import db
import pathlib
from datetime import datetime, date, time
from enum import Enum
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os
import streamlit.components.v1 as components
# Carrega .env automaticamente em tempo de execu├º├úo (se python-dotenv estiver instalado)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv ausente ou falha ao carregar ÔÇö continue normalmente (espera vari├íveis de ambiente do sistema)
    pass

# Fallback simples: se python-dotenv n├úo estiver presente e houver um arquivo .env na raiz,
# vamos carregar chaves b├ísicas (APP_ADMIN_USER/APP_ADMIN_PASS) para o ambiente.
def _fallback_load_dotenv(env_path: pathlib.Path | None = None) -> None:
    try:
        root = pathlib.Path(__file__).resolve().parent
        env_path = env_path or (root / '.env')
        if not env_path.exists():
            return
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # only set if not already present (treat empty string as unset)
                # algumas execu├º├Áes de Streamlit podem deixar a vari├ível definida mas vazia;
                # considerar isso como n├úo-configurada para permitir o fallback do .env
                if key and val and not os.getenv(key):
                    try:
                        os.environ[key] = val
                    except Exception:
                        # N├úo falhar a inicializa├º├úo por causa de problemas ao setar env
                        pass
    except Exception:
        # N├úo falhar na inicializa├º├úo por causa desse fallback
        pass

# Executar fallback imediatamente para garantir que vari├íveis definidas em .env sejam vis├¡veis
_fallback_load_dotenv()

# Configurar p├ígina do Streamlit
st.set_page_config(
    page_title="JULIANA - Gestão Clínica",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar esquema do banco (cria tabelas caso ainda n├úo existam)
try:
    db.create_tables_if_needed()
except Exception:
    # N├úo interromper a interface: DatabaseManager.initialize_database mant├®m a mesma responsabilidade
    pass

BASE_DIR = pathlib.Path(__file__).resolve().parent
DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M"
PRIMARY_ACCENT = "#4DA768"

class ModalidadeAtendimento(Enum):
    ADMISSIONAL = "Admissional"
    DEMISSIONAL = "Demissional"
    PERIODO = "Período"
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
            return False, "Nome do arquivo inv├ílido"
        if not filename.lower().endswith('.pdf'):
            return False, "Apenas arquivos PDF s├úo permitidos"
        if size_bytes > max_size_mb * 1024 * 1024:
            return False, f"Arquivo muito grande. M├íximo: {max_size_mb}MB"
        return True, "OK"
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
            st.error(f"Erro ao inicializar banco (DB): {e}")
            return False

    @staticmethod
    def get_all_appointments():
        try:
            return db.listar_atendimentos()
        except Exception as e:
            st.error(f"Erro ao buscar atendimentos: {e}")
            return []

    @staticmethod
    def add_appointment(appointment_data):
        try:
            db.inserir_atendimento(
                appointment_data.empresa,
                appointment_data.nome,
                appointment_data.modalidade,
                appointment_data.data,
                appointment_data.hora,
                appointment_data.laudo_pdf,
                appointment_data.avaliacao_pdf,
                getattr(appointment_data, 'observacoes', '')
            )
            return True
        except Exception as e:
            st.error(f"Erro ao adicionar atendimento: {e}")
            return False

    @staticmethod
    def delete_appointment(appointment_id):
        try:
            return db.excluir_atendimento(appointment_id)
        except Exception as e:
            st.error(f"Erro ao excluir atendimento: {e}")
            return False

    @staticmethod
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
    for i, card in enumerate(cards):
        with cols[i]:
            st.metric(
                label=f"{card.get('icon', '')} {card.get('title', '')}",
                value=card.get('value', ''),
                delta=card.get('delta', None)
            )

def render_page_header(title, subtitle, inverse=False):
    st.markdown(f"<h2 style='color: #fff; font-weight: 700;'>{title}</h2>", unsafe_allow_html=True)
    st.caption(f"<span style='color: #fff; font-size: 1.1em;'>{subtitle}</span>", unsafe_allow_html=True)

def apply_custom_css(dark_mode=False, advanced=False):
    st.markdown(
        '''<style>
    body, .main, .block-container {background-color: #73C883 !important;}
    .css-1d391kg, .css-1v0mbdj, .stSidebar, .sidebar-content {background: #4da768 !important; color: #fff !important;}
        .stSidebar .stButton > button, .stSidebar input, .stSidebar select {background: #fff !important; color: #4da768 !important; border-radius: 6px !important;}
        .css-1d391kg, .css-1v0mbdj, .stSidebar, .sidebar-content, .stRadio label, .stRadio div, .stRadio span {color: #fff !important;}
        .stDataFrame, .stTable, .stMarkdown table {background: #fff; border-radius: 10px; box-shadow: 0 2px 12px rgba(44,62,80,0.10); border: 1px solid #e1e8ed; margin-bottom: 18px; font-size: 15px;}
        .stMarkdown table th, .stMarkdown table td {padding: 8px 14px; border-bottom: 1px solid #e1e8ed;}
        .stMarkdown table th {background: #eafaf1; color: #2c3e50; font-weight: 700;}
        .stMarkdown table tr:hover td {background: #f7f9fa;}
        .stMarkdown table tr.important td {background: #ffeaa7 !important; color: #636e72 !important; font-weight: 600;}
        h1, h2, h3, h4 {color: #2c3e50; font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; font-weight: 700;}
        h3, .subtitle-highlight {color: #2c3e50 !important; background: linear-gradient(90deg, #eafaf1 0%, #73C883 100%); padding: 6px 18px; border-radius: 8px; font-size: 1.35em; font-weight: 700; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(44,62,80,0.07); display: inline-block;}
        .stButton > button {background: linear-gradient(90deg, #4DA768 0%, #2ecc71 100%); color: white; border-radius: 6px; border: none; font-weight: 600; padding: 8px 20px; box-shadow: 0 2px 8px rgba(60,170,95,0.08); transition: background 0.2s;}
        .stButton > button:hover {background: linear-gradient(90deg, #2ecc71 0%, #4DA768 100%);}
        /* Card dashboard degrad├¬ azul mais suave */
        .stMetric {
            background: linear-gradient(135deg, rgba(77,167,120,0.12) 0%, rgba(77,167,248,0.08) 60%, rgba(255,255,255,0.0) 100%);
            border-radius: 12px;
            padding: 14px 18px;
            box-shadow: 0 2px 12px rgba(44,62,80,0.07);
            margin-bottom: 10px;
            border: 1.5px solid #222;
            transition: box-shadow 0.2s;
        }
        /* For├ºar todas as cores de texto dentro do card para branco (label, value, delta) */
        .stMetric, .stMetric * {
            color: #ffffff !important;
        }
        /* Garantir que a caption do dashboard / badge do DB tamb├®m fiquem em branco */
        .stCaption, .stCaption span, .stCaption * {
            color: #ffffff !important;
        }
        span.db-badge, span.db-badge.sqlite, .db-badge, .db-badge.sqlite {
            color: #ffffff !important;
        }
        /* Estilizar campos de formul├írio / ├írea de autentica├º├úo para a paleta profissional */
        .stForm, .stForm .stTextInput, .stForm .stTextArea, .stForm .stSelectbox, .stForm .stDateInput, .stForm .stTimeInput {
            background: linear-gradient(180deg, rgba(0,191,255,0.04), rgba(77,167,248,0.02));
            border-radius: 10px;
            padding: 10px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div, .stDateInput>div>div>input, .stTimeInput>div>div>input {
            background: rgba(255,255,255,0.04) !important;
            color: #000000 !important; /* Texto digitado: preto */
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 6px !important;
            padding: 8px !important;
        }
        /* Para o formul├írio de autentica├º├úo, for├ºa texto preto e fundo claro para facilitar digita├º├úo
           Seletores espec├¡ficos para a estrutura interna gerada pelo Streamlit */
        .auth-card input, .auth-card textarea,
        .auth-card .stTextInput>div>div>input, .auth-card .stTextArea>div>div>textarea,
        .auth-card .stTextInput>div>div>input[type="password"] {
            color: #000000 !important;
            background: #ffffff !important;
            border: 1px solid rgba(0,0,0,0.08) !important;
            caret-color: #000000 !important;
        }
    .auth-card .stTextInput>div>div>input::placeholder, .auth-card .stTextArea>div>div>textarea::placeholder { color: #888888 !important; }
        /* Refor├ºo adicional para navegadores que usam -webkit-text-fill-color e seletores distintos */
        .auth-card :where(input, textarea) {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important; /* Safari/Chrome */
            background: #ffffff !important;
            caret-color: #000000 !important;
        }
        .auth-card input::placeholder, .auth-card textarea::placeholder { color: rgba(0,0,0,0.45) !important; }
        /* Labels e textos informativos dentro do card devem ser brancos para contraste com o tema */
        .auth-card .stTextInput>div>label, .auth-card .stForm label, .auth-card .stMarkdown, .auth-card div[data-testid='stCaption'] {
            color: #ffffff !important;
        }
        .stTextInput>div>label, .stForm label, .stCaption, .stMarkdown h2, .stMarkdown h3 {
            color: #ffffff !important;
        }
        /* For├ºar t├¡tulo dos cards para preto quando necess├írio */
        .card-title { color: #000000 !important; }
        .stTextInput>div>div>input::placeholder, .stTextArea>div>div>textarea::placeholder {
            color: #888888 !important; /* Placeholder: cinza */
        }
        /* Bot├úo de login/a├º├Áes com varia├º├úo da paleta */
        .stButton > button {
            background: linear-gradient(90deg, #2196F3 0%, #00BFFF 100%); /* azul profissional */
            color: #ffffff !important;
            border-radius: 8px !important;
            padding: 8px 18px !important;
            font-weight: 700 !important;
        }
        .stButton > button:hover { opacity: 0.95; transform: translateY(-1px); }
        /* Small privacy/login area highlight removed (use AuthPage render instead) */
        /* seletores mais espec├¡ficos caso alguma vers├úo do streamlit use nomes diferentes */
        .stMetric .stMetricValue, .stMetric .stMetricDelta, .stMetric .stMetricLabel {
            color: #ffffff !important;
        }
        .stMetric:hover {
            box-shadow: 0 4px 18px rgba(44,62,80,0.13);
            background: linear-gradient(135deg, rgba(77,167,248,0.16) 0%, rgba(255,255,255,0.0) 100%);
        }
        </style>''', unsafe_allow_html=True)

def apply_plotly_theme(dark_mode=False):
    pio.templates.default = "plotly_white"

def save_uploaded_pdf(uploaded_file):
    if uploaded_file is None:
        return ""
    try:
        uploads_dir = BASE_DIR / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        safe_name = security.generate_safe_filename(uploaded_file.name)
        file_path = uploads_dir / safe_name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return str(file_path)
    except Exception as e:
        st.error(f"Erro ao salvar PDF: {e}")
        return ""

def verificar_conexao():
    return db.verificar_conexao()

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
        render_page_header("🩺 JULIANA - Gestão Clínica", "Dashboard Executivo — Indicadores e métricas principais do sistema", inverse=True)
        conn_ok = verificar_conexao()
        st.caption(f"<span style='color: #fff; font-size: 1.1em;'>🗄️ Banco de Dados: {'Conectado' if conn_ok else 'Desconectado'} <span class='db-badge postgres'>Postgres</span></span>", unsafe_allow_html=True)
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
            st.error(f"Erro ao carregar estatísticas: {e}")
            total_appointments = total_empresas = laudos_enviados = avaliacoes_enviadas = 0
        cards = [
            {"icon": "📋", "title": "Atendimentos", "value": total_appointments, "acc": PRIMARY_ACCENT},
            {"icon": "🏢", "title": "Empresas", "value": total_empresas, "acc": PRIMARY_ACCENT},
            {"icon": "📄", "title": "Relatórios", "value": laudos_enviados, "acc": PRIMARY_ACCENT},
            {"icon": "📝", "title": "Avaliações", "value": avaliacoes_enviadas, "acc": PRIMARY_ACCENT},
        ]
        display_cards(cards)
        if not total_appointments:
            st.info("Sem dados ainda. Cadastre alguns atendimentos para visualizar o painel.")
        if stats.get("modalidades"):
            vals = list(stats["modalidades"].values())
            labels = list(stats["modalidades"].keys())
            fig = px.pie(values=vals, names=labels, title="Distribuição por Modalidade")
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(legend_title_text="Modalidade", height=420)
            st.plotly_chart(fig, use_container_width=True)

class AppointmentsPage:
    @staticmethod
    def render(filters):
        render_page_header("📅 Atendimentos", "Gerenciamento de Consultas e Procedimentos")
        with st.expander("➕ Cadastrar Novo Atendimento", expanded=False):
            with st.form("appointment_form_new", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    empresa = st.text_input("🏢 Empresa/Organização")
                    # Modalidades padronizadas (ignoramos outras entradas do DB)
                    modalidade = st.selectbox("🧾 Modalidade", [m.value for m in ModalidadeAtendimento])
                    data_sel = st.date_input("📅 Data", min_value=date.today())
                with col2:
                    nome = st.text_input("👤 Nome do Paciente")
                    hora_sel = st.time_input("⏰ Horário")
                st.markdown("#### 📎 Anexos (opcional)")
                c1a, c2a = st.columns(2)
                with c1a:
                    up_laudo = st.file_uploader("📄 Laudo PDF", type=["pdf"], key="up_laudo_new")
                    if up_laudo:
                        size_mb = len(up_laudo.getvalue()) / (1024 * 1024)
                        st.caption(f"Selecionado: {up_laudo.name} — {size_mb:.2f} MB")
                with c2a:
                    up_avaliacao = st.file_uploader("📝 Avaliação PDF", type=["pdf"], key="up_aval_new")
                    if up_avaliacao:
                        size_mb = len(up_avaliacao.getvalue()) / (1024 * 1024)
                        st.caption(f"Selecionado: {up_avaliacao.name} — {size_mb:.2f} MB")
                observacoes = st.text_area("🗒️ Observações", placeholder="Observações adicionais...")
                submitted = st.form_submit_button("💾 Salvar", type="primary")
                if submitted:
                    if not empresa or not nome:
                        st.error("Preencha os campos obrigatórios (Empresa e Nome).")
                    else:
                        laudo_path = save_uploaded_pdf(up_laudo)
                        avaliacao_path = save_uploaded_pdf(up_avaliacao)
                        novo_atendimento = AtendimentoData(
                            empresa=security.sanitize_input(empresa),
                            nome=security.sanitize_input(nome),
                            modalidade=modalidade,
                            data=data_sel.strftime(DATE_FORMAT),
                            hora=hora_sel.strftime(TIME_FORMAT),
                            laudo_pdf=laudo_path,
                            avaliacao_pdf=avaliacao_path,
                            observacoes=security.sanitize_input(observacoes)
                        )
                        if DatabaseManager.add_appointment(novo_atendimento):
                            security.log_access("ADD_APPOINTMENT", f"{nome} - {empresa}")
                            st.success("✅ Atendimento cadastrado!")
                            st.rerun()
                        else:
                            st.error("Erro ao cadastrar atendimento.")
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

        df["Laudo"] = df["Laudo PDF"].apply(lambda x: "SIM" if x else "NÃO")
        df["Avaliação"] = df["Avaliação PDF"].apply(lambda x: "SIM" if x else "NÃO")

        st.markdown(
            "<h3 class='card-title' style='color:#000000 !important;'>📋 Lista de Atendimentos</h3>",
            unsafe_allow_html=True,
        )

        df_display = df[["Empresa", "Nome", "Modalidade", "Data", "Hora", "Laudo", "Avaliação", "Status"]].copy()
        st.dataframe(df_display, use_container_width=True, height=400)

        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Exportar CSV", data=csv_data, file_name="atendimentos.csv", mime="text/csv")

class SettingsPage:
    @staticmethod
    def render() -> None:
        render_page_header("⚙️ Configurações", "Administração do Sistema")

        # For├ºar paleta visual apenas para a p├ígina de configura├º├Áes
        # Injetar uma classe no <body> para escopo confi├ível dos estilos (override do estilo global)
        try:
            components.html(
                """<script>try{document.body.classList.add('page-settings');}catch(e){};</script>""",
                height=0,
            )
        except Exception:
            pass

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
    background: #f6fbf7 !important; /* tom suave compat├¡vel */
    border-radius: 8px !important;
    color: #4DA768 !important;
}
.page-settings .stSuccess, .page-settings .stSuccess>div { background: rgba(77,167,120,0.08) !important; color: #4DA768 !important; }
.page-settings .stError, .page-settings .stError>div { background: rgba(223,50,80,0.06) !important; }
/* Garantir que os cards tamb├®m usem hover verde dentro da p├ígina de configura├º├Áes */
.page-settings .stMetric:hover {
    box-shadow: 0 4px 18px rgba(44,62,80,0.13) !important;
    background: linear-gradient(135deg, rgba(77,167,120,0.12) 0%, rgba(255,255,255,0.0) 100%) !important;
}
</style>
""",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='settings-page page-settings' style='padding:6px;border-radius:6px;'>",
            unsafe_allow_html=True,
        )

        conn_ok = verificar_conexao()
        stats = DatabaseManager.get_statistics()
        cards = [
            {"icon": "🗄️", "title": "Banco de Dados", "value": "Conectado" if conn_ok else "Offline"},
            {"icon": "🐘", "title": "Postgres", "value": "Ativo"},
            {"icon": "📋", "title": "Atendimentos", "value": stats.get("total_atendimentos", 0)},
        ]

        display_cards(cards)

        col1, col2, col3, col4 = st.columns(4)

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

        st.markdown("</div>", unsafe_allow_html=True)

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
            fig = px.bar(x=modal_counts.index, y=modal_counts.values, title="Atendimentos por Modalidade")
            fig.update_layout(xaxis_title="Modalidade", yaxis_title="Quantidade", height=400)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("### ⬇️ Exportar Relatório")
        if formato == "CSV":
            csv_data = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Baixar CSV", data=csv_data, file_name="relatorio_atendimentos.csv", mime="text/csv")

class UploadPage:
    @staticmethod
    def render() -> None:
        render_page_header("📤 Upload de Arquivos", "Gerencie arquivos PDF")
        uploaded_file = st.file_uploader("Escolha um arquivo PDF", type=["pdf"])
        if uploaded_file:
            size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            st.info(f"Arquivo: {uploaded_file.name} — {size_mb:.2f} MB")
            if st.button("Salvar Arquivo", type="primary"):
                saved_path = save_uploaded_pdf(uploaded_file)
                if saved_path:
                    st.success(f"Arquivo salvo em: {saved_path}")
        st.markdown("### 📁 Arquivos Salvos")
        uploads_dir = BASE_DIR / "uploads"
        if uploads_dir.exists():
            pdf_files = list(uploads_dir.glob("*.pdf"))
            if pdf_files:
                for pdf_file in pdf_files:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        size_kb = pdf_file.stat().st_size // 1024
                        st.write(f"📄 {pdf_file.name} ({size_kb} KB)")
                    with col2:
                        with open(pdf_file, 'rb') as f:
                            st.download_button(
                                "Baixar", 
                                data=f.read(), 
                                file_name=pdf_file.name,
                                key=f"download_{pdf_file.name}"
                            )
            else:
                st.info("Nenhum arquivo encontrado.")
        else:
            st.info("Diretório de uploads não existe ainda.")


class AuthPage:
    @staticmethod
    def render():
        """Renderiza a página de autenticação — não força bloqueio, apenas oferece formulário."""
        render_page_header("🔒 Autenticação", "Área de login (opcional)")
        st.markdown(
            "<div style='color: #ffffff;'>Use as variáveis de ambiente <code>APP_ADMIN_USER</code> e <code>APP_ADMIN_PASS</code> para configurar credenciais.</div>",
            unsafe_allow_html=True,
        )
        # Formulário que grava autenticação em session_state
        if 'user_authenticated' not in st.session_state:
            st.session_state['user_authenticated'] = False
        if 'user_name' not in st.session_state:
            st.session_state['user_name'] = ''

        st.markdown("<div class='auth-card' style='padding:10px;border-radius:8px;'>", unsafe_allow_html=True)
        with st.form('auth_form'):
            user = st.text_input('Usuário')
            pwd = st.text_input('Senha', type='password')
            submitted = st.form_submit_button('Entrar', type='primary')

            if submitted:
                admin_user = os.getenv('APP_ADMIN_USER', '').strip()
                admin_pass = os.getenv('APP_ADMIN_PASS', '').strip()
                if admin_user and admin_pass:
                    if user == admin_user and pwd == admin_pass:
                        st.session_state['user_authenticated'] = True
                        st.session_state['user_name'] = user
                        security.log_access('AUTH_LOGIN', f'Usuário {user} autenticado via AuthPage')
                        st.success('Login bem-sucedido — você será redirecionado.')
                        # Reload imediato para refletir estado
                        try:
                            components.html('<script>window.location.reload();</script>', height=0)
                        except Exception:
                            try:
                                rerun = getattr(st, 'experimental_rerun', None)
                                if callable(rerun):
                                    rerun()
                                else:
                                    raise AttributeError('experimental_rerun ausente')
                            except Exception:
                                try:
                                    st.stop()
                                except Exception:
                                    pass
                    else:
                        st.error('Credenciais inválidas')
                        security.log_access('AUTH_FAIL', f'Tentativa falha via AuthPage: {user}')
                else:
                    st.warning('Credenciais de administrador não configuradas — sistema em modo aberto.')
        st.markdown("</div>", unsafe_allow_html=True)
        # Injetar JS via components para garantir estilo nos inputs do auth-card
        js = r"""
<script>
(function(){
    try{
        function applyAuthStyles(wrap){
            if(!wrap) return;
            const inputs = wrap.querySelectorAll('input, textarea');
            inputs.forEach(i=>{
                try{
                    i.style.setProperty('color', '#000000', 'important');
                    i.style.setProperty('background', '#ffffff', 'important');
                    i.style.setProperty('caret-color', '#000000', 'important');
                    i.style.setProperty('-webkit-text-fill-color', '#000000', 'important');
                    i.style.setProperty('border', '1px solid rgba(0,0,0,0.08)', 'important');
                }catch(e){}
            });
            let style = document.getElementById('auth-card-placeholder-style');
            if(!style){
                style = document.createElement('style');
                style.id = 'auth-card-placeholder-style';
                style.innerHTML = '.auth-card input::placeholder, .auth-card textarea::placeholder{ color: rgba(0,0,0,0.45) !important; }';
                // Evitar append se j├í estiver presente por outro processo concorrente
                if(!document.head.contains(style)){
                    document.head.appendChild(style);
                }
            } else {
                // Se existir mas n├úo estiver no head, tentar anexar com seguran├ºa
                if(!document.head.contains(style)){
                    try{
                        document.head.appendChild(style);
                    }catch(e){/* ignore */}
                }
            }
        }

        const observer = new MutationObserver(function(mutations){
            const wrap = document.querySelector('.auth-card');
            if(wrap){
                applyAuthStyles(wrap);
                // Aplicado com sucesso ÔÇö desconectar observer para evitar m├║ltiplas altera├º├Áes
                try{ observer.disconnect(); }catch(e){}
                try{ if(typeof intervalId !== 'undefined') clearInterval(intervalId); }catch(e){}
            }
        });
        try{ observer.observe(document.body, { childList: true, subtree: true }); }catch(e){}

        // Apply once now
        const wrapNow = document.querySelector('.auth-card');
        if(wrapNow){
            applyAuthStyles(wrapNow);
            try{ observer.disconnect(); }catch(e){}
        }
        // Fallback: reaplicar por alguns ciclos e adicionar listener para Enter
        let tries = 0; const maxTries = 6;
        const intervalId = setInterval(()=>{
            const w = document.querySelector('.auth-card');
            if(w){
                applyAuthStyles(w);
                try{ clearInterval(intervalId); }catch(e){}
                // adicionar listener para Enter -> clicar no bot├úo Login (ignora textarea)
                try{
                    w.addEventListener('keydown', function(ev){
                        if(ev.key === 'Enter' && ev.target && ev.target.tagName !== 'TEXTAREA'){
                            const btn = w.querySelector('button');
                            if(btn){ btn.click(); ev.preventDefault(); }
                        }
                    });
                }catch(e){}
            }
            tries++;
            if(tries>=maxTries) try{ clearInterval(intervalId); }catch(e){}
        }, 300);

    }catch(e){console.log(e)}
})();
</script>
"""
        try:
            components.html(js, height=10)
        except Exception:
            # fallback silencioso se components não puder executar
            pass

class ClinicalManagementApp:
    def __init__(self):
        pass
    def run(self):
        # Inicializa├º├úo do DB e temas
        if not DatabaseManager.initialize_database():
            st.error("Erro ao inicializar banco de dados.")
            st.stop()
        apply_custom_css()
        apply_plotly_theme()
        with st.sidebar:
            st.markdown("## 🩺 JULIANA")
            st.markdown("*Gestão Clínica*")
            conn_status = "🟢 Conectado" if verificar_conexao() else "🔴 Desconectado"
            st.caption(f"Status: {conn_status}", unsafe_allow_html=True)
            # Logout r├ípido
            if 'user_authenticated' in st.session_state and st.session_state['user_authenticated']:
                st.write(f"Usuário: {st.session_state.get('user_name', '')}")
                if st.button('🚪 Logout'):
                    security.log_access('AUTH_LOGOUT', f"Usuário {st.session_state.get('user_name','')} deslogado")
                    st.session_state['user_authenticated'] = False
                    st.session_state['user_name'] = ''
                    # Reiniciar a interface; experimental_rerun pode n├úo existir em algumas vers├Áes do Streamlit
                    try:
                        rerun = getattr(st, 'experimental_rerun', None)
                        if callable(rerun):
                            rerun()
                        else:
                            raise AttributeError('experimental_rerun ausente')
                    except Exception:
                        try:
                            st.stop()
                        except Exception:
                            pass
            pages = {
                "🏠 Dashboard": "dashboard",
                "📅 Atendimentos": "appointments",
                "📊 Relatórios": "reports",
                "📤 Upload": "upload",
                "⚙️ Configurações": "settings"
            }
            # Fornecer key ├║nica para evitar StreamlitDuplicateElementId em casos de re-render
            selected_page = st.radio("Navegação", list(pages.keys()), index=0, key='nav_radio')
            page_key = pages[selected_page]
        if page_key == "dashboard":
            # Prote├º├úo: redireciona para AuthPage se n├úo autenticado
            if not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                DashboardPage.render()
        elif page_key == "appointments":
            if not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                AppointmentsPage.render({})
        elif page_key == "reports":
            if not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                ReportsPage.render()
        elif page_key == "upload":
            if not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                UploadPage.render()
        elif page_key == "settings":
            if not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                SettingsPage.render()

if __name__ == "__main__":
    ClinicalManagementApp().run()
