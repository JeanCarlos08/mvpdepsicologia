# 📋 Guia de Teste - Sistema de Gestão Clínica

## Funcionalidades de PDF e Anexos - Como Testar

### 1. ✅ Geração de PDF da Lista de Atendimentos

**Como testar:**
1. Vá para a aba "Atendimentos"
2. Cadastre alguns atendimentos
3. Na seção de tabela, clique em "⬇️ Exportar PDF"
4. Verifique se o arquivo PDF foi gerado e pode ser aberto

**Resultado esperado:**
- PDF com título "Relatório de Atendimentos"
- Tabela contendo: Empresa, Nome, Modalidade, Data, Hora, Status
- Data de geração no canto superior direito

---

### 2. ✅ Upload de Laudo PDF

**Como testar:**
1. Vá para "Atendimentos" → "Cadastrar Novo Atendimento"
2. Preencha os campos obrigatórios (Empresa, Nome)
3. Na seção "Anexos", clique em "📄 Laudo PDF"
4. Selecione um arquivo PDF
5. Clique em "💾 Salvar"

**Resultado esperado:**
- Arquivo é validado (verifica se é PDF válido)
- Mensagem "Atendimento cadastrado com sucesso!" aparece
- Anexo é salvo no banco de dados com referência `db:<id>`

---

### 3. ✅ Upload de Avaliação PDF

**Como testar:**
1. Mesmo procedimento do Laudo, mas com "📝 Avaliação PDF"
2. Pode enviar tanto Laudo quanto Avaliação no mesmo atendimento

**Resultado esperado:**
- Ambos os anexos são salvos independentemente
- Cada um recebe um ID de referência no banco

---

### 4. ✅ Análise de PDF com IA

**Como testar:**
1. No formulário de cadastro, após selecionar um PDF
2. Clique em "🪄 Analisar [Laudo/Avaliação] com IA"
3. A IA irá gerar um resumo do documento

**Resultado esperado:**
- Resumo textual dos pontos principais do documento
- Recomendações extraídas pelo modelo Gemini
- Texto aparece no campo de "Observações"

**Pré-requisito:** Variável `GOOGLE_API_KEY` configurada no `.env`

---

### 5. ✅ Download de Anexos

**Como testar:**
1. Cadastre um atendimento com anexo
2. Na lista de atendimentos, encontre a linha do atendimento
3. Procure pelos botões "⬇️ Laudo" e "⬇️ Avaliação"
4. Clique para fazer download do arquivo

**Resultado esperado:**
- Arquivo PDF é baixado com o nome original
- Verificar se o arquivo está intacto (não corrompido)

---

### 6. ✅ Visualização de Anexos

**Como testar:**
1. Na lista de atendimentos, clique em "👁️ Ver Laudo" ou "👁️ Ver Aval."
2. O PDF deve ser exibido em um iframe dentro da página

**Resultado esperado:**
- PDF é exibido direto no navegador
- Pode usar as ferramentas de visualização do PDF (zoom, etc)

---

### 7. ✅ Edição de Atendimento com Novo Anexo

**Como testar:**
1. Na aba "Atendimentos", procure um atendimento cadastrado
2. Clique em "📎 Gerenciar por atendimento"
3. Procure pelo atendimento e clique em "✏️ Editar"
4. Na seção "Anexos", escolha um novo arquivo para substituir
5. Clique em "💾 Salvar alterações"

**Resultado esperado:**
- Anexo antigo é removido do banco
- Novo anexo é salvo com novo ID
- Mensagem "Alterações salvas com sucesso!" aparece

---

### 8. ✅ Exclusão de Anexo

**Como testar:**
1. Na aba "Atendimentos", procure um atendimento com anexo
2. Clique em "📎 Gerenciar por atendimento"
3. Procure pelos botões "🗑️ Laudo" ou "🗑️ Aval."
4. Clique para excluir o anexo

