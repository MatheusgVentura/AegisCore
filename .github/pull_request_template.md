## Description
<!-- Please explain the motivation, context, and details of your change. -->

---

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change fixing an issue)
- [ ] ✨ New feature (non-breaking change adding functionality)
- [ ] 🎨 UI / UX refinement
- [ ] ⚡ Performance optimization
- [ ] 🔒 Security hardening
- [ ] 📝 Documentation update

---

## 🛡️ Mandatory Security Checklist
*Because AegisCore is a security-critical password vault, all Pull Requests must comply with these rules:*

- [ ] **No Outbound Data Leaks:** This change introduces NO telemetry, background tracking, analytics, or outbound HTTP/socket transmission of credentials or vault files.
- [ ] **Dependency Audit:** No unverified, untrusted, or vulnerable third-party dependencies were introduced into `requirements.txt`.
- [ ] **Cryptographic Invariance:** The Argon2id KDF and AES-256-GCM AEAD encryption engines remain unmodified or strictly hardened.
- [ ] **Atomic I/O:** Disk persistence remains atomic and guarded with `os.fsync()`.
- [ ] **Memory & Clipboard Safety:** Plaintext credentials are cleared upon vault lock, and clipboard auto-wipe is respected.
- [ ] **Local Testing:** I have tested the application locally (`python app.py` and/or `build.bat`) without errors.
