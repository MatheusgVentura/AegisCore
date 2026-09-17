# 🛡️ AegisCore — Vault Engine

**AegisCore** é um cofre de credenciais e senhas local de alto desempenho e segurança militar, construído com foco em criptografia moderna, privacidade absoluta e design refinado inspirado no tema *Desert Gold*.

---

## 🔒 Arquitetura Criptográfica & Segurança

- **Derivação de Chaves (KDF):** `Argon2id` (64 MB de memória, 4 iterações, 4 lanes paralelas), resistente a ataques massivos de GPU e ASIC.
- **Cifra Simétrica Autenticada:** `AES-256-GCM` (AEAD) com autenticação de integridade (Tag de 128 bits) e Nonces criptograficamente seguros de 96 bits (`os.urandom(12)`).
- **Persistência Atômica:** Gravações com flush e `os.fsync()` em arquivos temporários antes da substituição atômica no disco, prevenindo corrupção mesmo em caso de corte repentino de energia.
- **Backup Automático:** Criação automática de arquivo de recuperação (`vault.enc.bak`) a cada escrita.
- **Higienização de Clipboard:** Limpeza automática da área de transferência após 15 segundos ao copiar senhas confidenciais.

---

## ✨ Funcionalidades

- **Reconhecimento Automático de Logos:** Detecção inteligente de serviços populares (Gmail, HackerOne, GitHub, Discord, AWS, Microsoft, OpenAI, Steam, bancos brasileiros, etc.) com exibição da logo oficial em alta resolução.
- **Abertura Rápida no Navegador (↗️):** Botão direto no card para abrir o site ou página de login no seu navegador padrão do Windows.
- **Organização por Drag-and-Drop:** Arraste e solte os cards de credenciais para organizar a ordem como preferir, com persistência criptografada.
- **Favoritos com 1 Clique:** Marque ou desmarque serviços favoritos com filtro dedicado em tempo real.
- **Gerador Avançado de Senhas:** Geração criptográfica com cálculo de entropia (Shannon / bits) em tempo real.
- **Busca Rápida Instantânea:** Localização por serviço, usuário ou notas com atalho global (`Ctrl + K`).

---

## 📁 Estrutura do Projeto

```text
📁 AegisCore/
│
├── 📄 app.py                  # Ponto de entrada do aplicativo (PyWebview + API)
├── 📄 vault_core.py            # Motor criptográfico, Argon2id e I/O atômico
├── 📄 iniciar_aegiscore.bat   # Inicializador silencioso com duplo clique
├── 📄 requirements.txt        # Dependências do Python
├── 📄 README.md               # Documentação técnica do projeto
├── 📄 aegiscore.ico           # Ícone do aplicativo para o Windows
├── 📄 vault.enc               # Cofre de senhas criptografado local
├── 📄 vault.enc.bak           # Backup de segurança automático
├── 📄 .gitignore              # Regras de exclusão para versionamento
│
└── 📁 ui/                     # Interface gráfica do usuário (HUD)
    ├── 📄 index.html          # Estrutura visual e modais
    ├── 📄 style.css           # Design Desert Gold, tipografia Cinzel e microinterações
    ├── 📄 app.js              # Lógica de interface, drag-and-drop e pontes API
    └── 📄 logo.png            # Brasão AegisCore oficial
```

---

## 🚀 Como Executar

### 1. Atalho na Área de Trabalho
Você pode abrir o aplicativo diretamente pelo atalho **AegisCore** criado na sua Área de Trabalho.

### 2. Pelo Executável em Lote
Basta dar um duplo clique no arquivo [`iniciar_aegiscore.bat`](./iniciar_aegiscore.bat).

### 3. Pelo Terminal
```powershell
python app.py
```
*(Ou de forma silenciosa sem console: `pythonw app.py`)*

---

## 📦 Dependências

- Python 3.10+
- `cryptography>=50.0.0`
- `pywebview>=6.2.0`
- `pyperclip>=1.11.0`
- `Pillow>=12.0.0`

Instalação rápida:
```bash
pip install -r requirements.txt
```
