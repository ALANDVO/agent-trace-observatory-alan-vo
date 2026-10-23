# Changelog

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to the Agent Trace Observatory project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-23

### Added
- Frontend test suite for Redaction Rules Manager component (`frontend/src/test/RedactionRulesManager.test.tsx`) covering rule table rendering, status badges, built-in indicators, edit/delete workflows, form cancellation, loading states, and error handling.
- 9 new frontend tests bringing total to 13 frontend tests and 48 total tests across the stack.

### Fixed
- Verified all 35 backend tests and 13 frontend tests pass consistently.
- Confirmed production build succeeds for both backend and frontend Docker images.

## [1.1.0] - 2026-10-15

### Added
- Custom redaction rules management: admin users can create, list, update, and delete custom regex/literal patterns for secret and PII detection via REST API (`/api/redaction/rules`).
- Custom rules applied during trace ingestion with precedence over built-in patterns for organization-specific formats.
- Pattern tester endpoint (`POST /api/redaction/rules/test`) for validating patterns against sample text before deployment.
- Frontend Redaction Rules Manager component with table view, create/edit modal, and interactive pattern tester (admin only).
- Database schema extension with `redaction_rules` table supporting pattern name, regex/literal pattern, replacement text, category, type, enabled toggle, and built-in flag.
- Seeded demo rules: internal API keys (`INT_API_`), custom session tokens (`SESS_`), and database connection strings.
- Role-based access: admin write, analyst pattern testing, viewer read-only.

### Changed
- Redaction engine now loads custom rules from database with 60-second cache TTL, invalidated on rule changes.
- Overlap resolution: custom rules take precedence over built-in patterns when matches overlap.

## [1.0.0] - 2026-10-07

### Added
- Core deterministic agent trace ingestion pipeline with automated secret and PII redaction (OpenAI, Anthropic, AWS, GitHub PAT, Bearer tokens, emails, SSN, IPv4, credit cards with Luhn checksum validation).
- Tool-call execution DAG builder with topological dependency analysis, cyclic retry loop detection, parallel fan-out tracking, and critical path latency calculation.
- Multi-model token cost accounting engine with pricing tables for OpenAI, Anthropic, Gemini, and Qwen models, calculating token waste ratios on retries and failures.
- Deterministic heuristic failure pattern classifier categorizing 10 distinct failure modes including context overflow, rate limit throttling, schema validation errors, and timeout backoff with anomaly scoring.
- Opt-in grounded advisory LLM assistant supporting OpenAI-compatible, Anthropic, Gemini, and Ollama adapters via httpx with strict redaction and deterministic offline fallback.
- Keycloak OIDC authentication integration with authorization code flow, PKCE S256, state/nonce validation, role-based access control (`viewer`, `analyst`, `admin`), CSRF token protection, and SAML identity brokering support.
- Fully typed React 18 + TypeScript + Vite frontend with dark-mode dashboard, interactive DAG visualization, span waterfall inspector, template importer, and CSV/JSON data export.
- Reproducible AI/ML benchmark evaluation suite with curated dataset of 12 multi-step agent trajectories and CLI evaluation command.
- Production-ready Dockerfiles with non-root users, healthchecks, and local docker compose deployment configuration.