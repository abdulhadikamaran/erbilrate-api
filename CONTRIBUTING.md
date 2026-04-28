# Contributing to ErbilRate API

Thank you for your interest in contributing. ErbilRate is an open API infrastructure project — the rate limiting, authentication, WebSocket system, and frontend are all open for improvement.

---

## What You Can Contribute

### High Priority
- **SDK clients** — Go, Swift, Kotlin, Ruby clients wrapping the REST API
- **Integration examples** — More language examples in `/examples`
- **Test coverage** — Expand `scripts/security_test_suite.py` with edge cases
- **Documentation** — Corrections, clarifications, translation improvements

### Out of Scope (Private Repo)
The following are part of the proprietary data pipeline and are not in this repository:
- Telegram connection and scraping logic
- Message parsing rules
- Sender allowlist configuration
- The live data pipeline internals

Please do not open issues requesting access to these components.

---

## How to Contribute

### 1. Fork and Clone
```bash
git clone https://github.com/YOUR_USERNAME/erbilrate-api
cd erbilrate-api
```

### 2. Create a Branch
```bash
git checkout -b feature/go-sdk
# or
git checkout -b fix/websocket-reconnect-example
```

### 3. Make Your Changes
- Keep PRs focused — one feature or fix per PR
- Add or update tests if relevant
- Update `CHANGELOG.md` under an `[Unreleased]` section

### 4. Run the Security Test Suite
Before submitting, make sure nothing is broken:
```bash
python -m scripts.security_test_suite
# Expected: 47/47 PASSED
```

### 5. Open a Pull Request
Write a clear description of what changed and why.

---

## Code Style

- Python: follow PEP 8, use type hints on all function signatures
- JavaScript: vanilla ES modules, no build tools required
- Comments: English only in code, Kurdish/Arabic acceptable in documentation

---

## Reporting Security Issues

**Do not open a public GitHub issue for security vulnerabilities.**

Email directly: `security@erbilrate.com`

Include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment

We aim to respond within 48 hours and patch within 7 days.

---

## Code of Conduct

Be professional. Be constructive. We're building something useful for the Kurdish and Iraqi developer community — let's keep it collaborative.
