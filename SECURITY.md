# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## Reporting a Vulnerability

We take the security of **StockWise Agents** seriously. If you believe you have discovered a security vulnerability or credential leak, please report it responsibly.

### Disclosure Protocol
- **Do not** file public GitHub issues for security vulnerabilities or exposed secrets.
- Please open a private GitHub Security Advisory via your repository fork, or contact the project maintainers directly through your designated repository owner channel.
- Provide a detailed description of the vulnerability, reproduction steps, and potential impact.
- We will acknowledge receipt within 48 hours and work with you to test and deploy a fix prior to public disclosure.

---

## Architecture Safeguards

StockWise Agents implements multiple built-in security and financial guardrails:
1. **Local-Only Credentials**: Secrets such as Agentverse mailbox keys, agent seeds, and LLM API keys are loaded strictly from environment variables (`.env`) and are never checked into version control.
2. **Approval Safeguards**: The system does not support automatic financial transactions or vendor ordering. All generated purchase orders remain in `pending_approval` until reviewed by an authorized human actor.
3. **Simulated Vendor Dispatch**: Vendor placement operates in simulated test mode (`simulated_placed`); no real funds, credit cards, bank accounts, or external supplier purchasing APIs are invoked.
4. **Immutable Audit Trail**: All state transitions (`draft` → `pending_approval` → `approved` → `simulated_placed` / `rejected`) are immutably logged with actor identifiers and timestamps in SQLite.
