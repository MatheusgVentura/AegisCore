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

## 📦 Versão 1.2.0 — Operação Tática, Atalhos & Bandeja (Versão Atual)

### 🎯 Objetivos
Agilizar a operação diária no Windows eliminando atrito ao fazer login em programas, navegadores e jogos, oferecendo background daemon com auto-bloqueio proativo e persistência atômica de preferências.

### 🧩 Funcionalidades Entregues
1. **Auto-Type Global & Local (Preenchimento Universal por Atalho)**
   - Atalho global de teclado (`Ctrl + Alt + V`) via `pynput` em qualquer aplicativo do Windows.
   - Botão tático de Auto-Type em cada card de credencial no Web HUD.
   - Minimização instantânea para devolução do foco à janela anterior e simulação sequencial: `Usuário` ➔ `[Tab]` ➔ `Senha` ➔ `[Enter]`.
   - Preferências configuráveis para envio de `Enter` e delay de foco (300ms a 1500ms).

2. **Ícone e Menu na Bandeja do Sistema (System Tray Icon)**
   - Ícone do escudo AegisCore no relógio do Windows gerenciado via `pystray`.
   - Minimização inteligente para segundo plano ao clicar no botão Fechar [X].
   - Menu de contexto com ações rápidas: *Abrir AegisCore, Auto-Type (Ctrl+Alt+V), Bloquear Cofre, Gerar Senha Rápida, Sair*.

3. **Auto-Bloqueio por Inatividade (Inactivity Auto-Lock)**
   - Temporizador de inatividade configurável (1, 5, 15, 30, 60 min ou desativado).
   - Detecção reativa de eventos do usuário com throttling e higienização imediata da memória RAM e área de transferência.
   - Banner tático na tela de desbloqueio informando o auto-bloqueio preventivo.

4. **Gerador de Frases-Senha (Passphrases estilo Diceware)**
   - Dicionário curado de 536 palavras em português (`DICEWARE_WORDS`).
   - Abas no modal de geração ("Senha Aleatória" vs "Frase-Senha (Diceware)").
   - Controles dinâmicos de quantidade de palavras (3 a 7), separador customizado, capitalização e número de sufixo.
   - Cálculo de entropia matemática em tempo real baseado no espaço amostral do dicionário.

5. **Central de Preferências do Sistema (Settings HUD)**
   - Modal de configurações com design Desert Gold para auto-bloqueio, limpeza de clipboard, bandeja e auto-type.
   - Engine atômica de persistência (`settings.json`).

---

## 📦 Versão 1.1.0 — Super App de Segurança & Migração (Versão Anterior)

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
