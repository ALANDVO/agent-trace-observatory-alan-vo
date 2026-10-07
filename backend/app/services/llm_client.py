"""Multi-provider LLM adapter with bounded timeouts, redaction, and deterministic offline fallback."""

import json
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.models.schemas import AdvisoryLLMResponse, FailureAnalysis, TraceSummaryResponse
from app.services.redaction import redaction_engine


class LLMClient:
    """Grounded advisory assistant supporting OpenAI-compatible, Anthropic, Gemini, and Ollama."""

    @classmethod
    async def generate_trace_explanation(
        cls,
        summary: TraceSummaryResponse,
        analysis: FailureAnalysis,
        spans: List[Dict[str, Any]],
        custom_prompt: Optional[str] = None
    ) -> AdvisoryLLMResponse:
        """Produce grounded root cause explanation via configured provider or deterministic fallback."""
        grounded_facts = [
            f"Agent: {summary.agent_name}",
            f"Trace Status: {summary.status.value}",
            f"Total Tokens: {summary.total_tokens} (Prompt: {summary.prompt_tokens}, Completion: {summary.completion_tokens})",
            f"Duration: {summary.duration_seconds:.2f}s | Steps: {summary.step_count} | Tool Calls: {summary.tool_call_count}",
            f"Deterministic Primary Diagnosis: {analysis.primary_failure.value} (Confidence: {analysis.confidence * 100:.1f}%)",
            f"Anomaly Score: {analysis.anomaly_score:.3f} | Token Waste Ratio: {analysis.token_waste_ratio * 100:.1f}%",
            f"Retry Loops Detected: {analysis.retry_count}",
            f"Root Cause Span: {analysis.root_cause_span_id or 'None'} (Tool: {analysis.root_cause_tool or 'None'})",
        ]

        # Add failed span error messages
        failed_spans = [s for s in spans if s.get("status") in ("error", "retrying") or bool(s.get("error_message"))]
        for idx, s in enumerate(failed_spans[:5]):
            err_msg, _ = redaction_engine.redact_text(str(s.get("error_message", "Unknown error")))
            grounded_facts.append(f"Failure Evidence #{idx + 1} [{s.get('span_name')}]: {err_msg[:200]}")

        # If no LLM key configured, provide high-quality deterministic offline report
        if not settings.llm_api_key:
            return cls._generate_offline_fallback(summary, analysis, grounded_facts)

        # Prepare sanitized prompt
        system_instruction = (
            "You are an expert AI agent reliability engineer. Analyze the provided trace evidence and "
            "explain the root cause of the agent's behavior. Only use facts present in the evidence. "
            "Do not fabricate external events. Highlight tool cascades, retry oscillation, and token waste."
        )

        user_content = (
            f"Trace Investigation Evidence:\n" +
            "\n".join([f"- {fact}" for fact in grounded_facts]) +
            f"\n\nSuggested Remediation: {analysis.suggested_remediation}"
        )
        if custom_prompt:
            sanitized_custom, _ = redaction_engine.redact_text(custom_prompt)
            user_content += f"\nOperator Inquiry: {sanitized_custom}"

        provider = settings.llm_provider.lower().strip()
        model = settings.llm_model
        base_url = settings.llm_base_url.rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                if provider in ("openai-compatible", "openai", "litellm", "openrouter"):
                    url = f"{base_url}/chat/completions"
                    hdrs = {"Authorization": f"Bearer {settings.llm_api_key}"}
                    body = {"model": model, "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_content}], "temperature": 0.2, "max_tokens": 800}
                    resp = await client.post(url, headers={"Content-Type": "application/json", **hdrs}, json=body)
                    resp.raise_for_status()
                    markdown_text = resp.json()["choices"][0]["message"]["content"]
                elif provider == "anthropic":
                    url = f"{base_url}/v1/messages"
                    hdrs = {"x-api-key": settings.llm_api_key, "anthropic-version": "2023-06-01"}
                    body = {"model": model, "system": system_instruction, "messages": [{"role": "user", "content": user_content}], "max_tokens": 800, "temperature": 0.2}
                    resp = await client.post(url, headers={"Content-Type": "application/json", **hdrs}, json=body)
                    resp.raise_for_status()
                    markdown_text = resp.json()["content"][0]["text"]
                elif provider == "gemini":
                    url = f"{base_url}/v1beta/models/{model}:generateContent?key={settings.llm_api_key}"
                    body = {"contents": [{"parts": [{"text": f"{system_instruction}\n\n{user_content}"}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800}}
                    resp = await client.post(url, headers={"Content-Type": "application/json"}, json=body)
                    resp.raise_for_status()
                    markdown_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif provider == "ollama":
                    url = f"{base_url}/api/chat"
                    body = {"model": model, "messages": [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_content}], "stream": False}
                    resp = await client.post(url, headers={"Content-Type": "application/json"}, json=body)
                    resp.raise_for_status()
                    markdown_text = resp.json()["message"]["content"]
                else:
                    return cls._generate_offline_fallback(
                        summary, analysis, grounded_facts,
                        notice_prefix=f"Unsupported provider '{provider}'. Delivered deterministic analysis."
                    )

            sanitized_markdown, _ = redaction_engine.redact_text(markdown_text)
            return AdvisoryLLMResponse(
                trace_id=summary.trace_id,
                provider=provider,
                model=model,
                is_offline_fallback=False,
                grounded_evidence=grounded_facts,
                explanation_markdown=sanitized_markdown,
                generated_at=time.time()
            )

        except Exception as exc:
            # Clear error reporting without crashing; fall back gracefully to deterministic analysis
            sanitized_err, _ = redaction_engine.redact_text(str(exc))
            return cls._generate_offline_fallback(
                summary,
                analysis,
                grounded_facts,
                notice_prefix=f"Upstream provider connection error ({sanitized_err[:120]}). Generated deterministic offline advisory."
            )

    @classmethod
    def _generate_offline_fallback(
        cls,
        summary: TraceSummaryResponse,
        analysis: FailureAnalysis,
        grounded_facts: List[str],
        notice_prefix: Optional[str] = None
    ) -> AdvisoryLLMResponse:
        md_lines = [
            "### Advisory Root-Cause Diagnosis (Offline Deterministic Core)",
            f"**Trace Assessment**: `{summary.agent_name}` ended with `{summary.status.value}` | Pattern: `{analysis.primary_failure.value}` ({analysis.confidence * 100:.1f}%)",
            f"**Metrics**: Cost: ${summary.total_cost_usd:.5f} | Tokens: {summary.total_tokens:,} | Anomaly Score: {analysis.anomaly_score:.3f} | Retries: {analysis.retry_count}",
            f"**Remediation**: {analysis.suggested_remediation}",
            "#### Grounded Trace Observations:"
        ] + [f"- {fact}" for fact in grounded_facts]

        return AdvisoryLLMResponse(
            trace_id=summary.trace_id,
            provider="deterministic-offline-core",
            model="heuristic-engine",
            is_offline_fallback=True,
            grounded_evidence=grounded_facts,
            explanation_markdown="\n".join(md_lines),
            generated_at=time.time(),
            notice=notice_prefix or "Offline deterministic core report. Configured provider API key is absent."
        )


llm_client = LLMClient()
