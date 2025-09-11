from playwright.sync_api import sync_playwright
import time

URL = "http://127.0.0.1:8512"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=60000)

        # Tentar abrir a página 'Novo Atendimento' na sidebar
        try:
            # clicar pelo texto que aparece na sidebar
            page.get_by_text("Novo Atendimento").click()
        except Exception:
            # fallback: tentar clicar no radio ou link semelhante
            try:
                page.get_by_role("radio", name="Novo Atendimento").click()
            except Exception:
                pass

        # Aguarda o formulário aparecer
        page.wait_for_timeout(800)
        try:
            page.wait_for_selector("label:has-text('Empresa')", timeout=5000)
        except Exception:
            # Se não encontrar label, continuar e tentar preencher campos por ordem
            pass

        # Preencher campo Empresa e Nome do Paciente (são obrigatórios)
        try:
            page.get_by_label("Empresa").fill("ACME E2E")
        except Exception:
            # fallback: procurar por input text visível
            try:
                page.locator('input[type="text"]').first.fill('ACME E2E')
            except Exception:
                pass

        try:
            page.get_by_label("Nome do Paciente").fill("E2E Test")
        except Exception:
            try:
                # second text input (if present)
                page.locator('input[type="text"]').nth(1).fill('E2E Test')
            except Exception:
                pass

        # Submeter o formulário
        try:
            page.get_by_role("button", name="Salvar").click()
        except Exception:
            try:
                page.get_by_text("Salvar").click()
            except Exception:
                pass

        # Esperar confirmação de sucesso (mensagem criada por st.success)
        success = False
        try:
            page.wait_for_selector("text=Atendimento cadastrado", timeout=6000)
            success = True
        except Exception:
            success = False

        # Navegar para a página 'Atendimentos' e procurar o nome inserido
        try:
            page.get_by_text("Atendimentos").click()
            page.wait_for_selector("text=E2E Test", timeout=5000)
            found = True
        except Exception:
            found = False

        browser.close()

        if success and found:
            print("E2E OK: atendimento criado e listado")
            return 0
        if success and not found:
            print("E2E WARNING: criado mas não encontrado na listagem")
            return 1
        print("E2E FAILED: não foi possível criar atendimento")
        return 2

if __name__ == '__main__':
    rc = run()
    raise SystemExit(rc)
