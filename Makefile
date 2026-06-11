# Makefile para MVP Dep. Psicologia
#
# Uso:
#   make run          - Rodar o app Streamlit
#   make install      - Instalar dependências
#   make freeze       - Congelar dependências
#   make clean        - Limpar arquivos temporários
#   make push         - Commitar e enviar para o GitHub
#   make status       - Ver status do git
#   make help         - Ver ajuda

.PHONY: help install run freeze clean push status lint

PROJECT_DIR := /home/jean/Downloads/mvpdepsicologia
VENV        := $(PROJECT_DIR)/venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip

help:
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════╗"
	@echo "║           MVP Dep. Psicologia - Makefile                      ║"
	@echo "╚═══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Comandos disponíveis:"
	@echo ""
	@echo "  make run          - Rodar app Streamlit (http://localhost:8501)"
	@echo "  make install      - Instalar dependências"
	@echo "  make freeze       - Congelar dependências em requirements.txt"
	@echo "  make clean        - Limpar arquivos temporários"
	@echo "  make lint         - Verificar código com pylint"
	@echo "  make status       - Ver status do git"
	@echo "  make push         - Commitar tudo e enviar para o GitHub"
	@echo "  make help         - Esta mensagem"
	@echo ""

# ─────────────────────────────────────────────────────────────────

install:
	@echo "📦 Instalando dependências..."
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "✅ Dependências instaladas!"

freeze:
	@echo "📋 Congelando dependências..."
	@$(PIP) freeze > requirements.txt
	@echo "✅ requirements.txt atualizado!"

run:
	@echo ""
	@echo "🌐 Iniciando Streamlit..."
	@echo "✨ Acesse: http://localhost:8501"
	@echo ""
	@. $(VENV)/bin/activate && cd $(PROJECT_DIR) && streamlit run app.py

lint:
	@echo ""
	@echo "🔍 Verificando código..."
	@echo ""
	@. $(VENV)/bin/activate && cd $(PROJECT_DIR) && \
		python -m pylint app.py db.py ai_manager.py --disable=all --enable=E,F

clean:
	@echo "🧹 Limpando arquivos temporários..."
	@find $(PROJECT_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find $(PROJECT_DIR) -type f -name "*.pyc" -delete
	@rm -rf $(PROJECT_DIR)/.pytest_cache
	@echo "✅ Limpeza concluída!"

status:
	@echo ""
	@echo "📊 Status do repositório:"
	@echo ""
	@cd $(PROJECT_DIR) && git status
	@echo ""
	@echo "📜 Últimos commits:"
	@echo ""
	@cd $(PROJECT_DIR) && git log --oneline -5

push:
	@echo ""
	@echo "🚀 Enviando para o GitHub..."
	@echo ""
	@cd $(PROJECT_DIR) && git add -A
	@cd $(PROJECT_DIR) && git diff --cached --name-only | xargs -I{} echo "  📄 {}"
	@cd $(PROJECT_DIR) && git commit -m "update: $(shell date '+%Y-%m-%d %H:%M')" || echo "⚠️  Nada novo para commitar."
	@cd $(PROJECT_DIR) && git push origin main
	@echo ""
	@echo "✅ Push concluído!"

# ─────────────────────────────────────────────────────────────────

.SILENT: help
