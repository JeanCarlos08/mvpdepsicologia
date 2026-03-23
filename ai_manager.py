import os
import google.generativeai as genai
from typing import Optional
import db

def _get_api_key() -> Optional[str]:
    """Recupera a chave da API do Google Gemini do ambiente ou Streamlit Secrets."""
    # Prioridade para Streamlit Secrets (Produção)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GOOGLE_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass
    
    # Fallback para .env / Variáveis de ambiente (Local)
    return os.getenv("GOOGLE_API_KEY")

class AIManager:
    """Gerencia a inteligência artificial do sistema (resumos, análises e chat)."""
    
    _model = None

    @classmethod
    def _initialize(cls):
        if not cls._model:
            api_key = _get_api_key()
            if not api_key:
                return False
            genai.configure(api_key=api_key)
            # Usar o nome padrão estável do modelo
            cls._model = genai.GenerativeModel('gemini-1.5-flash')
        return True

    @classmethod
    def analyze_pdf_content(cls, file_content: bytes, filename: str) -> str:
        """Analisa o conteúdo de um PDF usando Gemini e retorna um resumo clínico."""
        if not cls._initialize():
            return "Erro: Chave de API da IA não configurada."
        
        try:
            prompt = f"""
            Você é um assistente especializado em gestão clínica de psicologia e medicina do trabalho. 
            Analise o conteúdo deste arquivo PDF ({filename}) e forneça um resumo executivo:
            1. Pontos principais do laudo/avaliação.
            2. Recomendações ou conclusões principais.
            3. Algum dado de saúde crítico que mereça atenção.
            
            Seja conciso e profissional. Se não conseguir ler os dados, informe.
            Responda em Português do Brasil.
            """
            
            # Preparar o arquivo para o Gemini (Multimodal)
            # Nota: flas-1.5 aceita bytes via upload_file ou inline_data
            response = cls._model.generate_content([
                prompt,
                {'mime_type': 'application/pdf', 'data': file_content}
            ])
            
            return response.text if response else "A IA não retornou uma resposta válida."
        except Exception as e:
            from app import Security
            Security.log_error("AI_PDF_ANALYSIS", e)
            return f"Falha na análise da IA: {str(e)}"

    @classmethod
    def chat_with_data(cls, query: str, context_df_json: str) -> str:
        """Chat inteligente que analisa o contexto dos dados atuais do usuário."""
        if not cls._initialize():
            return "IA não disponível."
        
        try:
            prompt = f"""
            Você é a 'IA Juliana', assistente de gestão clínica. 
            Com base nos dados abaixo (JSON), responda à pergunta do usuário.
            
            Dados atuais:
            {context_df_json}
            
            Pergunta: {query}
            
            Seja prestativa, use tabelas se necessário e cite nomes ou empresas se presentes nos dados.
            """
            response = cls._model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Erro no chat: {str(e)}"
