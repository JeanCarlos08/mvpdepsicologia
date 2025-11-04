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
import base64
# Observação: o carregamento de variáveis do .env é feito em db.py com fallback de encoding
# ...restante do arquivo permanece inalterado...

# Configurar página do Streamlit
st.set_page_config(
    page_title="JULIANA - Gestão Clínica",
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
            return False, "Nome do arquivo inválido"
        if not filename.lower().endswith('.pdf'):
            return False, "Apenas arquivos PDF são permitidos"
        if size_bytes > max_size_mb * 1024 * 1024:
            return False, f"Arquivo muito grande. Máximo: {max_size_mb}MB"
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
        /* Card dashboard degradê azul mais suave */
        .stMetric {
            background: linear-gradient(135deg, rgba(77,167,120,0.12) 0%, rgba(77,167,248,0.08) 60%, rgba(255,255,255,0.0) 100%);
            border-radius: 12px;
            padding: 14px 18px;
            box-shadow: 0 2px 12px rgba(44,62,80,0.07);
            margin-bottom: 10px;
            border: 1.5px solid #222;
            transition: box-shadow 0.2s;
        }
        /* Forçar todas as cores de texto dentro do card para branco (label, value, delta) */
        .stMetric, .stMetric * {
            color: #ffffff !important;
        }
        /* Garantir que a caption do dashboard / badge do DB também fiquem em branco */
        .stCaption, .stCaption span, .stCaption * {
            color: #ffffff !important;
        }
        span.db-badge, .db-badge {
            color: #ffffff !important;
        }
        /* Estilizar campos de formulário / área de autenticação para a paleta profissional */
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
        /* Para o formulário de autenticação, força texto preto e fundo claro para facilitar digitação
           Seletores específicos para a estrutura interna gerada pelo Streamlit */
        .auth-card input, .auth-card textarea,
        .auth-card .stTextInput>div>div>input, .auth-card .stTextArea>div>div>textarea,
        .auth-card .stTextInput>div>div>input[type="password"] {
            color: #000000 !important;
            background: #ffffff !important;
            border: 1px solid rgba(0,0,0,0.08) !important;
            caret-color: #000000 !important;
        }
    .auth-card .stTextInput>div>div>input::placeholder, .auth-card .stTextArea>div>div>textarea::placeholder { color: #888888 !important; }
        /* Reforço adicional para navegadores que usam -webkit-text-fill-color e seletores distintos */
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
        /* Forçar título dos cards para preto quando necessário */
        .card-title { color: #000000 !important; }
        .stTextInput>div>div>input::placeholder, .stTextArea>div>div>textarea::placeholder {
            color: #888888 !important; /* Placeholder: cinza */
        }
        /* Botão de login/ações com variação da paleta */
        .stButton > button {
            background: linear-gradient(90deg, #2196F3 0%, #00BFFF 100%); /* azul profissional */
            color: #ffffff !important;
            border-radius: 8px !important;
            padding: 8px 18px !important;
            font-weight: 700 !important;
        }
        .stButton > button:hover { opacity: 0.95; transform: translateY(-1px); }
        /* Small privacy/login area highlight removed (use AuthPage render instead) */
        /* seletores mais específicos caso alguma versão do streamlit use nomes diferentes */
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
    """Salva PDF no banco (BYTEA) e retorna um marcador 'db:<id>'.

    Compatibilidade: registros antigos que apontam para caminho no disco continuam funcionando.
    """
    if uploaded_file is None:
        return ""
    try:
        safe_name = security.generate_safe_filename(uploaded_file.name)
        file_bytes = uploaded_file.getvalue()
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
                d1 = st.date_input("Data inicial", value=None, key="flt_dini")
                d2 = st.date_input("Data final", value=None, key="flt_dfim")

            filters["q"] = q
            filters["modalidade_filter"] = None if mod_sel == "(Todas)" else mod_sel
            filters["status_filter"] = None if status_sel == "(Todos)" else status_sel
            filters["date_start"] = d1
            filters["date_end"] = d2
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

        st.markdown(
            "<h3 class='card-title' style='color:#000000 !important;'>📋 Lista de Atendimentos</h3>",
            unsafe_allow_html=True,
        )

        # Paginação simples
        total_rows = len(df)
        page_size = st.selectbox("Tamanho da página", [10, 20, 50, 100], index=1, key="pg_size")
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1, key="pg_num")
        start, end = (page - 1) * page_size, min(page * page_size, total_rows)
        page_df = df.iloc[start:end]

        df_display = page_df[["Empresa", "Nome", "Modalidade", "Data", "Hora", "Laudo", "Avaliação", "Status"]].copy()
        st.dataframe(df_display, use_container_width=True, height=360)

        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Exportar CSV (todos os filtrados)", data=csv_data, file_name="atendimentos_filtrados.csv", mime="text/csv")

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

        with st.expander("📎 Gerenciar por atendimento (visualizar/download/editar/status/exportar)", expanded=False):
            for row in page_rows:
                # Indices conforme colunas retornadas por listar_atendimentos
                aid = row[0]
                empresa = row[1]
                nome = row[2]
                laudo_ref = row[6]
                aval_ref = row[7]
                c1, c2, c3, c4, c5, c6, c7, c8, c9 = st.columns([3, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4])
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
                    with st.popover(f"⚙️ Status", use_container_width=True):
                        st.caption("Atualizar status")
                        for stx in ["Agendado", "Atendido", "Concluído", "Cancelado"]:
                            if st.button(stx, key=f"st_{stx}_{aid}"):
                                try:
                                    db.atualizar_status(aid, stx)
                                    st.success(f"Status atualizado para {stx}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao atualizar status: {e}")

                # Editor inline por atendimento
                if st.session_state.get(f"edit_open_{aid}"):
                    with st.expander(f"Editar atendimento #{aid}", expanded=True):
                        with st.form(f"form_edit_{aid}"):
                            colu1, colu2, colu3 = st.columns(3)
                            with colu1:
                                nv_empresa = st.text_input("Empresa", value=str(empresa))
                                nv_modal = st.selectbox("Modalidade", [m.value for m in ModalidadeAtendimento], index= [m.value for m in ModalidadeAtendimento].index(str(row[3])) if row[3] in [m.value for m in ModalidadeAtendimento] else 0)
                                nv_status = st.selectbox("Status", ["Agendado","Atendido","Concluído","Cancelado"], index=["Agendado","Atendido","Concluído","Cancelado"].index(str(row[8])) if row[8] in ["Agendado","Atendido","Concluído","Cancelado"] else 0)
                            with colu2:
                                nv_nome = st.text_input("Nome", value=str(nome))
                                try:
                                    cur_dt = pd.to_datetime(str(row[4]), dayfirst=True, errors="coerce").date()
                                except Exception:
                                    cur_dt = date.today()
                                nv_data = st.date_input("Data", value=cur_dt)
                            with colu3:
                                try:
                                    (hh,mm) = str(row[5]).split(":")[:2]
                                    cur_tm = time(int(hh), int(mm))
                                except Exception:
                                    cur_tm = time(8,0)
                                nv_hora = st.time_input("Hora", value=cur_tm)
                                nv_obs = st.text_area("Observações", value=str(row[9] or ""))
                            st.markdown("#### 📎 Anexos")
                            colaf1, colaf2 = st.columns(2)
                            with colaf1:
                                up_laudo_novo = st.file_uploader("Substituir Laudo (PDF)", type=["pdf"], key=f"up_laudo_edit_{aid}")
                            with colaf2:
                                up_aval_novo = st.file_uploader("Substituir Avaliação (PDF)", type=["pdf"], key=f"up_aval_edit_{aid}")
                            colbtn1, colbtn2, colbtn3 = st.columns([1.2,1,1])
                            with colbtn1:
                                s = st.form_submit_button("💾 Salvar alterações", type="primary")
                            with colbtn2:
                                cancel = st.form_submit_button("Cancelar")
                            with colbtn3:
                                exp_csv = st.form_submit_button("⬇️ Exportar CSV")
                            colbtn4, = st.columns(1)
                            with colbtn4:
                                exp_html = st.form_submit_button("🖨️ Exportar HTML (PDF via impressão)")
                            if s:
                                try:
                                    updates = {
                                        "empresa": nv_empresa,
                                        "nome": nv_nome,
                                        "modalidade": nv_modal,
                                        "data": nv_data.strftime(DATE_FORMAT) if nv_data else None,
                                        "hora": nv_hora.strftime(TIME_FORMAT) if nv_hora else None,
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
                                    st.success("Alterações salvas")
                                    st.session_state[f"edit_open_{aid}"] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar: {e}")
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
                                    csv_bytes = row_df.to_csv(index=False).encode("utf-8-sig")
                                    st.download_button("Baixar CSV do Atendimento", data=csv_bytes, file_name=f"atendimento_{aid}.csv", mime="text/csv", key=f"dl_csv_{aid}")
                                except Exception as e:
                                    st.error(f"Erro ao exportar CSV: {e}")
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

        # Forçar paleta visual apenas para a página de configurações
        # Injetar uma classe no <body> para escopo confiável dos estilos (override do estilo global)
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
                    st.warning(f"Falha ao coletar snapshot: {e}")
                try:
                    st.subheader("Diagnóstico do banco")
                    st.json(db.get_db_diagnostics())
                except Exception as e:
                    st.warning(f"Falha ao consultar diagnóstico: {e}")

        with col6:
            if st.button("⚡ Criar índices"):
                try:
                    db.ensure_indexes()
                    st.success("Índices criados/verificados!")
                except Exception as e:
                    st.error(f"Falha ao criar índices: {e}")

        st.markdown("### 🧾 Auditoria (últimos 100)")
        try:
            aud = db.listar_auditoria(100)
            if aud:
                st.dataframe(pd.DataFrame(aud), use_container_width=True, height=300)
            else:
                st.info("Sem registros de auditoria ainda.")
        except Exception as e:
            st.warning(f"Falha ao listar auditoria: {e}")

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
                    if saved_path.startswith("db:"):
                        st.success("Arquivo salvo no banco de dados.")
                    else:
                        st.success(f"Arquivo salvo em: {saved_path}")
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
                # Fallback seguro: se os Secrets não estiverem configurados, usar admin/admin123
                admin_user = os.getenv('APP_ADMIN_USER', 'admin').strip()
                admin_pass = os.getenv('APP_ADMIN_PASS', 'admin123').strip()
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
                // Evitar append se já estiver presente por outro processo concorrente
                if(!document.head.contains(style)){
                    document.head.appendChild(style);
                }
            } else {
                // Se existir mas não estiver no head, tentar anexar com segurança
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
                // Aplicado com sucesso – desconectar observer para evitar múltiplas alterações
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
                // adicionar listener para Enter -> clicar no botão Login (ignora textarea)
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
        # Inicialização do DB e temas (não bloquear a UI se o banco estiver offline)
        db_ok = False
        try:
            db_ok = DatabaseManager.initialize_database()
        except Exception:
            db_ok = False
        if not db_ok:
            st.warning("Banco de dados indisponível no momento. Você ainda pode fazer login e acessar Configurações; demais páginas exigem conexão.")
        # Autenticação: por padrão, EXIGE login. Para liberar sem login, defina APP_REQUIRE_AUTH=false nos Secrets.
        require_auth = os.getenv('APP_REQUIRE_AUTH', 'true').strip().lower() in ('1','true','yes')
        if not require_auth:
            # Considera usuário autenticado automaticamente
            if 'user_authenticated' not in st.session_state or not st.session_state['user_authenticated']:
                st.session_state['user_authenticated'] = True
                st.session_state['user_name'] = st.session_state.get('user_name', 'guest')
        apply_custom_css()
        apply_plotly_theme()
        with st.sidebar:
            st.markdown("## 🩺 JULIANA")
            st.markdown("*Gestão Clínica*")
            conn_status = "🟢 Conectado" if verificar_conexao() else "🔴 Desconectado"
            st.caption(f"Status: {conn_status}", unsafe_allow_html=True)
            # Logout rápido
            if 'user_authenticated' in st.session_state and st.session_state['user_authenticated']:
                st.write(f"Usuário: {st.session_state.get('user_name', '')}")
                if st.button('🚪 Logout'):
                    security.log_access('AUTH_LOGOUT', f"Usuário {st.session_state.get('user_name','')} deslogado")
                    st.session_state['user_authenticated'] = False
                    st.session_state['user_name'] = ''
                    # Reiniciar a interface; experimental_rerun pode não existir em algumas versões do Streamlit
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
            # Fornecer key única para evitar StreamlitDuplicateElementId em casos de re-render
            selected_page = st.radio("Navegação", list(pages.keys()), index=0, key='nav_radio')
            page_key = pages[selected_page]
        if page_key == "dashboard":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                DashboardPage.render()
        elif page_key == "appointments":
            if require_auth and not st.session_state.get('user_authenticated', False):
                AuthPage.render()
            else:
                AppointmentsPage.render({})
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
        try:
            st.divider()
        except Exception:
            st.markdown("---")
        conn_ok = verificar_conexao()
        if not conn_ok:
            with st.expander("Ajuda rápida: conexão com PostgreSQL", expanded=False):
                st.markdown(
                    "- Em produção (Streamlit Cloud): use um host público (Neon/Render/RDS) e defina Secrets: `DATABASE_URL=postgresql://usuario:senha@host:5432/gestao_clinica`\n"
                    "- Em desenvolvimento local (Windows): abra services.msc e inicie o serviço `postgresql-x64-18`\n"
                    "- Se o banco não existir, crie `gestao_clinica` no pgAdmin/psql\n"
                    "- Verifique usuário/senha e privilégios (pode usar um usuário app de menor privilégio)"
                )

if __name__ == "__main__":
    ClinicalManagementApp().run()