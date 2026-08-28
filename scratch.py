import pandas as pd
from fpdf import FPDF
from datetime import datetime

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

    cols = ["Empresa", "Nome", "Modalidade", "Data", "Hora", "Status"]
    widths = [70, 70, 45, 25, 22, 40] 

    pdf.set_font("Arial", 'B', 10)
    for i, col in enumerate(cols):
        pdf.cell(widths[i], 10, col, 1, 0, 'C')
    pdf.ln()

    pdf.set_font("Arial", size=8)
    
    def safe_cell_text(text):
        try:
            return str(text).encode('latin-1', 'replace').decode('latin-1')
        except:
            return str(text)

    for index, row in df.iterrows():
        try:
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
                
        except Exception as e:
            print("Error in row loop:", e)
            pass

    try:
        return pdf.output()
    except Exception as e:
        print("Error in pdf.output():", e)
        raise e

df = pd.DataFrame([{
    "Empresa": "Empresa Teste",
    "Nome": "Nome Teste",
    "Modalidade": "Consulta",
    "Data": "2023-01-01",
    "Hora": "10:00",
    "Status": "Agendado"
}])

pdf_bytes = generate_pdf_report(df)
print("PDF type:", type(pdf_bytes))
