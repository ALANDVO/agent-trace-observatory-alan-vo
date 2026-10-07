"""SQLite persistence layer with parameterized queries, transactions, and migration logic."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

from app.core.config import settings


def get_db_path() -> str:
    """Resolve sqlite file path from database url."""
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        if path == ":memory:":
            return ":memory:"
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        return path
    return "traces.db"


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with row factory and foreign key enforcement."""
    path = get_db_path()
    conn = sqlite3.connect(path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables and default schema."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT UNIQUE NOT NULL, agent_name TEXT NOT NULL,
                status TEXT NOT NULL, root_goal TEXT NOT NULL, model TEXT NOT NULL,
                total_tokens INTEGER DEFAULT 0, prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0, duration_seconds REAL DEFAULT 0.0, step_count INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0, error_count INTEGER DEFAULT 0, redactions_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL, updated_at REAL NOT NULL, metadata_json TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT, span_id TEXT UNIQUE NOT NULL, trace_id TEXT NOT NULL,
                parent_span_id TEXT, span_name TEXT NOT NULL, span_type TEXT NOT NULL, model TEXT,
                input_data TEXT DEFAULT '', output_data TEXT DEFAULT '', redacted_input TEXT DEFAULT '', redacted_output TEXT DEFAULT '',
                status TEXT NOT NULL, error_message TEXT DEFAULT '', latency_ms REAL DEFAULT 0.0,
                prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0.0,
                start_time REAL NOT NULL, end_time REAL NOT NULL, step_index INTEGER DEFAULT 0,
                FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_name);
            CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
            CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at);
            CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, username TEXT NOT NULL,
                action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
                details TEXT DEFAULT '', ip_address TEXT DEFAULT '', created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT UNIQUE NOT NULL, dataset_name TEXT NOT NULL,
                sample_count INTEGER NOT NULL, accuracy REAL NOT NULL, loop_detection_f1 REAL NOT NULL,
                redaction_recall REAL NOT NULL, cost_mae REAL NOT NULL, failure_cls_f1 REAL NOT NULL,
                executed_at REAL NOT NULL, metrics_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS redaction_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT, rule_name TEXT UNIQUE NOT NULL, pattern TEXT NOT NULL,
                replacement TEXT NOT NULL, category TEXT NOT NULL, enabled INTEGER DEFAULT 1, created_at REAL NOT NULL
            );
        """)


def log_audit_event(
    user_id: str,
    username: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: str = "",
    ip_address: str = ""
) -> None:
    """Record an audit event."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (user_id, username, action, resource_type, resource_id, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, action, resource_type, resource_id, details, ip_address, time.time())
        )
