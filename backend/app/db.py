"""Supabase persistence. Falls back to in-memory storage when Supabase is not configured,
so the app still works for a demo without any database setup."""
import uuid
from datetime import datetime, timezone

from .config import SUPABASE_SERVICE_KEY, SUPABASE_URL

_sb = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    from supabase import create_client

    _sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

_mem_reports: dict[str, dict] = {}
_mem_messages: dict[str, list[dict]] = {}


def save_report(record: dict) -> str:
    if _sb:
        row = _sb.table("reports").insert(record).execute().data[0]
        return row["id"]
    rid = str(uuid.uuid4())
    _mem_reports[rid] = {"id": rid, "created_at": datetime.now(timezone.utc).isoformat(), **record}
    return rid


def get_report(report_id: str) -> dict | None:
    if _sb:
        data = _sb.table("reports").select("*").eq("id", report_id).limit(1).execute().data
        return data[0] if data else None
    return _mem_reports.get(report_id)


def add_message(report_id: str, role: str, content: str) -> None:
    if _sb:
        _sb.table("chat_messages").insert({"report_id": report_id, "role": role, "content": content}).execute()
        return
    _mem_messages.setdefault(report_id, []).append({"role": role, "content": content})


def get_messages(report_id: str, limit: int) -> list[dict]:
    if _sb:
        rows = (
            _sb.table("chat_messages")
            .select("role,content,created_at")
            .eq("report_id", report_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return list(reversed(rows))
    return _mem_messages.get(report_id, [])[-limit:]
