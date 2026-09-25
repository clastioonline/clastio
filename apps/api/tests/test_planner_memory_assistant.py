from __future__ import annotations

import json
from datetime import date, timedelta

from app.services.assistant import rule_intent


async def _setup_class_and_timetable(client, h, days=(0, 1, 2, 3, 4)):
    c = (await client.post("/api/v1/classes", headers=h, json={"name": "8A", "grade": "8", "subject": "Science",
                                                                 "eal_percent": 30})).json()
    slots = [{"class_section_id": c["id"], "day_of_week": d, "start_time": "08:00", "end_time": "08:45"} for d in days]
    r = await client.put("/api/v1/timetable", headers=h, json={"slots": slots})
    assert r.status_code == 200
    return c


async def test_preferences_and_memory(client, teacher):
    h = teacher["headers"]
    r = await client.put("/api/v1/me/profile", headers=h, json={
        "curriculum": "british", "subjects": ["Science"], "grades": ["8"], "class_duration_minutes": 50,
        "preferences": {"language_level": "simple English", "quiz_length": 5, "homework_last": True}})
    assert r.status_code == 200 and r.json()["class_duration_minutes"] == 50
    mem = (await client.get("/api/v1/memory", headers=h)).json()
    prefs = {p["key"]: p for p in mem["preferences"]}
    assert prefs["language_level"]["value"] == "simple English" and prefs["language_level"]["confirmed"]
    r = await client.post("/api/v1/memory/items", headers=h, json={"kind": "note",
                                                                      "content": "8A loves hands-on experiments"})
    assert r.status_code == 200
    found = (await client.get("/api/v1/memory/search?q=experiments", headers=h)).json()["items"]
    assert any("experiments" in f["content"] for f in found)


async def test_week_plan_and_reflection_loop(client, teacher):
    h = teacher["headers"]
    c = await _setup_class_and_timetable(client, h)
    r = await client.post("/api/v1/courses", headers=h, json={
        "topic": "Photosynthesis", "grade": "8", "subject": "Science", "num_lectures": 3, "slides_per_lecture": 6,
        "class_section_id": c["id"]})
    assert r.status_code == 200
    week = (await client.get("/api/v1/planner/week", headers=h)).json()["days"]
    lessons = [cl["lesson"]["number"] for d in week for cl in d["classes"] if cl.get("lesson")]
    assert lessons[:3] == [1, 2, 3]  # consecutive lessons across the week
    prep = (await client.post("/api/v1/planner/prepare", headers=h, json={"scope": "week"})).json()
    assert prep["lessons_queued"] == 3
    project_id = r.json()["course"]["project_id"]
    proj = (await client.get(f"/api/v1/projects/{project_id}", headers=h)).json()
    assert all(les["has_pptx"] for les in proj["lessons"])
    l1, l2 = proj["lessons"][0]["id"], proj["lessons"][1]["id"]
    res = (await client.post(f"/api/v1/lessons/{l1}/reflection", headers=h,
                             json={"outcome": "struggled", "note": "Mixed up reactants and products"})).json()
    assert res["status"] == "reflected"
    assert any("remedial" in e.lower() for e in res["effects"])
    nxt = (await client.get(f"/api/v1/lessons/{l2}", headers=h)).json()
    assert nxt["lesson"]["carry_over"]["kind"] == "remedial"
    mem = (await client.get("/api/v1/memory?kind=misconception", headers=h)).json()["items"]
    assert any("reactants" in m["content"] for m in mem)
    hist = (await client.get("/api/v1/planner/history", headers=h)).json()["items"]
    assert any(i["status"] == "reflected" for i in hist)


