# Changelog

All notable changes to the Agent Trace Observatory project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
