<div align="center">

# 🛡️ AegisCore — Vault Engine

**[ 🇺🇸 English ](README.md)** • **[ 🇧🇷 Português (Brasil) ](README.pt-BR.md)**

[![License: MIT](https://img.shields.io/badge/License-MIT-gold.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](https://www.microsoft.com/windows)
[![Security](https://img.shields.io/badge/Security-Argon2id%20%2B%20AES--256--GCM-success.svg)](#-cryptographic-architecture--security)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%99%A5-red.svg)](https://github.com/MatheusgVentura/AegisCore)

<p align="center">
  <strong>Local-first, auditable, and battle-hardened password vault engine styled in Tactical Imperial Bronze with end-to-end military-grade cryptography.</strong>
</p>

<p align="center">
  <img src="./docs/screenshots/dashboard.png" alt="AegisCore Dashboard" width="880" style="border-radius: 8px;">
</p>

</div>

---

## 📖 Overview

**AegisCore** is an independent, local-first, open-source credential and password manager built under the core principle of **Absolute Privacy & Zero Telemetry**. Your data never leaves your computer. There are no remote servers, analytics, trackers, or third-party cloud services involved.

Sporting a refined HUD inspired by the elegance of *Tactical Imperial Bronze* and the geometric shield (*Aegis*), AegisCore bridges military-grade cryptographic standards with the fluid responsiveness of a native desktop application.

---

## 📸 Visual Showcase

<div align="center">

| Unlock Vault (Master Key) | Real-time Entropy Password Generator |
| :---: | :---: |
| <img src="./docs/screenshots/unlock.png" width="430" style="border-radius: 6px;"/> | <img src="./docs/screenshots/generator.png" width="430" style="border-radius: 6px;"/> |
| *Vault secured by Argon2id key derivation* | *CSPRNG generation with live Shannon entropy evaluation* |

| Vault Health & Security Audit Dashboard (v1.1.0) |
| :---: |
| <img src="./docs/screenshots/audit_health.png" width="880" style="border-radius: 8px;"/> |
| *Continuous cryptographic entropy monitoring, password reuse detection, and 2FA coverage analysis* |

</div>

---

## 🔒 Cryptographic Architecture & Security

AegisCore's security posture strictly obeys **Kerckhoffs's Principle**: security must reside entirely in the mathematical strength of the algorithm and the master password, rather than through obscurity.

- **Key Derivation Function (KDF):** Powered by `Argon2id` (Password Hashing Competition winner) configured with **64 MB** of dedicated RAM, 4 iterations, 4 parallel lanes, and a cryptographic 16-byte random salt (`os.urandom(16)`). This renders GPU/ASIC brute-force cracking attempts virtually infeasible.
- **Authenticated Encryption (AEAD):** Symmetrically encrypted with `AES-256-GCM` featuring a 128-bit integrity tag and fresh 96-bit random nonces per write operation. Tampering with even a single bit causes immediate decryption failure.
- **Atomic Persistence with `os.fsync()`:** All disk writes are first committed to temporary buffers with physical drive synchronization before performing atomic OS replacement, eliminating database corruption during sudden power failures.
- **Automatic Backups (`vault.enc.bak`):** Prior state is seamlessly mirrored to a safety backup file on each commit.
- **Memory & Clipboard Sanitization:** Clipboard entries auto-wipe after 15 seconds, and in-memory cryptographic keys are immediately cleared when locking the session.

---

## ✨ Features

- **Integrated 2FA / TOTP Authenticator:** Generates RFC 6238 compliant 6-digit tokens with real-time 30s countdown and 1-click clipboard copy on credential cards.
- **Vault Health & Security Audit Dashboard:** Analytical dashboard evaluating vault resilience (0-100%), identifying low-entropy passwords, reused credentials, and multi-factor authentication (2FA) coverage with direct corrective actions.
- **Seamless CSV Import & Export:** Effortlessly migrate credentials from Chrome, Edge, Brave, Bitwarden, and KeePassXC with intelligent field auto-detection.
- **Smart Logo Auto-Detection:** Automatically matches brand icons for hundreds of services (GitHub, AWS, Google, ProtonMail, OpenAI, Discord, Steam, Microsoft, Brazilian banks, etc.).
- **Quick Browser Launch (↗️):** Direct action buttons on credential cards to open login portals securely in your default browser.
- **Drag-and-Drop Reordering:** Organize entries manually with intuitive drag-and-drop mechanics preserved securely on disk.
- **1-Click Favorites:** Star high-priority accounts for instant filtering.
- **Instant Search (`Ctrl + K`):** Real-time multi-attribute search across services, usernames, or custom notes.
- **Advanced Password Generator:** Custom character sets and length sliders with Shannon entropy calculation (bits and rating).
- **100% Offline & Private:** Zero network requests, zero telemetry.

---

## 🚀 Getting Started

### 🌟 For End Users (No Python required)
1. Go to the [**Releases**](https://github.com/MatheusgVentura/AegisCore/releases) tab.
2. Download the standalone portable archive **`AegisCore-Portable-Windows.zip`**.
3. Extract the `.zip` anywhere and double-click **`AegisCore.exe`**.

### 💻 For Developers (Running from source)

#### 1. Clone the repository
```bash
git clone https://github.com/MatheusgVentura/AegisCore.git
cd AegisCore
```

#### 2. Install dependencies
```bash
pip install -r requirements.txt
```

#### 3. Run development server
```bash
python app.py
```
*(Or in background without terminal console: `pythonw app.py` or double-click `iniciar_aegiscore.bat`)*

#### 4. Build standalone Windows binary locally
```powershell
.\build.bat
```
Artifacts will be placed inside the `dist/` directory.

---

## 📁 Repository Structure

```text
📁 AegisCore/
│
├── 📄 app.py                  # Application entry point (PyWebview + API Bridge)
├── 📄 vault_core.py            # Cryptographic engine (Argon2id, AES-GCM & atomic I/O)
├── 📄 build.bat               # Automated Windows packaging script
├── 📄 installer.iss           # Windows Installer script (Inno Setup)
├── 📄 iniciar_aegiscore.bat   # Python background launcher
├── 📄 requirements.txt        # Python dependency manifest
├── 📄 LICENSE                 # MIT Open Source License
├── 📄 aegiscore.ico           # High-resolution application icon
├── 📄 README.md               # English Documentation
├── 📄 README.pt-BR.md         # Portuguese Documentation
│
├── 📁 ui/                     # Native Web HUD
│   ├── 📄 index.html          # Semantic structure & modals
│   ├── 📄 style.css           # Tactical Imperial Bronze styling & Orbitron / Michroma typography
│   ├── 📄 app.js              # State management & pywebview bridge
│   └── 📄 logo.png            # AegisCore imperial bronze shield insignia
│
└── 📁 docs/screenshots/       # UI showcase images
```

---

## ⚖️ License & Open Source Auditing

This project is licensed under the [MIT License](./LICENSE).

In the domain of cybersecurity, transparency is imperative. Developers and security auditors are actively encouraged to review the implementation, submit pull requests, and report issues.

Copyright (c) 2026 Matheus Ventura.
