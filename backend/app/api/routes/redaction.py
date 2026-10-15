"""Redaction rules API."""
import re, time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from app.core.database import get_db, log_audit_event
from app.core.security import Role, UserSession, require_role
from app.services.redaction import redaction_engine

router = APIRouter(prefix="/redaction/rules", tags=["redaction"])

class R(BaseModel):
    rule_name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    pattern: str = Field(..., min_length=1, max_length=500)
    replacement: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)
    pattern_type: str = Field(default="regex", pattern="^(regex|literal)$")
    enabled: bool = True
    id: int = 0; is_builtin: bool = False; created_at: float = 0; updated_at: float = 0
    class Config: from_attributes = True

class U(BaseModel):
    pattern: Optional[str] = Field(None, min_length=1, max_length=500)
    replacement: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    pattern_type: Optional[str] = Field(None, pattern="^(regex|literal)$")
    enabled: Optional[bool] = None

class T(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=500)
    pattern_type: str = Field(default="regex", pattern="^(regex|literal)$")
    sample_text: str = Field(..., max_length=10000)

class TR(BaseModel):
    matches: List[Dict[str, Any]]
    sanitized_text: str
    pattern_valid: bool
    error: Optional[str] = None

def _v(p: str) -> None:
    try: re.compile(p)
    except re.error as e: raise HTTPException(400, f"Invalid regex: {e}")

@router.get("", response_model=List[R])
async def lr(user: UserSession = Depends(require_role(Role.VIEWER))):
    with get_db() as c: return [dict(r) for r in c.execute("SELECT * FROM redaction_rules ORDER BY is_builtin DESC, rule_name").fetchall()]

@router.post("", response_model=R, status_code=201)
async def cr(r: R, rq: Request, u: UserSession = Depends(require_role(Role.ADMIN))):
    _v(r.pattern)
    with get_db() as conn:
        cur = conn.cursor()
        if cur.execute("SELECT 1 FROM redaction_rules WHERE rule_name=?", (r.rule_name,)).fetchone(): raise HTTPException(409, f"Rule '{r.rule_name}' exists")
        n = time.time()
        cur.execute("""INSERT INTO redaction_rules(rule_name,pattern,replacement,category,pattern_type,is_builtin,enabled,created_at,updated_at) VALUES(?,?,?,?,?,0,?,?,?)""", (r.rule_name, r.pattern, r.replacement, r.category, r.pattern_type, int(r.enabled), n, n))
        i = cur.lastrowid
    redaction_engine.invalidate_cache()
    log_audit_event(u.user_id, u.username, "CREATE_REDACTION_RULE", "redaction_rule", str(i), f"Created '{r.rule_name}'", rq.client.host if rq.client else "")
    with get_db() as c: return dict(c.execute("SELECT * FROM redaction_rules WHERE id=?", (i,)).fetchone())

@router.put("/{i}", response_model=R)
async def ur(i: int, u: U, rq: Request, usr: UserSession = Depends(require_role(Role.ADMIN))):
    with get_db() as c: row = c.execute("SELECT * FROM redaction_rules WHERE id=?", (i,)).fetchone()
    if not row: raise HTTPException(404, "Not found")
    if row["is_builtin"]: raise HTTPException(403, "Cannot modify built-in")
    if u.pattern: _v(u.pattern)
    s, p = [], []
    for k, v in u.model_dump(exclude_unset=True).items(): s.append(f"{k}=?"); p.append(int(v) if k=="enabled" else v)
    if not s: raise HTTPException(400, "No fields")
    s.append("updated_at=?"); p.append(time.time()); p.append(i)
    with get_db() as c:
        c.execute(f"UPDATE redaction_rules SET {','.join(s)} WHERE id=?", p)
        row = c.execute("SELECT * FROM redaction_rules WHERE id=?", (i,)).fetchone()
    redaction_engine.invalidate_cache()
    log_audit_event(usr.user_id, usr.username, "UPDATE_REDACTION_RULE", "redaction_rule", str(i), f"Updated '{row['rule_name']}'", rq.client.host if rq.client else "")
    return dict(row)

@router.delete("/{i}", status_code=204)
async def dr(i: int, rq: Request, u: UserSession = Depends(require_role(Role.ADMIN))):
    with get_db() as c: row = c.execute("SELECT * FROM redaction_rules WHERE id=?", (i,)).fetchone()
    if not row: raise HTTPException(404, "Not found")
    if row["is_builtin"]: raise HTTPException(403, "Cannot delete built-in")
    with get_db() as c: c.execute("DELETE FROM redaction_rules WHERE id=?", (i,))
    redaction_engine.invalidate_cache()
    log_audit_event(u.user_id, u.username, "DELETE_REDACTION_RULE", "redaction_rule", str(i), f"Deleted '{row['rule_name']}'", rq.client.host if rq.client else "")

@router.post("/test", response_model=TR)
async def tr(t: T, u: UserSession = Depends(require_role(Role.ANALYST))):
    try:
        p = re.compile(t.pattern) if t.pattern_type=="regex" else re.compile(re.escape(t.pattern))
        m = [{"match":x.group(),"start":x.start(),"end":x.end()} for x in p.finditer(t.sample_text)]
        return TR(matches=m, sanitized_text=p.sub("[REDACTED]", t.sample_text), pattern_valid=True)
    except re.error as e: return TR(matches=[], sanitized_text=t.sample_text, pattern_valid=False, error=str(e))