**Resultado esperado:**
- Anexo é removido do banco
- Referência no atendimento é setada como NULL
- Campo "Laudo"/"Avaliação" na lista passa a mostrar "NÃO"

---

### 9. ✅ Exportação de Atendimento Individual

**Como testar:**
1. Na aba "Atendimentos" → "📎 Gerenciar por atendimento"
2. Procure pelo atendimento desejado
3. Clique em "✏️ Editar"
4. Em "Manutenção de Dados" → Aba "🔎 Recuperar Dados"
5. Clique em "⬇️ Baixar registro como JSON"

**Resultado esperado:**
- Arquivo JSON é baixado com todos os dados do atendimento
- Pode ser usado para auditoria ou backup individual

---

### 10. ✅ Geração de Parecer Clínico

**Como testar:**
1. Na aba "Atendimentos" → "📎 Gerenciar por atendimento"
2. Procure pelo atendimento
3. Clique em "✏️ Editar" ou abra o container "🪄 Gerar Parecer Clínico"
4. Escreva algumas anotações em "Suas anotações (rascunho)"
5. Clique em "✍️ Gerar Parecer Formal"

**Resultado esperado:**
- IA transforma as anotações em um parecer formal estruturado
- Texto em Markdown é exibido
- Botão "⬇️ Baixar Parecer (.txt)" permite salvar

---

## 🔧 Troubleshooting

### PDF não está sendo gerado

**Verificar:**
1. Dependência `fpdf2` está instalada: `pip list | grep fpdf2`
2. Se não, instalar: `pip install fpdf2==2.8.2`
3. Tentar fazer download novamente

### Anexo não está sendo salvo

**Verificar:**
1. PostgreSQL está conectado: Clique em "🩺 Verificar Banco" nas Configurações
2. Arquivo é PDF válido (começa com `%PDF`)
3. Tamanho do arquivo < 50MB
4. Se erro persiste, checar logs em `./logs/error.log`

### IA não está analisando PDFs

**Verificar:**
1. `GOOGLE_API_KEY` está no `.env` ou Streamlit Secrets
2. Chave API é válida e tem créditos disponíveis
3. Modelo Gemini está disponível para a chave (alguns modelos requerem acesso especial)
4. Se erro persiste, sistema funcionará sem IA (modo degradado)

### Download de PDF falha

**Verificar:**
1. Navegador está permitindo downloads
2. Espaço em disco disponível
3. Arquivo não foi deletado do banco enquanto tentava baixar
4. Se erro persiste, tentar de outro navegador

---

## 📊 Checklist de Validação Final

Antes de colocar em produção, validar:

- [ ] Cadastro de atendimento com ambos os anexos
- [ ] Edição de atendimento trocando anexos
- [ ] Download e visualização de PDF funcionam
- [ ] Exclusão de anexo funciona
- [ ] PDF de relatório é gerado corretamente
- [ ] Backup do banco pode ser feito
- [ ] Todos os logs estão sendo gravados em `./logs/`
- [ ] Sem erros críticos ao testar fluxo completo

---

## 📝 Notas Técnicas

**Armazenamento de Anexos:**
- PDFs são salvos na tabela `arquivos` como BYTEA (dados binários)
- Referência salva em `atendimentos.laudo_pdf` e `avaliacao_pdf` no formato `db:<file_id>`
- Fallback em disco local na pasta `./uploads/` se banco falhar

**Validação de PDF:**
- Verifica se começa com magic bytes `%PDF` 
- IA verifica se parece um documento clínico válido
- Limite de 50MB por arquivo para proteção de memória

**Data e Hora:**
- Armazenados como tipos DATE e TIME no PostgreSQL
- Streamlit converte automaticamente ao submitir form
- psycopg2 converte objetos Python para tipos SQL

---

**Última atualização:** 06/06/2026
**Versão:** 1.0
**Status:** ✅ Pronto para Teste
