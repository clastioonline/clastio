"""Object-level authorization (IDOR) and file access: one teacher can never read or change another's resources."""

from __future__ import annotations

import time
import uuid

from tests.conftest import SAMPLES, make_user


async def _course(client, h) -> dict:
    cls = (await client.post("/api/v1/classes", headers=h, json={"name": "7B", "grade": "7",
                                                                 "subject": "Science"})).json()
    r = await client.post("/api/v1/courses", headers=h, json={
        "topic": "Magnets", "grade": "7", "subject": "Science", "num_lectures": 1, "slides_per_lecture": 6,
        "class_section_id": cls["id"], "auto_generate": True})
    assert r.status_code == 200, r.text
    body = r.json()
    course = body["course"]
    project = (await client.get(f"/api/v1/projects/{course['project_id']}", headers=h)).json()
    return {"class_id": cls["id"], "project_id": course["project_id"], "course_id": course["id"],
            "lesson_id": project["lessons"][0]["id"], "job_id": body.get("job_id")}


async def test_teachers_cannot_reach_each_others_resources(client):
    a = await make_user(client)
    b = await make_user(client)
    ids = await _course(client, a["headers"])
    hb = b["headers"]
    denied = [
        ("get", f"/api/v1/projects/{ids['project_id']}", None),
        ("delete", f"/api/v1/projects/{ids['project_id']}", None),
        ("get", f"/api/v1/lessons/{ids['lesson_id']}", None),
        ("patch", f"/api/v1/lessons/{ids['lesson_id']}", {"title": "hijacked"}),
        ("get", f"/api/v1/lessons/{ids['lesson_id']}/slides/1/versions", None),
        ("post", f"/api/v1/lessons/{ids['lesson_id']}/slides/1/regenerate", {"action": "simpler"}),
        ("put", f"/api/v1/classes/{ids['class_id']}", {"name": "x", "grade": "7", "subject": "Science"}),
        ("delete", f"/api/v1/classes/{ids['class_id']}", None),
        ("post", "/api/v1/documents", {"kind": "worksheet", "lesson_id": ids["lesson_id"]}),
    ]
    if ids["course_id"]:
        denied.append(("get", f"/api/v1/courses/{ids['course_id']}/progress", None))
    if ids["job_id"]:
        denied.append(("get", f"/api/v1/jobs/{ids['job_id']}", None))
    for method, path, body in denied:
        kwargs = {"headers": hb}
        if body is not None:
            kwargs["json"] = body
        r = await getattr(client, method)(path, **kwargs)
        # Someone else's resource is indistinguishable from a missing one.
        assert r.status_code in (403, 404), (method, path, r.status_code, r.text[:200])
    # A's things still work for A and weren't changed by B.
    lesson = (await client.get(f"/api/v1/lessons/{ids['lesson_id']}", headers=a["headers"])).json()
    assert lesson.get("title") != "hijacked"
    assert not any(p["id"] == ids["project_id"] for p in
                   (await client.get("/api/v1/projects", headers=hb)).json().get("items", []))


async def test_uploads_and_media_are_private(client):
    a = await make_user(client)
    b = await make_user(client)
    with open(SAMPLES / "science_ms_sara.pdf", "rb") as fh:
        r = await client.post("/api/v1/uploads", headers=a["headers"], data={"kind": "source"},
                              files={"file": ("notes.pdf", fh, "application/pdf")})
    assert r.status_code == 200, r.text
    fid = r.json()["file"]["id"]
    assert (await client.get(f"/api/v1/uploads/{fid}", headers=b["headers"])).status_code == 404
    assert (await client.delete(f"/api/v1/uploads/{fid}", headers=b["headers"])).status_code == 404
    assert all(f["id"] != fid for f in (await client.get("/api/v1/uploads", headers=b["headers"])).json()["items"])
    assert (await client.get(f"/api/v1/media/{uuid.uuid4()}", headers=b["headers"])).status_code == 404


async def test_signed_file_links_cannot_be_forged_or_reused_after_expiry(client):
    from app.core.storage import get_storage

    storage = get_storage()
    await storage.put("tests/secret.txt", b"private lesson notes", "text/plain")
    url = storage.signed_url("tests/secret.txt")
    assert (await client.get(url)).status_code == 200
    forged = url.replace("secret.txt", "other.txt")
    assert (await client.get(forged)).status_code == 403
    tampered = url.rsplit("sig=", 1)[0] + "sig=" + "0" * 64
    assert (await client.get(tampered)).status_code == 403
    expired = storage.signed_url("tests/secret.txt", ttl=-10)
    assert (await client.get(expired)).status_code == 403
    exp = int(time.time()) + 60
    from app.core.security import sign_value

    traversal = f"/api/v1/files/..%2F..%2Fetc%2Fpasswd?exp={exp}&sig={sign_value('../../etc/passwd', exp)}"
    assert (await client.get(traversal)).status_code in (400, 403, 404)


async def test_teacher_cannot_escalate_via_profile_or_settings(client):
    u = await make_user(client)
    r = await client.put("/api/v1/me/profile", headers=u["headers"], json={"role": "admin", "admin_role":
                                                                            "super_admin", "status": "active"})
    assert r.status_code in (200, 422)
    me = (await client.get("/api/v1/auth/me", headers=u["headers"])).json()["user"]
    assert me["role"] == "teacher" and me["permissions"] == []
    assert (await client.put("/api/v1/admin/settings/system", headers=u["headers"],
                             json={"maintenance": {"enabled": True}})).status_code == 403
