"""Teaching-assistant chat (web + WhatsApp).

Messages are routed to *actions* (planning, generation, history, reflections...) rather than free-form chat
wherever possible. A cheap rule-based router handles common phrasings at zero cost; the fast AI tier handles
the rest. General questions are answered with streaming using the teacher's context.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage
from app.ai.offline_provider import register_structured
from app.ai.service import get_ai
from app.core.errors import AppError
from app.generation import prompts
from app.models import ClassSection, Conversation, ConversationMessage, Course, Lesson, User
from app.services import planner
from app.services.context import build_context

IntentName = Literal["plan_today", "plan_tomorrow", "plan_week", "create_course", "create_worksheet", "create_quiz",
                     "create_homework", "create_test", "remedial", "adapt", "history", "next_topic", "cover_lesson",
                     "reflection", "general"]


class Intent(BaseModel):
    intent: IntentName
    topic: str | None = None
    grade: str | None = None
    subject: str | None = None
    lectures: int | None = None
    slides_per_lecture: int | None = None
    minutes: int | None = None
    class_name: str | None = None
    difficulty: str | None = None
    num_questions: int | None = None
    scope: str | None = None
    outcome: str | None = None
    instruction: str | None = None


RULES: list[tuple[str, str]] = [
    # Order matters: the most specific requests first.
    (r"\b(went well|ran out of time|we skipped|lesson went|class went)\b", "reflection"),
    (r"\b(struggl|didn'?t understand|confused|remedial|re-?teach)", "remedial"),
    (r"\b(cover lesson|substitute|i'?m absent|sick tomorrow)\b", "cover_lesson"),
    (r"\bworksheet", "create_worksheet"),
    (r"\bhomework\b", "create_homework"),
    (r"\b(test|exam|assessment)\b", "create_test"),
    (r"\b(quiz|mcqs?)\b", "create_quiz"),
    (r"\btomorrow", "plan_tomorrow"),
    (r"\b(my week|this week|whole week|next week|weekly)\b", "plan_week"),
    (r"\b(what should i teach|prepare|plan|get ready)\b.*\b(today|this morning)\b|^today\b|today'?s (plan|classes)",
     "plan_today"),
    (r"\b(create|make|generate|build|prepare|design)\b.*\b(lessons?|slides|ppt|presentation|deck|course|unit)\b",
     "create_course"),
    (r"\b(what did i teach|what have i taught|last week|yesterday)\b", "history"),
    (r"\b(continue|what'?s next|next topic|what next)\b", "next_topic"),
    (r"\b(easier|simpler|harder|adapt)\b", "adapt"),
]


def rule_intent(text: str) -> Intent | None:
    t = text.lower().strip()
    for pattern, name in RULES:
        if re.search(pattern, t):
            it = Intent(intent=name)  # type: ignore[arg-type]
            if m := re.search(r"grade\s*(\d{1,2})|year\s*(\d{1,2})|class\s*(\d{1,2})", t):
                it.grade = next(g for g in m.groups() if g)
            if m := re.search(r"(\d{1,2})\s*(lectures|lessons)", t):
                it.lectures = int(m.group(1))
            if m := re.search(r"(\d{1,2})\s*slides", t):
                it.slides_per_lecture = int(m.group(1))
            if m := re.search(r"(\d{2,3})[- ]?min", t):
                it.minutes = int(m.group(1))
            if m := re.search(r"(\d{1,2})\s*(questions|mcqs?)", t):
                it.num_questions = int(m.group(1))
            if m := re.search(r"\b(\d{1,2}[a-z])\b", t):
                it.class_name = m.group(1).upper()
            if "month" in t:
                it.scope = "month"
            for d in ("easy", "medium", "hard", "mixed"):
                if d in t:
                    it.difficulty = d
            if name == "reflection":
                it.outcome = ("ran_out_of_time" if "time" in t else "skipped" if "skip" in t else
                              "struggled" if "struggl" in t else "went_well")
            if m := re.search(r"\b(?:on|about|topic)\s+([a-z][a-z \-']{2,60}?)(?:\s+for\b|\s+grade\b|,|\.|$)", t):
                topic = m.group(1).strip()
                if not re.search(r"\b(today|this|my|previous|last)\b.*\blesson|^lesson$", topic):
                    it.topic = topic
            for subj in ("science", "biology", "chemistry", "physics", "math", "maths", "mathematics", "english",
                         "geography", "history", "arabic", "computing", "ai"):
                if re.search(rf"\b{subj}\b", t):
                    it.subject = {"math": "Mathematics", "maths": "Mathematics", "ai": "Artificial Intelligence"
                                  }.get(subj, subj.title())
            return it
    return None


@register_structured("intent")
def _offline_intent(ctx: dict[str, Any], schema) -> Intent:
    return rule_intent(ctx.get("text", "")) or Intent(intent="general")


async def classify(text: str, owner_id: uuid.UUID) -> Intent:
    fast = rule_intent(text)
    if fast and fast.intent not in ("create_course", "general"):
        return fast
    ai = get_ai()
    try:
        return await ai.structured(task="intent", tier="fast", system=prompts.INTENT_SYSTEM, prompt=text,
                                   schema=Intent, effort="low", max_tokens=800, owner_id=owner_id,
                                   offline_context={"text": text}, cache=True)
    except Exception:
        return fast or Intent(intent="general")


async def _find_class(db: AsyncSession, user: User, name: str | None) -> ClassSection | None:
    if not name:
        return None
    return (await db.execute(select(ClassSection).where(ClassSection.user_id == user.id,
                                                          ClassSection.name.ilike(name)))).scalars().first()


def _fmt_day(day: dict[str, Any]) -> str:
    if day.get("holiday"):
        return f"**{day['weekday']} {day['date']}** — {day['holiday']} (no classes)"
    if not day["classes"]:
        return f"**{day['weekday']} {day['date']}** — no classes on your timetable"
    lines = [f"**{day['weekday']} {day['date']}**" + (" (shortened timings)" if day["duration_factor"] < 1 else "")]
    for c in day["classes"]:
        if c.get("lesson"):
            les = c["lesson"]
            ready = "✅ ready" if les["materials"]["pptx"] else ("⏳ preparing" if les["status"] == "generating"
                                                                  else "📝 not generated yet")
            lines.append(f"- {c['start']} {c['class']['name']} {c['class']['subject']}: {c['course']['topic']} — "
                         f"lesson {les['number']} “{les['title']}” ({c['minutes']} min) {ready}")
        else:
            sug = c.get("suggestion") or {}
            lines.append(f"- {c['start']} {c['class']['name']} {c['class']['subject']}: no lesson planned. "
                         + (f"Suggested next: {sug['topic']}." if sug.get("topic") else sug.get("reason", "")))
    return "\n".join(lines)


async def run_action(db: AsyncSession, user: User, intent: Intent, text: str) -> tuple[str, list[dict[str, Any]]]:
    """Execute an intent. Returns (markdown reply, actions)."""
    actions: list[dict[str, Any]] = []
    today = planner.today_for(user)
    if intent.intent in ("plan_today", "plan_tomorrow"):
        day = today if intent.intent == "plan_today" else await planner.next_working_day(db, user, today)
        res = await planner.prepare(db, user, [day])
        reply = _fmt_day(res["days"][0])
        if res["lessons_queued"]:
            reply += f"\n\nI'm preparing {res['lessons_queued']} lesson(s) now — they'll be ready in a few minutes."
        actions.append({"type": "open", "label": "Open day plan", "href": f"/calendar?date={day.isoformat()}"})
        return reply, actions
    if intent.intent == "plan_week":
        days = await planner.week_days(db, user, today)
        res = await planner.prepare(db, user, days, with_documents=False)
        reply = "\n\n".join(_fmt_day(d) for d in res["days"])
        if res["lessons_queued"]:
            reply += f"\n\nPreparing {res['lessons_queued']} lesson(s) for the week in the background."
        actions.append({"type": "open", "label": "Open week", "href": "/calendar?view=week"})
        return reply, actions
    if intent.intent == "history":
        cs = await _find_class(db, user, intent.class_name)
        items = await planner.history(db, user, class_id=cs.id if cs else None, days=14)
        if not items:
            return "I couldn't find lessons in the last two weeks.", actions
        lines = [f"- {i['date'] or 'unscheduled'} {i['class'] or ''} {i['topic']} L{i['lesson']}: {i['title']} "
                 f"({i['status']})" for i in items[:15]]
        return "Here's what you've covered recently:\n" + "\n".join(lines), actions
    if intent.intent == "next_topic":
        cs = await _find_class(db, user, intent.class_name)
        classes = [cs] if cs else list((await db.execute(select(ClassSection).where(ClassSection.user_id == user.id))
                                        ).scalars().all())
        lines = []
        for c in classes[:6]:
            course = (await db.execute(select(Course).where(Course.class_section_id == c.id)
                                       .order_by(Course.created_at.desc()))).scalars().first()
            nxt = None
            if course:
                nxt = (await db.execute(select(Lesson).where(Lesson.course_id == course.id,
                                                              Lesson.status.in_(planner.PENDING))
                                        .order_by(Lesson.number))).scalars().first()
            if nxt:
                carry = f" (starts with: {nxt.carry_over['text']})" if nxt.carry_over else ""
                lines.append(f"- {c.name}: continue {course.topic} with lesson {nxt.number} “{nxt.title}”{carry}")
            else:
                sug = await planner.suggest_next_topic(db, user, c, finished_course=course)
                lines.append(f"- {c.name}: " + (f"start **{sug['topic']}** ({sug['reason']})" if sug.get("topic")
                                               else sug["reason"]))
        return ("Next up:\n" + "\n".join(lines)) if lines else "Add your classes first so I can track progress.", \
            [{"type": "open", "label": "Classes", "href": "/curriculum"}]
    if intent.intent in ("create_course", "remedial", "cover_lesson"):
        from app.services.courses import create_course

        tp_topic = intent.topic
        if intent.intent == "remedial" and not tp_topic:
            m = re.search(r"struggled with ([a-z \-']+)", text.lower())
            tp_topic = m.group(1).strip() if m else None
        if not tp_topic:
            return ("Which topic should I prepare? For example: *“Create 5 lessons on photosynthesis for Grade 8, "
                    "10 slides each.”*"), actions
        cs = await _find_class(db, user, intent.class_name)
        grade = intent.grade or (cs.grade if cs else None)
        subject = intent.subject or (cs.subject if cs else None)
        if not grade or not subject:
            from app.models import TeacherProfile

            tp = (await db.execute(select(TeacherProfile).where(TeacherProfile.user_id == user.id))).scalars().first()
            grade = grade or (tp.grades[0] if tp and tp.grades else "8")
            subject = subject or (tp.subjects[0] if tp and tp.subjects else "Science")
        instructions = intent.instruction
        lectures = intent.lectures or (1 if intent.intent in ("remedial", "cover_lesson") else 3)
        if intent.intent == "remedial":
            instructions = (f"Remedial lesson: students struggled with {tp_topic}. Re-teach with a different "
                            f"approach, concrete examples, worked examples and lots of checking for understanding.")
        if intent.intent == "cover_lesson":
            instructions = ("Cover lesson for a substitute teacher: fully self-contained, clear instructions on every "
                            "slide, independent student tasks, no prior context needed.")
        course, job_id = await create_course(db, user, {
            "topic": tp_topic, "grade": grade, "subject": subject, "num_lectures": lectures,
            "slides_per_lecture": intent.slides_per_lecture or 10, "lecture_minutes": intent.minutes,
            "class_section_id": cs.id if cs else None, "instructions": instructions, "auto_generate": True})
        actions.append({"type": "open", "label": "Open project", "href": f"/projects/{course.project_id}"})
        actions.append({"type": "job", "job_id": str(job_id)})
        return (f"On it — planning **{lectures} lesson(s) on {tp_topic}** for Grade {grade} {subject}, then building "
                f"the slides in your style. I'll let you know when they're ready."), actions
    if intent.intent in ("create_worksheet", "create_quiz", "create_homework", "create_test"):
        from app.services.documents import create_document

        kind = {"create_worksheet": "worksheet", "create_quiz": "quiz", "create_homework": "homework",
                "create_test": "assessment"}[intent.intent]
        data: dict[str, Any] = {"kind": kind, "difficulty": intent.difficulty or "mixed",
                                "num_questions": intent.num_questions}
        if intent.scope == "month":
            data["scope"] = "month"
        else:
            latest = (await db.execute(select(Lesson).where(Lesson.owner_id == user.id, Lesson.plan.is_not(None))
                                       .order_by(Lesson.updated_at.desc()))).scalars().first()
            if latest is None and not intent.topic:
                return "Generate a lesson first, or tell me the topic for the worksheet.", actions
            if latest is not None and not intent.topic:
                data["lesson_id"] = latest.id
            else:
                data["topic"] = intent.topic
        doc, job_id = await create_document(db, user, data)
        actions.append({"type": "job", "job_id": str(job_id)})
        actions.append({"type": "open", "label": "Open documents", "href": "/lessons?tab=documents"})
        scope = "everything taught this month" if data.get("scope") == "month" else (
            f"“{intent.topic}”" if intent.topic else "your latest lesson")
        return f"Creating a {kind.replace('_', ' ')} from {scope}, with a separate answer key.", actions
    if intent.intent == "reflection":
        latest = (await db.execute(select(Lesson).where(Lesson.owner_id == user.id, Lesson.status.in_(
            ("generated",))).order_by(Lesson.scheduled_date.desc().nullslast(), Lesson.updated_at.desc()))
        ).scalars().first()
        if latest is None:
            return "I couldn't find a lesson to attach that to.", actions
        res = await planner.record_reflection(db, user, latest.id, intent.outcome or "went_well", note=text,
                                              channel="chat")
        return "Thanks — noted. " + " ".join(res["effects"]), actions
    if intent.intent == "adapt":
        return ("Open the lesson and use **Make simpler / Adapt for Grade N** on the deck or any slide — "
                "the design stays the same."), [{"type": "open", "label": "Projects", "href": "/projects"}]
    raise AppError("general", "", 200)


async def converse(db: AsyncSession, user: User, text: str, conversation_id: uuid.UUID | None
                   ) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE events: status, token, action, done."""
    if conversation_id:
        conv = await db.get(Conversation, conversation_id)
        if conv is None or conv.owner_id != user.id:
            raise AppError("not_found", "Conversation not found", 404)
    else:
        conv = Conversation(owner_id=user.id, title=text[:80])
        db.add(conv)
        await db.flush()
    db.add(ConversationMessage(conversation_id=conv.id, role="user", content=text))
    await db.commit()
    yield {"event": "conversation", "data": {"id": str(conv.id)}}
    intent = await classify(text, user.id)
    yield {"event": "status", "data": {"intent": intent.intent}}
    reply, actions = "", []
    if intent.intent != "general":
        try:
            reply, actions = await run_action(db, user, intent, text)
        except AppError as e:
            if e.code != "general":
                reply = e.message
            else:
                intent.intent = "general"
    if intent.intent == "general" and not reply:
        context_text, _ = await build_context(db, user, topic=text, include_sources=True)
        recent = (await db.execute(select(ConversationMessage).where(ConversationMessage.conversation_id == conv.id)
                                   .order_by(ConversationMessage.created_at.desc()).limit(8))).scalars().all()
        history = [ChatMessage("user" if m.role == "user" else "assistant", m.content) for m in reversed(recent)]
        if not history or history[-1].role != "user":
            history.append(ChatMessage("user", text))
        history[0] = ChatMessage("user", f"TEACHING CONTEXT\n{context_text}\n\nTEACHER: {history[0].content}")
        async for chunk in get_ai().stream(task="assistant_chat", tier="content", system=prompts.ASSISTANT_SYSTEM,
                                           messages=history, owner_id=user.id):
            reply += chunk
            yield {"event": "token", "data": {"text": chunk}}
    else:
        yield {"event": "token", "data": {"text": reply}}
    for a in actions:
        yield {"event": "action", "data": a}
    db.add(ConversationMessage(conversation_id=conv.id, role="assistant", content=reply, actions=actions))
    await db.commit()
    yield {"event": "done", "data": {"conversation_id": str(conv.id)}}


async def answer_once(db: AsyncSession, user: User, text: str, conversation_id: uuid.UUID | None = None
                      ) -> tuple[str, list[dict[str, Any]], uuid.UUID]:
    """Non-streaming variant (WhatsApp)."""
    reply, actions, conv_id = "", [], None
    async for ev in converse(db, user, text, conversation_id):
        if ev["event"] == "token":
            reply += ev["data"]["text"]
        elif ev["event"] == "action":
            actions.append(ev["data"])
        elif ev["event"] == "conversation":
            conv_id = uuid.UUID(ev["data"]["id"])
    return reply, actions, conv_id
