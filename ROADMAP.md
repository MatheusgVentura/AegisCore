# 🗺️ AegisCore — Roadmap de Evolução & Arquitetura

Este documento consolida a visão de futuro, arquitetura técnica e o cronograma de funcionalidades planejadas para o **AegisCore**, garantindo a preservação dos princípios fundamentais: **100% Offline, Zero Telemetria, Criptografia Militar e Design HUD Desert Gold**.

---

## 🧭 Visão Estratégica das Versões

```
[ v1.0.0 ] ──> [ v1.1.0 ] ──> [ v1.2.0 ] ──> [ v2.0.0 ]
  Lançamento     Super App       Auto-Type       Extensão de
  Oficial        • 2FA / TOTP    • Atalho Global Navegador
                 • Auditoria     • Tray Icon     • Native Messaging
                 • Import/Export                 • Preenchimento Web
```

---

## 📦 Versão 1.1.0 — Super App de Segurança & Migração (Versão Atual)

### 🎯 Objetivos
Elevar o AegisCore de um gerenciador de credenciais básico para um cofre multifuncional com suporte nativo a segundo fator e análise proativa de riscos.

### 🧩 Funcionalidades
1. **Autenticador 2FA / TOTP Integrado (RFC 6238 / RFC 4226)**
   - Armazenamento de chaves secretas Base32 e URIs `otpauth://totp/...`.
   - Geração de tokens de 6 dígitos em tempo real com contador regressivo de 30 segundos.
   - Cópia do token com 1 clique diretamente pelo card da credencial.
   - Implementação nativa com Python puro (`hashlib`, `hmac`, `struct`) — zero dependências externas.

2. **Central de Saúde do Cofre (Security Audit & Health HUD)**
   - Painel tático com métricas de blindagem e pontuação geral de segurança (0 a 100%).
   - Detecção automática de **Senhas Fracas** (baseado na Entropia de Shannon).
   - Detecção de **Senhas Reutilizadas** em múltiplos serviços (risco crítico de vazamento em cascata).
   - Filtros instantâneos para visualizar e corrigir credenciais vulneráveis com 1 clique.

3. **Importação e Exportação de Credenciais (CSV)**
   - **Importador Inteligente:** Reconhece e mapeia automaticamente formatos do Google Chrome, Brave, Microsoft Edge, Bitwarden e KeePassXC.
   - **Exportador Seguro:** Exportação em formato CSV padronizado para backup portátil.
   - Suporte a seleção de arquivos e processamento direto no cofre.

4. **Nova Identidade Visual & Design System v1.1.0**
   - **Nova Logo do Escudo:** Escudo geométrico com nós entrelaçados em ouro escovado (substituindo a antiga Medusa).
   - **Paleta Ouro Nobre Escuro:** Fundo Obsidian Warm (`#0c0a07`), cards (`#15120c`), botões e detalhes em ouro escovado nobre (`#c5a038`).
   - **Nova Tipografia High-Tech:** `Orbitron` (800 Bold) + `Michroma` com suporte a execução 100% offline via fontes locais em `ui/fonts/`.
   - **Filtros de Tópicos Minimalistas:** Pílulas sem emojis com ícones lineares vetoriais SVG (estrelas, chaves, avisos, setas e escudos).
   - **Pacote Multi-Resolução do Windows:** Ícone `.ico` gerado com suporte nativo de 16x16 até 256x256 para barra de tarefas e instalador.

---

## ⚡ Versão 1.2.0 — Operação Tática & Atalho Global (Planejado)

### 🎯 Objetivos
Agilizar o uso diário no Windows eliminando atrito ao fazer login em programas, navegadores e jogos.

### 🧩 Funcionalidades
1. **Auto-Type Global (Preenchimento Universal por Atalho)**
   - Atalho global de teclado configurável (ex: `Ctrl + Alt + V`).
   - O AegisCore detecta a janela em foco ativa no Windows.
   - Simula a sequência automática de digitação: `Usuário` ➔ `[Tab]` ➔ `Senha` ➔ `[Enter]`.
   - **Vantagem:** Funciona em qualquer navegador e programas desktop (Steam, Discord, Spotify, etc.) sem precisar de extensão.

2. **Minimizar para a Bandeja do Sistema (System Tray)**
   - Ícone do escudo AegisCore perto do relógio do Windows (`pystray`).
   - Fechar a janela oculta o app sem encerrar o processo.
   - Menu de contexto rápido: *Bloquear Cofre, Gerar Senha Rápida, Abrir Cofre, Sair*.

3. **Auto-Bloqueio por Inatividade (Inactivity Auto-Lock)**
   - Temporizador de segurança configurável (ex: 5 min, 15 min, 30 min sem interação).
   - Higienização imediata das chaves criptográficas da memória RAM e retorno à tela de bloqueio.

4. **Gerador de Frases-Senha (Passphrases / Estilo Diceware / XKCD)**
   - Geração de combinações de palavras seguras e memoráveis (ex: `deserto-pantera-safira-42`).

---

## 🧩 Versão 2.0.0 — Integração com Navegadores (AegisCore Companion Extension)

### 🎯 Objetivos
Criar a extensão oficial para Google Chrome, Brave, Edge e Firefox, permitindo preenchimento de login com 1 clique diretamente nas páginas web.

### 🏗️ Arquitetura Técnica Proposta
Devido ao isolamento de segurança (*sandbox*) dos navegadores, a extensão não pode ler o arquivo `vault.enc` diretamente. A comunicação será realizada através de um dos modelos abaixo:

#### Opção A: Native Messaging Host (Padrão KeePassXC & 1Password)
* O instalador do AegisCore registra um manifesto em:
  `HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\aegiscore_companion`
* O Chrome abre um canal de comunicação de entrada/saída padrão (`stdin`/`stdout`) com mensagens JSON codificadas com prefixo de tamanho de 4 bytes.
* **Segurança:** Máxima, pois apenas a extensão com o ID autorizado consegue disparar mensagens.

#### Opção B: Mini-Servidor Local Seguro (WebSocket Local em `127.0.0.1`)
* O AegisCore executa um servidor em loopback local (`127.0.0.1:18291`).
* A extensão se conecta e realiza um handshake de pareamento com código de confirmação na tela (evita que sites maliciosos acessem a porta).
* Suporte a múltiplos navegadores com um único servidor.

### 📋 Módulos da Extensão (Manifest V3)
* **Content Script:** Detecta formulários de login (`<input type="password">`, `<input type="email">`).
* **Injeção com 1 clique:** Ícone do AegisCore dentro do campo para preenchimento imediato.
* **Popup de Navegador:** Visualização rápida das credenciais da URL atual.
