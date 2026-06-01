"""Admin dashboard statistics routes — usage metrics for site maintainers."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func

from .. import state
from ..auth.middleware import require_admin
from ..configdb.base import scoped_session
from ..configdb.models.user import User
from ..configdb.models.session import Session, Message
from ..configdb.models.token import TokenUsage

router = APIRouter()


class OverviewStats(BaseModel):
    total_users: int
    total_sessions: int
    total_messages: int
    today_logins: int
    today_questions: int
    today_token_prompt: int
    today_token_completion: int
    today_token_total: int


class TrendPoint(BaseModel):
    date: str
    value: int


class TrendsData(BaseModel):
    active_users: list[TrendPoint]
    questions: list[TrendPoint]
    token_usage: list[TrendPoint]


class TopUser(BaseModel):
    username: str
    question_count: int
    last_active: str


class ModelUsage(BaseModel):
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    call_count: int


class AdminStatsResponse(BaseModel):
    overview: OverviewStats
    trends: TrendsData
    top_users: list[TopUser]
    model_usage: list[ModelUsage]


def _today_start() -> float:
    """Return Unix timestamp for 00:00:00 UTC today."""
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()


def _days_ago_timestamp(days: int) -> float:
    """Return Unix timestamp for 00:00:00 UTC N days ago."""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return (start.timestamp() - days * 86400)


def _iso_today_start() -> str:
    """Return ISO format string for 00:00:00 UTC today."""
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).isoformat()


def _date_list(days: int) -> list[str]:
    """Generate a list of date strings for the trend period (oldest first)."""
    result: list[str] = []
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    for i in range(days - 1, -1, -1):
        d = start - timedelta(days=i)
        result.append(d.strftime("%Y-%m-%d"))
    return result


@router.get("/api/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days for trend data"),
    _admin: dict = Depends(require_admin),
) -> AdminStatsResponse:
    """Return system operation statistics for admin dashboard.

    Includes overview counts, daily trends, top active users, and model usage.
    """
    try:
        with scoped_session() as session:
            today_start_ts = _today_start()
            today_start_iso = _iso_today_start()

            # --- Overview ---
            total_users = session.query(User).count()
            total_sessions = session.query(Session).count()
            total_messages = session.query(Message).count()

            today_logins = session.query(User).filter(
                User.last_login_at.isnot(None),
                User.last_login_at >= today_start_iso,
            ).count()

            today_questions = session.query(Message).filter(
                Message.role == "user",
                Message.created_at >= today_start_ts,
            ).count()

            token_row = session.query(
                func.coalesce(func.sum(TokenUsage.prompt), 0).label("prompt"),
                func.coalesce(func.sum(TokenUsage.completion), 0).label("completion"),
                func.coalesce(func.sum(TokenUsage.total), 0).label("total"),
            ).filter(TokenUsage.created_at >= today_start_ts).first()
            today_token_prompt = token_row.prompt if token_row else 0
            today_token_completion = token_row.completion if token_row else 0
            today_token_total = token_row.total if token_row else 0

            # --- Trends ---
            dates = _date_list(days)
            active_users: list[TrendPoint] = []
            questions: list[TrendPoint] = []
            token_usage_list: list[TrendPoint] = []

            for date_str in dates:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                day_start_ts = date_obj.timestamp()
                day_end_ts = (date_obj + timedelta(days=1)).timestamp()
                day_start_iso = date_obj.isoformat()
                day_end_iso = (date_obj + timedelta(days=1)).isoformat()

                au = session.query(User).filter(
                    User.last_login_at.isnot(None),
                    User.last_login_at >= day_start_iso,
                    User.last_login_at < day_end_iso,
                ).count()

                q = session.query(Message).filter(
                    Message.role == "user",
                    Message.created_at >= day_start_ts,
                    Message.created_at < day_end_ts,
                ).count()

                t_row = session.query(
                    func.coalesce(func.sum(TokenUsage.total), 0)
                ).filter(
                    TokenUsage.created_at >= day_start_ts,
                    TokenUsage.created_at < day_end_ts,
                ).first()
                tokens = t_row[0] if t_row else 0

                active_users.append(TrendPoint(date=date_str, value=au))
                questions.append(TrendPoint(date=date_str, value=q))
                token_usage_list.append(TrendPoint(date=date_str, value=tokens))

            # --- Top users ---
            user_question_map: dict[str, dict] = {}
            top_rows = session.query(
                Message.created_at, User.username
            ).join(
                Session, Message.session_id == Session.id
            ).join(
                User, Session.user_id == User.id
            ).filter(
                Message.role == "user"
            ).order_by(Message.created_at.desc()).all()

            for created_at, username in top_rows:
                if username not in user_question_map:
                    user_question_map[username] = {"count": 0, "last_active": created_at}
                user_question_map[username]["count"] += 1
                if created_at > user_question_map[username]["last_active"]:
                    user_question_map[username]["last_active"] = created_at

            sorted_users = sorted(user_question_map.items(), key=lambda x: -x[1]["count"])[:10]
            top_users_list = [
                TopUser(
                    username=username,
                    question_count=info["count"],
                    last_active=_format_ts(info["last_active"]),
                )
                for username, info in sorted_users
            ]

            # --- Model usage ---
            model_rows = session.query(
                TokenUsage.model,
                func.coalesce(func.sum(TokenUsage.prompt), 0),
                func.coalesce(func.sum(TokenUsage.completion), 0),
                func.coalesce(func.sum(TokenUsage.total), 0),
                func.count(TokenUsage.id),
            ).group_by(TokenUsage.model).order_by(func.count(TokenUsage.id).desc()).all()

            model_usage_list = [
                ModelUsage(
                    model=row[0],
                    prompt_tokens=row[1],
                    completion_tokens=row[2],
                    total_tokens=row[3],
                    call_count=row[4],
                )
                for row in model_rows
            ]

            return AdminStatsResponse(
                overview=OverviewStats(
                    total_users=total_users,
                    total_sessions=total_sessions,
                    total_messages=total_messages,
                    today_logins=today_logins,
                    today_questions=today_questions,
                    today_token_prompt=today_token_prompt,
                    today_token_completion=today_token_completion,
                    today_token_total=today_token_total,
                ),
                trends=TrendsData(
                    active_users=active_users,
                    questions=questions,
                    token_usage=token_usage_list,
                ),
                top_users=top_users_list,
                model_usage=model_usage_list,
            )
    except Exception:
        return AdminStatsResponse(
            overview=OverviewStats(
                total_users=0, total_sessions=0, total_messages=0,
                today_logins=0, today_questions=0,
                today_token_prompt=0, today_token_completion=0, today_token_total=0,
            ),
            trends=TrendsData(active_users=[], questions=[], token_usage=[]),
            top_users=[],
            model_usage=[],
        )


def _format_ts(ts: float | str) -> str:
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    return str(ts)
