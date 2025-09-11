E2E Playwright - Novo Atendimento

Requisitos
- Python 3.8+
- Playwright (instalar via pip) e browsers do Playwright

Instalação rápida:

```powershell
python -m pip install playwright
python -m playwright install
```

Executar o teste (assumindo servidor Streamlit local em http://127.0.0.1:8512):

```powershell
python e2e\e2e_playwright_new_appointment.py
```

Observações
- O script é um teste conservador; seletores podem precisar ser ajustados conforme a UI atual.
- Preferível rodar com o Streamlit já aberto localmente.
