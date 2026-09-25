"""Admin metrics, AI cost dashboard and user management."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.models import (
    AIUsage,
    ApiRequest,
    Course,
    Document,
    GenerationJob,
    Payment,
    Plan,
    Project,
    Subscription,
    UploadedFile,
    User,
    WhatsAppMessage,
)


async def metrics(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    teacher = User.role == "teacher"  # admins run the platform; they are not customers
    total_users = (await db.execute(select(func.count()).select_from(User).where(teacher))).scalar_one()
    active_users = (await db.execute(select(func.count()).select_from(User).where(
        teacher, User.last_login_at >= since))).scalar_one()
    live = (Subscription.status.in_(("active", "trialing", "past_due")),
            or_(Subscription.provider.notin_(("trial", "manual")), Subscription.current_period_end > func.now()))
    subs = (await db.execute(select(Subscription, Plan).join(Plan, Plan.code == Subscription.plan_code)
                             .join(User, User.id == Subscription.user_id).where(teacher, *live))).all()
    paying = [(s, p) for s, p in subs if s.provider in ("stripe", "dodo")]
    # Revenue counts only subscriptions paid through a gateway: trials and admin-granted plans earn nothing.
    mrr = sum(float(p.price_annual_aed) / 12 if s.interval == "year" else float(p.price_monthly_aed)
              for s, p in paying if s.status != "trialing")
    by_plan: dict[str, int] = {}
    for s, _ in paying:
        by_plan[s.plan_code] = by_plan.get(s.plan_code, 0) + 1
    trials = sum(1 for s, _ in subs if s.provider == "trial")
    granted = sum(1 for s, _ in subs if s.provider == "manual")
    trial_starts = (await db.execute(select(func.count()).select_from(Subscription).where(
        Subscription.provider == "trial", Subscription.created_at >= since))).scalar_one()
    converted = (await db.execute(select(func.count(func.distinct(Subscription.user_id))).where(
        Subscription.provider.in_(("stripe", "dodo")), Subscription.created_at >= since))).scalar_one()

    job_rows = (await db.execute(select(GenerationJob.type, GenerationJob.status, func.count()).where(
        GenerationJob.created_at >= since).group_by(GenerationJob.type, GenerationJob.status))).all()
    jobs: dict[str, dict[str, int]] = {}
    for t, st, c in job_rows:
        jobs.setdefault(t, {})[st] = c
    lesson_jobs = jobs.get("lesson_generation", {})
    success_rate = (lesson_jobs.get("succeeded", 0) / max(1, lesson_jobs.get("succeeded", 0) +
                                                           lesson_jobs.get("failed", 0)))
    avg_time = (await db.execute(select(func.avg(func.extract("epoch", GenerationJob.completed_at -
                                                              GenerationJob.started_at))).where(
        GenerationJob.type == "lesson_generation", GenerationJob.status == "succeeded",
        GenerationJob.created_at >= since))).scalar_one()
    ai = (await db.execute(select(func.coalesce(func.sum(AIUsage.cost_usd), 0), func.coalesce(
        func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0), func.count()).where(AIUsage.created_at >= since))
          ).one()
    storage = (await db.execute(select(func.coalesce(func.sum(UploadedFile.size_bytes), 0)))).scalar_one()
    wa = (await db.execute(select(WhatsAppMessage.direction, WhatsAppMessage.status, func.count()).where(
        WhatsAppMessage.created_at >= since).group_by(WhatsAppMessage.direction, WhatsAppMessage.status))).all()
    subjects = (await db.execute(select(Course.subject, func.count()).group_by(Course.subject)
                                 .order_by(func.count().desc()).limit(8))).all()
    grades = (await db.execute(select(Course.grade, func.count()).group_by(Course.grade)
                               .order_by(func.count().desc()).limit(8))).all()
    doc_kinds = (await db.execute(select(Document.kind, func.count()).group_by(Document.kind)
                                  .order_by(func.count().desc()))).all()
    projects = (await db.execute(select(func.count()).select_from(Project))).scalar_one()
    recent = (await db.execute(select(User).where(teacher).order_by(User.created_at.desc()).limit(6))
              ).scalars().all()
    plan_of = {s.user_id: ("trial" if s.provider == "trial" else s.plan_code) for s, _ in subs}
    now = utcnow()
    last_seen = func.coalesce(User.last_active_at, User.last_login_at)
    dau, wau, mau = [(await db.execute(select(func.count()).select_from(User).where(
        teacher, last_seen >= now - timedelta(days=d)))).scalar_one() for d in (1, 7, 30)]
    statuses = dict((await db.execute(select(User.status, func.count()).where(teacher).group_by(User.status))).all())
    unverified = (await db.execute(select(func.count()).select_from(User).where(
        teacher, User.email_verified.is_(False), User.status == "active"))).scalar_one()
    failed_count, failed_amount = (await db.execute(select(func.count(), func.coalesce(func.sum(Payment.amount), 0))
                                                    .where(Payment.status == "failed", Payment.created_at >= since))).one()
    revenue_period = (await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == "paid", Payment.created_at >= since))).scalar_one()
    past_due = sum(1 for s, _ in paying if s.status == "past_due")
    req_total, req_err = (await db.execute(select(func.count(), func.count().filter(ApiRequest.status >= 500))
                                           .where(ApiRequest.created_at >= now - timedelta(days=1)))).one()
    return {
        "active": {"dau": dau, "wau": wau, "mau": mau, "stickiness": round(dau / mau, 3) if mau else 0},
        "accounts": {"by_status": statuses, "unverified": unverified},
        "payments": {"failed": failed_count, "failed_amount_aed": round(float(failed_amount), 2),
                     "collected_aed": round(float(revenue_period), 2), "past_due_subscriptions": past_due},
        "conversion": {"trial_starts": trial_starts, "converted": converted,
                       "rate": round(converted / trial_starts, 3) if trial_starts else None},
        "api": {"requests_24h": req_total, "errors_24h": req_err,
                "error_rate_24h": round(req_err / req_total, 4) if req_total else 0},
        "recent_signups": [{"id": str(u.id), "name": u.name, "email": u.email, "role": u.role,
                            "plan": plan_of.get(u.id, "free"), "created_at": u.created_at.isoformat()}
                           for u in recent],
        "users": {"total": total_users, "active_30d": active_users, "paid": len(paying), "by_plan": by_plan,
                  "trialing": trials, "granted": granted, "trial_starts": trial_starts, "converted": converted},
        "revenue": {"mrr_aed": round(mrr, 2), "arr_aed": round(mrr * 12, 2)},
        "generation": {"jobs": jobs, "lesson_success_rate": round(success_rate, 3),
                       "avg_lesson_seconds": round(float(avg_time or 0), 1),
                       "failed": sum(v.get("failed", 0) for v in jobs.values()), "projects": projects},
        "ai": {"cost_usd": round(float(ai[0]), 4), "tokens": int(ai[1]), "calls": int(ai[2]),
               "cost_per_project_usd": round(float(ai[0]) / max(1, projects), 4)},
        "storage_mb": round(storage / 1_048_576, 1),
        "whatsapp": [{"direction": d, "status": s, "count": c} for d, s, c in wa],
        "popular": {"subjects": [{"name": s, "count": c} for s, c in subjects],
                    "grades": [{"name": g, "count": c} for g, c in grades],
                    "documents": [{"name": k, "count": c} for k, c in doc_kinds]},
        "series": await series(db, days),
    }


async def series(db: AsyncSession, days: int = 30) -> dict[str, list[dict[str, Any]]]:
    since = utcnow() - timedelta(days=days)
    day = cast(GenerationJob.created_at, Date)
    gen = (await db.execute(select(day, func.count()).where(GenerationJob.created_at >= since,
                                                            GenerationJob.type == "lesson_generation")
                            .group_by(day).order_by(day))).all()
    aday = cast(AIUsage.created_at, Date)
    cost = (await db.execute(select(aday, func.sum(AIUsage.cost_usd)).where(AIUsage.created_at >= since)
                             .group_by(aday).order_by(aday))).all()
    uday = cast(User.created_at, Date)
    signups = (await db.execute(select(uday, func.count()).where(User.created_at >= since, User.role == "teacher")
                                .group_by(uday)
                                .order_by(uday))).all()
    return {"lessons": [{"date": d.isoformat(), "value": c} for d, c in gen],
            "ai_cost": [{"date": d.isoformat(), "value": round(float(c or 0), 4)} for d, c in cost],
            "signups": [{"date": d.isoformat(), "value": c} for d, c in signups]}


async def ai_costs(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    by_model = (await db.execute(select(AIUsage.provider, AIUsage.model, func.count(), func.sum(AIUsage.input_tokens),
                                        func.sum(AIUsage.output_tokens), func.sum(AIUsage.cached_tokens),
                                        func.sum(AIUsage.cost_usd), func.avg(AIUsage.latency_ms),
                                        func.sum(case((AIUsage.success.is_(False), 1), else_=0)))
                                 .where(AIUsage.created_at >= since).group_by(AIUsage.provider, AIUsage.model)
                                 .order_by(func.sum(AIUsage.cost_usd).desc()))).all()
    by_task = (await db.execute(select(AIUsage.task, func.count(), func.sum(AIUsage.cost_usd), func.avg(
        AIUsage.latency_ms)).where(AIUsage.created_at >= since).group_by(AIUsage.task)
        .order_by(func.sum(AIUsage.cost_usd).desc()))).all()
    top_users = (await db.execute(select(User.email, func.sum(AIUsage.cost_usd)).join(User, User.id == AIUsage.owner_id)
                                  .where(AIUsage.created_at >= since).group_by(User.email)
                                  .order_by(func.sum(AIUsage.cost_usd).desc()).limit(10))).all()
    return {
        "by_model": [{"provider": p, "model": m, "calls": c, "input_tokens": int(i or 0), "output_tokens": int(o or 0),
                      "cached_tokens": int(ca or 0), "cost_usd": round(float(cost or 0), 4),
                      "avg_latency_ms": int(lat or 0), "failures": int(f or 0)}
                     for p, m, c, i, o, ca, cost, lat, f in by_model],
        "by_task": [{"task": t, "calls": c, "cost_usd": round(float(cost or 0), 4), "avg_latency_ms": int(lat or 0)}
                    for t, c, cost, lat in by_task],
        "top_users": [{"email": e, "cost_usd": round(float(c or 0), 4)} for e, c in top_users],
    }
