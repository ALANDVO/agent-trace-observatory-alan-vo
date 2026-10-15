# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

custom-redaction-rules

## Roadmap

### custom-redaction-rules — Custom Redaction Rules Management

Status: done

Acceptance:
- Admin users can create, list, update, and delete custom redaction patterns via REST API
- Custom rules are applied during trace ingestion alongside built-in patterns
- Custom rules support regex pattern, category, type, and enable/disable toggle
- Frontend provides a management interface for custom redaction rules (admin only)
- Rules persist across restarts via database storage
- Built-in patterns remain functional and take precedence for standard credential formats

Implementation: `backend/app/core/database.py (schema migration)`, `backend/app/models/schemas.py (new schemas)`, `backend/app/services/redaction.py (custom rules integration)`, `backend/app/api/routes/redaction.py (new routes file)`, `backend/app/main.py (mount new router)`, `backend/app/core/seed.py (seed default custom rules)`, `frontend/src/api.ts (redaction API client)`, `frontend/src/types.ts (redaction types)`, `frontend/src/components/RedactionRulesManager.tsx (new component)`, `frontend/src/App.tsx (integrate component)`

Tests: `backend/tests/test_redaction_rules.py (new test file)`, `frontend/src/test/RedactionRulesManager.test.tsx (new test file)`

