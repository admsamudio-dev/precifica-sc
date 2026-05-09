# Precifica SC — Sistema de Precificação

Aplicação web para precificação com ICMS por estado, Lucro Presumido · Santa Catarina.

---

## Como publicar no Render.com (gratuito)

### 1. Criar conta no GitHub
Acesse https://github.com e crie uma conta gratuita.

### 2. Criar repositório
- Clique em "New repository"
- Nome: `precifica-sc`
- Marque "Public"
- Clique "Create repository"

### 3. Fazer upload dos arquivos
Na página do repositório criado, clique em "uploading an existing file"
e arraste todos os arquivos desta pasta.

Os arquivos são:
```
app.py
requirements.txt
Procfile
templates/
  login.html
  index.html
```

### 4. Criar conta no Render.com
Acesse https://render.com e clique "Get Started for Free".
Pode entrar com a conta do GitHub (mais fácil).

### 5. Criar o serviço
- Clique "New +" → "Web Service"
- Conecte seu repositório GitHub `precifica-sc`
- Preencha:
  - **Name**: precifica-sc
  - **Region**: Oregon (US West) — mais próximo do Brasil disponível no plano free
  - **Runtime**: Python 3
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `gunicorn app:app`
- Clique "Create Web Service"

### 6. Adicionar variável de ambiente (IMPORTANTE)
Após criar, vá em "Environment" e adicione:
- Key: `SECRET_KEY`
- Value: qualquer texto longo e aleatório, ex: `minha-empresa-sc-2025-chave-secreta-xyz`

### 7. Aguardar o deploy
O Render vai instalar as dependências e iniciar o servidor.
Em 2-3 minutos aparecerá uma URL no formato:
`https://precifica-sc.onrender.com`

---

## Acesso inicial

Após o primeiro acesso, o sistema cria automaticamente um usuário admin:

- **E-mail**: admin@empresa.com
- **Senha**: admin123

**TROQUE A SENHA após o primeiro login criando um novo usuário admin
e deletando o padrão.**

---

## Gerenciar equipe

O usuário admin tem acesso ao botão "Equipe" no topo da tela,
onde pode adicionar e remover usuários.

---

## Observação sobre o plano gratuito do Render

No plano gratuito, o servidor "dorme" após 15 minutos sem acesso.
O primeiro acesso após isso pode demorar ~30 segundos para "acordar".
Para uso contínuo, o plano Starter custa ~$7/mês.
