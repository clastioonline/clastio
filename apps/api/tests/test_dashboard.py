from __future__ import annotations

from tests.conftest import make_user


async def test_teacher_dashboard_for_new_and_active_teacher(client):
    u = await make_user(client, plan="assistant")
    h = u["headers"]
    d = (await client.get("/api/v1/me/dashboard", headers=h)).json()
    assert d["kpis"]["total"] == 0 and len(d["week"]) == 7 and sum(w["today"] for w in d["week"]) == 1
    assert d["next_class"] is None and d["upcoming"] == [] and d["classes"] == []
    assert not any(d["checklist"].values())

    cls = (await client.post("/api/v1/classes", headers=h, json={"name": "8A", "grade": "8", "subject": "Science"})).json()
    r = await client.post("/api/v1/courses", headers=h, json={
        "topic": "Photosynthesis", "grade": "8", "subject": "Science", "num_lectures": 2, "slides_per_lecture": 8,
        "class_section_id": cls["id"], "auto_generate": True})
    assert r.status_code == 200, r.text
    d = (await client.get("/api/v1/me/dashboard", headers=h)).json()
    assert d["kpis"]["total"] == 2 and d["kpis"]["ready"] == 2
    assert d["week"][[w["today"] for w in d["week"]].index(True)]["value"] == 2  # both built today
    assert d["checklist"]["class"] and d["checklist"]["course"] and not d["checklist"]["timetable"]
    c = d["classes"][0]
    assert c["topic"] == "Photosynthesis" and c["status"] == "ready" and c["next_lesson"]["number"] == 1
    assert [x["number"] for x in d["upcoming"]] == [1, 2]
