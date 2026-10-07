"""High-performance deterministic redaction and secret sanitization engine."""

import re
from typing import Dict, List, Pattern, Tuple
from app.models.schemas import RedactionMatch, RedactionReport


def luhn_checksum_valid(card_number_str: str) -> bool:
    """Validate credit card number using Luhn algorithm."""
    digits = [int(d) for d in re.sub(r"\D", "", card_number_str)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for idx, d in enumerate(reverse_digits):
        if idx % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class RedactionEngine:
    """Deterministic pattern-matching engine for secrets and PII redaction."""

    # Pre-compiled high-confidence regular expressions
    PATTERNS: List[Tuple[str, str, Pattern[str]]] = [
        # LLM and Cloud API Credentials
        ("ANTHROPIC_KEY", "SECRET_KEY", re.compile(r"\b(?:sk-ant-[A-Za-z0-9_-]{20,})\b")),
        ("OPENAI_KEY", "SECRET_KEY", re.compile(r"\b(?:sk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{20,})\b")),
        ("GITHUB_PAT", "SECRET_KEY", re.compile(r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,})\b")),
        ("AWS_ACCESS_KEY", "SECRET_KEY", re.compile(r"\b(?:AKIA[0-9A-Z]{16})\b")),
        ("BEARER_TOKEN", "SECRET_KEY", re.compile(r"\bBearer\s+([A-Za-z0-9\-._~+/]+=*)\b", re.IGNORECASE)),
        ("JWT_TOKEN", "SECRET_KEY", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
        ("GENERIC_API_KEY", "SECRET_KEY", re.compile(r"""(?i)(?:api_key|apikey|secret_key|auth_token)["']?\s*[:=]\s*["']?([A-Za-z0-9_\-]{16,})["']?""")),
        ("SLACK_TOKEN", "SECRET_KEY", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),

        # Personally Identifiable Information (PII)
        ("EMAIL", "PII", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
        ("US_SSN", "PII", re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
        ("IPV4_ADDRESS", "NETWORK_PII", re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")),
        ("CREDIT_CARD", "FINANCIAL_PII", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"))
    ]

    def redact_text(self, text: str) -> Tuple[str, List[RedactionMatch]]:
        """Redact sensitive occurrences in raw text and record matches."""
        if not text:
            return "", []

        matches: List[RedactionMatch] = []
        sanitized = text

        for name, category, pattern in self.PATTERNS:
            for match in list(pattern.finditer(sanitized)):
                original_snippet = match.group(0)

                # Extra validation for potential credit cards
                if name == "CREDIT_CARD" and not luhn_checksum_valid(original_snippet):
                    continue

                # Extra validation for localhost / private non-sensitive IPs
                if name == "IPV4_ADDRESS" and original_snippet in ("127.0.0.1", "0.0.0.0"):
                    continue

                replacement = f"[REDACTED:{name}]"
                matches.append(
                    RedactionMatch(
                        category=category,
                        pattern_name=name,
                        original_snippet=original_snippet[:4] + "..." if len(original_snippet) > 8 else "***",
                        redacted_snippet=replacement,
                        start_pos=match.start(),
                        end_pos=match.end()
                    )
                )

            # Replace pattern occurrences
            if name == "CREDIT_CARD":
                def replace_cc(m: re.Match[str]) -> str:
                    val = m.group(0)
                    return f"[REDACTED:{name}]" if luhn_checksum_valid(val) else val
                sanitized = pattern.sub(replace_cc, sanitized)
            elif name == "IPV4_ADDRESS":
                def replace_ip(m: re.Match[str]) -> str:
                    val = m.group(0)
                    return val if val in ("127.0.0.1", "0.0.0.0") else f"[REDACTED:{name}]"
                sanitized = pattern.sub(replace_ip, sanitized)
            elif name == "BEARER_TOKEN":
                sanitized = pattern.sub(r"Bearer [REDACTED:BEARER_TOKEN]", sanitized)
            elif name == "GENERIC_API_KEY":
                sanitized = pattern.sub(r'api_key="[REDACTED:API_KEY]"', sanitized)
            else:
                sanitized = pattern.sub(f"[REDACTED:{name}]", sanitized)

        return sanitized, matches

    def generate_report(self, all_matches: List[RedactionMatch]) -> RedactionReport:
        """Aggregate detection metrics from collected matches."""
        categories: Dict[str, int] = {}
        for m in all_matches:
            categories[m.category] = categories.get(m.category, 0) + 1

        return RedactionReport(
            total_redactions=len(all_matches),
            categories_detected=categories,
            sanitized=len(all_matches) > 0,
            details=all_matches[:100]  # Cap at 100 for safety and payload size
        )


redaction_engine = RedactionEngine()
