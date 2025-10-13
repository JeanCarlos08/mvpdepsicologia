from __future__ import annotations
import sys
import os
from pathlib import Path

# Configurar encoding para Windows ANTES de qualquer import
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PGCLIENTENCODING'] = 'UTF8'

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, time
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

from core import services, security
import db_unified as db

ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="JULIANA - Gestão Clínica", page_icon="🩺", layout="wide")

# ==================== AUTENTICAÇÃO ====================
def check_authentication():
    """Verifica se o usuário está autenticado."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

def login_page():
    """Página de login."""
    # CSS leve para refletir o tema padrão do projeto (ver .streamlit/config.toml)
    st.markdown(
        """
        <style>
        :root { --brand:#4DA768; --bg:#ffffff; --bg2:#f0f2f6; --text:#262730; }
        .login-hero { background: var(--brand); color:#fff; padding: 12px 16px; border-radius: 10px; margin-bottom: 16px; }
        .login-card { background: var(--bg2); padding: 24px; border-radius: 12px; border: 1px solid #e6e6e6; }
        .login-note { color:#59636e; font-size: 0.9rem; }
        .stButton>button, .stForm [data-testid="baseButton-secondary"] { background: var(--brand) !important; color:#fff !important; border: 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='login-hero'>🔐 JULIANA - Gestão Clínica</div>", unsafe_allow_html=True)
    st.subheader("Faça login para continuar")
    
    with st.form("login_form"):
        username = st.text_input("Usuário", placeholder="Digite seu usuário")
        password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submit = st.form_submit_button("Entrar", use_container_width=True, type="primary")
        
        if submit:
            # Credenciais fixas do .env
            correct_user = os.getenv("APP_ADMIN_USER", "admin")
            correct_pass = os.getenv("APP_ADMIN_PASS", "admin123")
            
            if username == correct_user and password == correct_pass:
                st.session_state.authenticated = True
                security.log_access("LOGIN_SUCCESS", f"user={username}")
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                security.log_access("LOGIN_FAILED", f"user={username}")
                st.error("❌ Usuário ou senha incorretos!")
    
    st.markdown("<div class='login-card login-note'>💡 <b>Credenciais padrão</b>: Usuário: <code>admin</code> | Senha: <code>admin123</code></div>", unsafe_allow_html=True)

def logout():
    """Realiza logout do usuário."""
    st.session_state.authenticated = False
    security.log_access("LOGOUT", "user=admin")
    st.rerun()

# Verificar autenticação
if not check_authentication():
    login_page()
    st.stop()

# ==================== APLICAÇÃO PRINCIPAL ====================

def save_uploaded_pdf(uploaded_file) -> str:
    """Salva o arquivo PDF no diretório de uploads."""
    if not uploaded_file:
        return ""
    try:
        # Gerar nome seguro
        safe_name = security.generate_safe_filename(uploaded_file.name)
        file_path = UPLOADS_DIR / safe_name
        
        # Salvar arquivo
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        security.log_access("FILE_UPLOAD", f"file={safe_name}")
        return str(file_path)
    except Exception as e:
        security.log_access("FILE_UPLOAD_ERROR", f"error={str(e)}")
        return ""

# Cabeçalho com botão de logout
col1, col2 = st.columns([6, 1])
with col1:
    st.title("JULIANA - Gestão Clínica (MVP)")
with col2:
    if st.button("🚪 Sair", use_container_width=True):
        logout()

# Tentar conectar ao banco sem bloquear a inicialização
db_ok = False
try:
    db_ok = db.ping_db()
except Exception as e:
    st.warning(f"⚠️ Aviso: Não foi possível conectar ao PostgreSQL. O sistema iniciará em modo limitado.")
    st.info("""
    **Para ativar o banco de dados:**
    1. Abra o pgAdmin e crie o banco: `CREATE DATABASE gestao_clinica;`
    2. Verifique se o PostgreSQL está rodando (services.msc → postgresql-x64-18)
    3. Confirme as credenciais no arquivo `.env`
    """)

st.caption(f"🔌 Banco: Postgres | Conexão: {'✅ OK' if db_ok else '⚠️ Desconectado'} | 👤 Usuário: admin")

cc1, cc2 = st.columns([6,1])
with cc2:
    if st.button("🔄 Re-testar", use_container_width=True):
        st.rerun()

tab1, tab2, tab3 = st.tabs(["📝 Novo atendimento", "📋 Atendimentos", "⚠️ Pendências"])

with tab1:
    st.subheader("📝 Criar novo atendimento")
    
    if not db_ok:
        st.warning("⚠️ Banco de dados não conectado. Não é possível criar atendimentos.")
        st.stop()
    
    with st.form("form_novo"):
        col1, col2, col3 = st.columns(3)
        with col1:
            empresa = st.text_input("🏢 Empresa *", "", help="Nome da empresa/convênio")
            nome = st.text_input("👤 Nome do paciente *", "", help="Nome completo do paciente")
        with col2:
            modalidade = st.text_input("🏥 Modalidade *", "", help="Ex: Consulta, Exame, Cirurgia")
            data_v = st.date_input("📅 Data *", value=date.today())
        with col3:
            hora_v = st.time_input("🕐 Hora *", value=time(9, 0))
            observacoes = st.text_area("📝 Observações", "", help="Informações adicionais (opcional)")

        st.markdown("---")
        st.markdown("**📎 Anexos (opcional)**")
        c1, c2 = st.columns(2)
        with c1:
            laudo_file = st.file_uploader("📄 Laudo (PDF)", type=["pdf"], key="laudo_new", help="Anexar laudo médico")
        with c2:
            avaliacao_file = st.file_uploader("📋 Avaliação (PDF)", type=["pdf"], key="avaliacao_new", help="Anexar avaliação")

        submitted = st.form_submit_button("💾 Salvar atendimento", use_container_width=True, type="primary")
        if submitted:
            # Validação básica
            if not empresa or not nome or not modalidade:
                st.error("❌ Por favor, preencha todos os campos obrigatórios (*).")
            else:
                empresa_s = security.sanitize_input(empresa)
                nome_s = security.sanitize_input(nome)
                modalidade_s = security.sanitize_input(modalidade)
                data_s = data_v.strftime("%Y-%m-%d")
                hora_s = hora_v.strftime("%H:%M")
                obs_s = security.sanitize_input(observacoes, max_len=2000) if observacoes else None
                
                # Upload de arquivos
                laudo_path = save_uploaded_pdf(laudo_file) if laudo_file else None
                avaliacao_path = save_uploaded_pdf(avaliacao_file) if avaliacao_file else None

                ok = services.create_atendimento(
                    empresa=empresa_s,
                    nome=nome_s,
                    modalidade=modalidade_s,
                    data=data_s,
                    hora=hora_s,
                    laudo_pdf=laudo_path,
                    avaliacao_pdf=avaliacao_path,
                    observacoes=obs_s
                )
                if ok:
                    security.log_access("CREATE_ATENDIMENTO", f"{empresa_s}|{nome_s}|{modalidade_s}")
                    st.success("✅ Atendimento salvo com sucesso!")
                    st.balloons()
                else:
                    st.error("❌ Falha ao salvar atendimento. Verifique o banco de dados.")

with tab2:
    st.subheader("📋 Lista de atendimentos")
    
    if not db_ok:
        st.warning("⚠️ Banco de dados não conectado. Não é possível listar atendimentos.")
        st.stop()
    
    data = services.list_atendimentos()
    if data:
        df = pd.DataFrame(data)
        # Formatação visual
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("ID", width="small"),
                "empresa": st.column_config.TextColumn("Empresa", width="medium"),
                "nome": st.column_config.TextColumn("Paciente", width="medium"),
                "modalidade": st.column_config.TextColumn("Modalidade", width="medium"),
                "data": st.column_config.TextColumn("Data", width="small"),
                "hora": st.column_config.TextColumn("Hora", width="small"),
                "status": st.column_config.TextColumn("Status", width="small"),
            }
        )
        st.caption(f"📊 Total de atendimentos: **{len(data)}**")
    else:
        st.info("ℹ️ Nenhum atendimento cadastrado ainda.")

    st.divider()
    st.subheader("✏️ Atualizar ou Excluir Atendimento")

    ids = [r.get("id") for r in data] if data else []
    
    if not ids:
        st.warning("⚠️ Não há atendimentos para atualizar/excluir.")
    else:
        selected_id = st.selectbox("🔍 Selecione o ID do atendimento", ids, help="Escolha o atendimento para editar ou excluir")

        c1, c2, c3 = st.columns(3)
        with c1:
            up_laudo = st.file_uploader("📄 Atualizar Laudo (PDF)", type=["pdf"], key="laudo_up")
        with c2:
            up_av = st.file_uploader("📋 Atualizar Avaliação (PDF)", type=["pdf"], key="avaliacao_up")
        with c3:
            novo_status = st.text_input("📌 Status", "", placeholder="Ex: Realizado, Cancelado")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("💾 Salvar atualizações", use_container_width=True, disabled=selected_id is None):
                update_fields = {}
                if up_laudo:
                    p = save_uploaded_pdf(up_laudo)
                    if p: update_fields["laudo_pdf"] = p
                if up_av:
                    p = save_uploaded_pdf(up_av)
                    if p: update_fields["avaliacao_pdf"] = p
                if novo_status.strip():
                    update_fields["status"] = security.sanitize_input(novo_status, 100)
                if not update_fields:
                    st.warning("⚠️ Nenhuma alteração foi feita.")
                else:
                    ok = db.atualizar_atendimento(int(selected_id), **update_fields)
                    if ok:
                        security.log_access("UPDATE_ATENDIMENTO", f"id={selected_id}|{list(update_fields.keys())}")
                        st.success("✅ Atualizado com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Falha ao atualizar.")
        with b2:
            if st.button("🗑️ Excluir atendimento", type="secondary", use_container_width=True, disabled=selected_id is None):
                ok = db.excluir_atendimento(int(selected_id))
                if ok:
                    security.log_access("DELETE_ATENDIMENTO", f"id={selected_id}")
                    st.success("✅ Excluído com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Falha ao excluir.")

with tab3:
    st.subheader("⚠️ Painel de pendências")
    
    if not db_ok:
        st.warning("⚠️ Banco de dados não conectado.")
        st.stop()
    
    pend = services.pending_items()
    c1, c2, c3 = st.columns(3)
    c1.metric("📄 Sem laudo", pend.get("sem_laudo", 0), help="Atendimentos sem laudo anexado")
    c2.metric("📋 Sem avaliação", pend.get("sem_avaliacao", 0), help="Atendimentos sem avaliação anexada")
    c3.metric("⚠️ Sem ambos", pend.get("sem_ambos", 0), help="Atendimentos sem laudo e sem avaliação")