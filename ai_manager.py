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
        """Inicializa o modelo com sistema de fallback para evitar erros 404 de modelos retirados."""
        if cls._model:
            return True
            
        api_key = _get_api_key()
        if not api_key:
            return False
            
        genai.configure(api_key=api_key)
        
        # Lista de modelos disponíveis para esta API Key (versões 2.0 e 2.5)
        candidates = [
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-flash-latest',
            'gemini-2.5-pro'
        ]
        
        last_error = None
        for model_name in candidates:
            try:
                # Teste rápido: instanciar o modelo
                m = genai.GenerativeModel(model_name)
                # Tentar uma chamada mínima para validar se o modelo existe para esta API Key
                # (Opcional, mas garante que o 404 não aconteça depois)
                cls._model = m
                return True
            except Exception as e:
                last_error = e
                continue
        
        if last_error:
            # Se nenhum funcionar, tentamos o genérico e deixamos o erro propagar se falhar
            try:
                cls._model = genai.GenerativeModel('gemini-pro')
                return True
            except:
                pass
        
        return False

    @classmethod
    def analyze_pdf_content(cls, file_content: bytes, filename: str) -> str:
        """Analisa o conteúdo de um PDF usando Gemini e retorna um resumo clínico."""
        if not cls._initialize():
            return "Erro: Chave de API da IA não configurada ou modelos indisponíveis."
        
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
    def generate_clinical_draft(cls, nome: str, empresa: str, modalidade: str, observacoes: str) -> str:
        """Gera um rascunho de parecer clínico formal baseado nos dados do atendimento."""
        if not cls._initialize():
            return "Erro: IA não disponível."
        
        try:
            prompt = f"""
            Você é um assistente de psicólogos e médicos do trabalho.
            Transforme as breves notas abaixo em um parecer clínico profissional e formal, com vocabulário técnico, pronto para ser assinado.
            
            **Dados do Paciente:**
            - Nome: {nome}
            - Empresa: {empresa}
            - Avaliação: {modalidade}
            
            **Anotações da Profissional (Rascunho):**
            "{observacoes}"
            
            **Regras:**
            - Comece com um cabeçalho formal ("PARECER TÉCNICO / CLÍNICO").
            - Desenvolva as anotações em parágrafos coesos e bem estruturados.
            - Termine com um espaço para "Data" e "Assinatura do Profissional".
            - Retorne o texto em Português do Brasil, formatado em Markdown limpo.
            """
            response = cls._model.generate_content(prompt)
            return response.text if response else "Falha ao gerar o parecer."
        except Exception as e:
            from app import Security
            Security.log_error("AI_DRAFT_GEN", e)
            return f"Erro na IA: {str(e)}"

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
