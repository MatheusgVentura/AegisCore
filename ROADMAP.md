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

## 📦 Versão 2.0.0 — Integração com Navegadores & Companion Extension (Versão Atual)

### 🎯 Objetivos
Criar a extensão oficial para Google Chrome, Brave, Edge e Firefox (Manifest V3) e mini-servidor local seguro em loopback (`127.0.0.1:18291`), permitindo preenchimento de login com 1 clique diretamente nas páginas web com zero telemetria e operação 100% offline.

### 🧩 Funcionalidades Entregues
1. **Mini-Servidor Local Seguro em Loopback (`127.0.0.1:18291`)**
   - Ouvindo estritamente em loopback (rejeição automática 403 para IPs externos).
   - Handshake de pareamento tático com código de confirmação de 6 dígitos e emissão de `X-Aegis-Token`.
   - Consulta protegida de credenciais por domínio e preenchimento sob demanda com 2FA/TOTP em tempo real.
   - Motor de matching inteligente de URLs/domínios com prevenção de falsos positivos.

2. **AegisCore Companion Extension (Manifest V3)**
   - Compatível com Google Chrome, Microsoft Edge, Brave Browser e Mozilla Firefox.
   - **Content Script:** Injeção do badge do escudo Desert Gold em campos de login com menu dropdown tático e eventos sintéticos para frameworks reativos (React, Vue, Angular).
   - **Popup HUD:** Interface Desert Gold com status de conexão, detecção do site ativo, cópia de credenciais, TOTP e gerador de senhas.
   - **Service Worker:** Gerenciador persistente de sessão, reconexão e badge de status no ícone do navegador.

3. **Desktop HUD & Central de Preferências**
   - Modal tático de pareamento com código de 6 dígitos em tempo real no AegisCore Desktop.
   - Gestão de extensões autorizadas com possibilidade de revogação de acessos e porta customizável.

4. **Empacotamento & Distribuição**
   - Script automatizado `build_extension.py` gerando `dist/AegisCore-Companion-Extension-v2.0.0.zip`.
   - Inclusão da extensão descompactada no instalador oficial do Windows (`installer.iss`).

---

## 📦 Versão 1.2.x — Operação Tática, Atalhos & Bandeja (Versão Anterior)

---

## 🧩 Versão 2.1.0 — Evolução & Recursos Avançados (Próximos Passos)
* Suporte a múltiplos cofres isolados (Pessoal, Trabalho, Projetos).
* Detecção e oferta automática para salvar novas senhas digitadas no navegador.
* Atalho configurável de extensão para ativação rápida (`Alt + Shift + V`).
