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
    course = r.json()['course']
    d = (await client.get("/api/v1/me/dashboard", headers=h)).json()
    assert d["kpis"]["total"] == 2 and d["kpis"]["ready"] == 1 and d["kpis"]["pending"] == 1
    assert d["week"][[w["today"] for w in d["week"]].index(True)]["value"] == 1
    assert d["checklist"]["class"] and d["checklist"]["course"] and not d["checklist"]["timetable"]
    c = d["classes"][0]
    assert c["topic"] == "Photosynthesis" and c["status"] == "ready" and c["next_lesson"]["number"] == 1
    assert [x["number"] for x in d["upcoming"]] == [1, 2]
    assert [x["status"] for x in d["upcoming"]] == ['generated', 'planned']

    blocked = await client.post(f"/api/v1/courses/{course['id']}/generate", headers=h, json={'lessons': [2]})
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()['error']['code'] == 'review_required'
    unchanged = (await client.get('/api/v1/me/dashboard', headers=h)).json()
    assert unchanged['kpis']['ready'] == 1 and unchanged['kpis']['pending'] == 1
    project = (await client.get(f"/api/v1/projects/{course['project_id']}", headers=h)).json()
    first = project['lessons'][0]
    approved = await client.post(f"/api/v1/lessons/{first['id']}/approve", headers=h,
                                json={'version': first['version']})
    assert approved.status_code == 200, approved.text
    generated = await client.post(f"/api/v1/courses/{course['id']}/generate", headers=h, json={'lessons': [2]})
    assert generated.status_code == 202, generated.text
    d = (await client.get('/api/v1/me/dashboard', headers=h)).json()
    assert d['kpis']['total'] == 2 and d['kpis']['ready'] == 2 and d['kpis']['pending'] == 0
    assert d['week'][[w['today'] for w in d['week']].index(True)]['value'] == 2
    assert all(item['status'] == 'generated' for item in d['upcoming'])
