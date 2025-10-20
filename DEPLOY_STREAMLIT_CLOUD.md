#  Deploy no Streamlit Cloud - Guia Completo

##  ERRO COMUM: DATABASE_URL com localhost

O erro mais comum ao fazer deploy no Streamlit Cloud é usar um banco PostgreSQL local (localhost/127.0.0.1).

**Streamlit Cloud NÃO pode acessar seu banco local!**

##  Solução: Use PostgreSQL em Nuvem (GRÁTIS)

### **Recomendação: Supabase** 

1. Acesse: https://supabase.com
2. Crie conta grátis
3. Create New Project:
   - Nome: mvp-psicologia
   - Database Password: [crie uma senha forte]
   - Region: South America (São Paulo) ou US East
4. Aguarde ~2 minutos para provisionar

5. **Copie a Connection String**:
   - Vá em: Settings  Database
   - Em "Connection string" selecione **"Session pooler"**
   - Copie a URL (formato: postgresql://postgres.xxx:senha@xxx.pooler.supabase.com:5432/postgres)

##  Configurar Secrets no Streamlit Cloud

1. Acesse seu app em: https://share.streamlit.io
2. Vá em: **Settings  Secrets**
3. Cole este conteúdo (substituindo com seus dados):

\\\	oml
APP_ADMIN_USER = "admin"
APP_ADMIN_PASS = "SuaSenhaForte123"
DATABASE_URL = "sua_connection_string_do_supabase_aqui"
\\\

4. Clique em **Save**
5. O app vai reiniciar automaticamente

##  Validação

- O app criará as tabelas automaticamente na primeira execução
- Acesse o app e faça login
- Verifique se aparece: ** Conectado**

##  Outros Erros Comuns

### Erro: "ModuleNotFoundError"
- Já está corrigido no requirements.txt

### Erro: "This app has encountered an error"
1. Clique nos 3 pontinhos () no canto superior direito
2. Clique em **View logs**
3. Leia o erro e ajuste conforme necessário

##  Alternativas ao Supabase

- **Neon**: https://neon.tech (Grátis)
- **Render**: https://render.com (Grátis)
- **ElephantSQL**: https://elephantsql.com (Grátis até 20MB)
