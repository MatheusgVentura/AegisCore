# 🛡️ AegisCore — Vault Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-gold.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)
[![Security](https://img.shields.io/badge/Security-Argon2id%20%2B%20AES--256--GCM-success.svg)](#-arquitetura-criptográfica--segurança)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%99%A5-red.svg)](https://github.com/MatheusgVentura/AegisCore)

**AegisCore** é um cofre de credenciais e senhas local de alto desempenho e segurança militar, construído com foco em criptografia moderna, privacidade absoluta e design refinado inspirado no tema *Desert Gold*. Desenvolvido como software livre e de código aberto (*Open Source*), seguindo o princípio da transparência e segurança auditável por design.

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
├── 📄 LICENSE                 # Licença de código aberto MIT
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

## 🚀 Como Usar e Executar

### 🌟 Para Usuários Finais (Sem precisar instalar Python)
1. Vá até a aba [**Releases**](https://github.com/MatheusgVentura/AegisCore/releases) do repositório.
2. Baixe o pacote portátil `AegisCore-Portable-Windows.zip` ou o instalador `AegisCore-Setup.exe`.
3. Descompacte o arquivo `.zip` e clique duas vezes em `AegisCore.exe` para começar a usar imediatamente!

### 💻 Para Desenvolvedores (A partir do código-fonte)

#### 1. Atalho ou Arquivo em Lote
- Duplo clique em [`iniciar_aegiscore.bat`](./iniciar_aegiscore.bat) para iniciar em segundo plano.

#### 2. Pelo Terminal
```powershell
python app.py
```
*(Ou de forma silenciosa sem console: `pythonw app.py`)*

#### 3. Gerando o Executável (.exe) e o Pacote Portátil (.zip)
Execute o script de compilação automática:
```powershell
.\build.bat
```
Os binários prontos para distribuição serão gerados na pasta `dist/`.

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

---

## ⚖️ Código Aberto & Licença

O **AegisCore** é um projeto de código aberto sob a licença [MIT](./LICENSE).

Acreditamos que softwares de segurança e gerenciamento de senhas devem ser **100% transparentes, auditáveis e livres de código proprietário obscuro**. Qualquer pessoa ou pesquisador de segurança pode inspecionar, auditar e contribuir com o código-fonte.

Copyright (c) 2026 Matheus Ventura.