async def test_holiday_and_ramadan_calendar(client, teacher):
    h = teacher["headers"]
    await _setup_class_and_timetable(client, h, days=tuple(range(7)))
    today = date.today()
    tomorrow = today + timedelta(days=1)
    await client.post("/api/v1/calendar/events", headers=h, json={
        "kind": "holiday", "title": "School trip day", "start_date": str(today), "end_date": str(today)})
    await client.post("/api/v1/calendar/events", headers=h, json={
        "kind": "ramadan", "title": "Ramadan", "start_date": str(tomorrow), "end_date": str(tomorrow),
        "duration_factor": 0.7})
    d1 = (await client.get(f"/api/v1/planner/day?day={today}", headers=h)).json()
    assert d1["holiday"] == "School trip day" and d1["classes"] == []
    d2 = (await client.get(f"/api/v1/planner/day?day={tomorrow}", headers=h)).json()
    assert d2["duration_factor"] == 0.7 and d2["classes"][0]["minutes"] == 31


async def test_timetable_csv_import(client, teacher):
    h = teacher["headers"]
    csv = "day,start,end,class,subject,grade,room\nMon,07:45,08:30,9B,Biology,9,Lab 2\nTue,09:00,09:45,9B,Biology,9,\n"
    r = await client.post("/api/v1/timetable/import", headers=h, files={"file": ("tt.csv", csv, "text/csv")})
    assert r.status_code == 200 and r.json()["imported"] == 2
    classes = (await client.get("/api/v1/classes", headers=h)).json()["items"]
    assert any(c["name"] == "9B" for c in classes)


async def test_coverage_and_next_topic(client, teacher):
    h = teacher["headers"]
    c = await _setup_class_and_timetable(client, h)
    cov = (await client.get(f"/api/v1/curriculum/coverage?class_id={c['id']}", headers=h)).json()
    assert cov["summary"]["total"] >= 5
    nxt = (await client.get("/api/v1/planner/next", headers=h)).json()["items"]
    assert nxt[0]["suggestion"]["topic"]


def test_rule_based_intents():
    cases = {
        "What should I teach today?": "plan_today",
        "Prepare tomorrow's classes.": "plan_tomorrow",
        "Prepare my week": "plan_week",
        "What did I teach last week?": "history",
        "Continue from my previous lesson.": "next_topic",
        "Students struggled with fractions. Give me a remedial lesson.": "remedial",
        "Make this easier for Grade 6.": "adapt",
        "Create homework based on today's lesson.": "create_homework",
        "Create a test from everything taught this month.": "create_test",
        "Create 2 lessons on the water cycle for grade 7 science, 8 slides each": "create_course",
    }
    for text, intent in cases.items():
        assert rule_intent(text).intent == intent, text
    it = rule_intent("Create 2 lessons on the water cycle for grade 7 science, 8 slides each")
    assert (it.topic, it.grade, it.lectures, it.slides_per_lecture) == ("the water cycle", "7", 2, 8)


async def _chat(client, h, text):
    r = await client.post("/api/v1/assistant/messages", headers=h, json={"text": text})
    assert r.status_code == 200
    out, actions = "", []
    for line in r.text.splitlines():
        if line.startswith("data:"):
            d = json.loads(line[5:])
            out += d.get("text", "")
            if d.get("type") in ("open", "job"):
                actions.append(d)
    return out, actions


async def test_assistant_creates_lessons_and_plans(client, teacher):
    h = teacher["headers"]
    await _setup_class_and_timetable(client, h)
    text, actions = await _chat(client, h, "Create 2 lessons on the water cycle for grade 7 science, 6 slides each")
    assert "water cycle" in text
    assert any(a["type"] == "job" for a in actions)
    projects = (await client.get("/api/v1/projects", headers=h)).json()["items"]
    wc = next(p for p in projects if p["course"]["topic"] == "the water cycle")
    assert wc["lessons_ready"] == 2
    text, _ = await _chat(client, h, "What should I teach today?")
    assert "8A" in text or "no classes" in text.lower() or "holiday" in text.lower()
    convs = (await client.get("/api/v1/assistant/conversations", headers=h)).json()["items"]
    assert len(convs) >= 2
