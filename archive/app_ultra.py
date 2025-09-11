// preserved from workspace root

import streamlit as st
import pandas as pd
from datetime import date
import sqlite3
from typing import Optional, List, Dict
from dataclasses import dataclass

# Configuração mais conservadora
st.set_page_config(
    page_title="JULIANA - Gestão Clínica",
    page_icon="🧠"
)

@dataclass
class AtendimentoData:
    empresa: str
    nome: str
    modalidade: str
    data: str
    hora: str
    status: Optional[str] = None

class UltraDB:
    def __init__(self):
        self.db_path = "juliana.db"
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS atendimentos (
                id INTEGER PRIMARY KEY,
                empresa TEXT,
                nome TEXT,
                modalidade TEXT,
                data TEXT,
                hora TEXT,
                status TEXT DEFAULT 'Agendado'
            )
        """)
        conn.commit()
        conn.close()
    
    def get_all(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM atendimentos")
        columns = [d[0] for d in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def add(self, data: AtendimentoData) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO atendimentos (empresa, nome, modalidade, data, hora, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data.empresa, data.nome, data.modalidade, data.data, data.hora, data.status))
            conn.commit()
            conn.close()
            return True
        except:
            return False

def main():
    st.title("🧠 JULIANA - Gestão Clínica")
    tab1, tab2 = st.tabs(["📊 Dashboard", "➕ Novo"])
    db = UltraDB()
    with tab1:
        st.header("Dashboard")
        appointments = db.get_all()
        if appointments:
            df = pd.DataFrame(appointments)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total", len(df))
            with col2:
                st.metric("Empresas", df['empresa'].nunique())
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenhum atendimento")
    with tab2:
        st.header("Novo Atendimento")
        empresa = st.text_input("Empresa")
        nome = st.text_input("Nome")
        modalidade = st.selectbox("Modalidade", ["Presencial", "Online"])
        data = st.date_input("Data")
        hora = st.time_input("Hora")
        if st.button("Salvar"):
            if empresa and nome:
                appointment = AtendimentoData(
                    empresa=empresa,
                    nome=nome,
                    modalidade=modalidade,
                    data=str(data),
                    hora=str(hora),
                    status="Agendado"
                )
                if db.add(appointment):
                    st.success("Salvo!")
                else:
                    st.error("Erro")
            else:
                st.error("Preencha empresa e nome")

if __name__ == "__main__":
    main()
