"""High-performance deterministic redaction engine."""
import re, time
from typing import Dict, List, Pattern, Tuple
from app.core.database import get_db
from app.models.schemas import RedactionMatch, RedactionReport

def luhn(s: str) -> bool:
    d = [int(x) for x in re.sub(r"\D", "", s)]
    if len(d) < 13 or len(d) > 19: return False
    c = 0
    for i, v in enumerate(d[::-1]):
        if i % 2: c += (v*2 - 9 if v*2 > 9 else v*2)
        else: c += v
    return c % 10 == 0

luhn_checksum_valid = luhn  # alias for tests

BUILTIN = [
    ("ANTHROPIC_KEY","SECRET_KEY",re.compile(r"\b(?:sk-ant-[A-Za-z0-9_-]{20,})\b")),
    ("OPENAI_KEY","SECRET_KEY",re.compile(r"\b(?:sk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{20,})\b")),
    ("GITHUB_PAT","SECRET_KEY",re.compile(r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("AWS_ACCESS_KEY","SECRET_KEY",re.compile(r"\b(?:AKIA[0-9A-Z]{16})\b")),
    ("BEARER_TOKEN","SECRET_KEY",re.compile(r"\bBearer\s+([A-Za-z0-9\-._~+/]+=*)\b", re.I)),
    ("JWT_TOKEN","SECRET_KEY",re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("GENERIC_API_KEY","SECRET_KEY",re.compile(r"""(?i)(?:api_key|apikey|secret_key|auth_token)["']?\s*[:=]\s*["']?([A-Za-z0-9_\-]{16,})["']?""")),
    ("SLACK_TOKEN","SECRET_KEY",re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("EMAIL","PII",re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("US_SSN","PII",re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("IPV4_ADDRESS","NETWORK_PII",re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")),
    ("CREDIT_CARD","FINANCIAL_PII",re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"))
]

class RedactionEngine:
    _cache: List[Tuple[str,str,Pattern[str],str]] = []
    _ts: float = 0
    _ttl: float = 60

    @classmethod
    def _load(cls) -> List[Tuple[str,str,Pattern[str],str]]:
        now = time.time()
        if cls._cache and now - cls._ts < cls._ttl: return cls._cache
        out = []
        try:
            with get_db() as c:
                for r in c.execute("SELECT rule_name,pattern,replacement,category FROM redaction_rules WHERE enabled=1 AND is_builtin=0").fetchall():
                    try: out.append((r["rule_name"], r["category"], re.compile(r["pattern"]), r["replacement"]))
                    except re.error: pass
        except: pass
        cls._cache, cls._ts = out, now
        return out

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache, cls._ts = [], 0

    def _patterns(self) -> List[Tuple[str,str,Pattern[str],str,bool]]:
        return [(n,c,p,r,True) for n,c,p,r in self._load()] + [(n,c,p,f"[REDACTED:{n}]",False) for n,c,p in BUILTIN]

    def redact_text(self, text: str) -> Tuple[str, List[RedactionMatch]]:
        if not text: return "", []
        m: List[Tuple[int,int,str,str,str,bool,callable]] = []
        cs: List[Tuple[int,int]] = []
        for n,c,p,r,ic in self._patterns():
            for x in p.finditer(text):
                v = x.group()
                if n=="CREDIT_CARD" and not luhn(v): continue
                if n=="IPV4_ADDRESS" and v in ("127.0.0.1","0.0.0.0"): continue
                fn = lambda _, rv=r: rv
                if n=="CREDIT_CARD": fn = lambda m, nn=n: f"[REDACTED:{nn}]" if luhn(m.group()) else m.group()
                elif n=="IPV4_ADDRESS": fn = lambda m: m.group() if m.group() in ("127.0.0.1","0.0.0.0") else f"[REDACTED:{n}]"
                elif n=="BEARER_TOKEN": fn = lambda _: "Bearer [REDACTED:BEARER_TOKEN]"
                elif n=="GENERIC_API_KEY": fn = lambda _: 'api_key="[REDACTED:API_KEY]"'
                m.append((x.start(), x.end(), n, c, r, ic, fn))
                if ic: cs.append((x.start(), x.end()))
        fl = []
        for s,e,n,c,r,ic,fn in m:
            if not ic and any(not (e <= a or s >= b) for a,b in cs): continue
            fl.append((s,e,n,c,r,ic,fn))
        fl.sort(key=lambda x: (x[0], -(x[1]-x[0])))
        fnl, le = [], -1
        for s,e,n,c,r,ic,fn in fl:
            if s >= le:
                fnl.append((s,e,n,c,r,ic,fn))
                le = e
        om = [RedactionMatch(category=c, pattern_name=n, original_snippet=text[s:e][:4]+"..." if e-s>8 else "***", redacted_snippet=r, start_pos=s, end_pos=e) for s,e,n,c,r,_,_ in fnl]
        san = text
        for s,e,_,_,_,_,fn in reversed(fnl):
            san = san[:s] + fn(type('M',(),{'group':lambda _: text[s:e]})()) + san[e:]
        return san, om

    def generate_report(self, ms: List[RedactionMatch]) -> RedactionReport:
        cat: Dict[str,int] = {}
        for x in ms: cat[x.category] = cat.get(x.category,0)+1
        return RedactionReport(total_redactions=len(ms), categories_detected=cat, sanitized=len(ms)>0, details=ms[:100])

redaction_engine = RedactionEngine()