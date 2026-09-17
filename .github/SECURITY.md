# Security Policy

## 🛡️ AegisCore Security Commitment

AegisCore is an open-source, local-first password vault. Because users entrust this application with confidential credentials, security and cryptographic integrity are our highest priorities.

---

## 🔒 Supported Versions

Only the latest stable release receives active security patches.

| Version | Supported          |
| :---    | :---               |
| 1.x.x   | :white_check_mark: |
| < 1.0.0 | :x:                |

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability, cryptographic weakness, or memory safety defect in AegisCore, **please do not disclose it publicly** through public GitHub issues or discussions.

### Preferred Disclosure Method:
1. **GitHub Private Vulnerability Reporting:**  
   Navigate to the [Security Advisories](https://github.com/MatheusgVentura/AegisCore/security/advisories) tab of this repository and click **"Report a vulnerability"**. This creates a secure, private disclosure workspace between you and the maintainers.
2. **Direct Security Contact:**  
   Alternatively, you can reach out directly via email to: `matheusgventura10@gmail.com` with the subject tag `[SECURITY: AegisCore]`.

### What to Include in Your Report:
- A clear description of the vulnerability and its potential impact.
- Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
- Proposed mitigation or patch (if available).
- Your preferred name/handle for public credit and acknowledgment once resolved.

---

## 🛑 Security Boundaries & Threat Model

AegisCore's threat model assumes:
1. **Zero Outbound Telemetry:** AegisCore must never perform outbound HTTP/socket network connections to transmit credentials or vault data. Any PR introducing outbound network calls with sensitive payloads is considered a critical security violation.
2. **Cryptographic Standards:** All keys must be derived via `Argon2id` (min. 64 MB memory cost) and encrypted via `AES-256-GCM` (AEAD).
3. **Atomic File I/O:** Database files must be flushed with `os.fsync()` before atomic file replacement to prevent data corruption.
4. **RAM Sanitization:** Sensitive plaintext credentials must be cleared from memory when locking the vault, and clipboard contents must be scrubbed automatically within 15 seconds.
