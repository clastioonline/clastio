from __future__ import annotations

import io
import zipfile

from tests.conftest import SAMPLES, make_user


async def test_signup_login_me(client):
    r = await client.post("/api/v1/auth/signup", json={"email": "Amira@Example.com", "password": "longenough1",
                                                          "name": "Amira"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "amira@example.com"
    assert "ata_session" in r.headers.get("set-cookie", "")
    assert "HttpOnly" in r.headers["set-cookie"]
    client.cookies.clear()
    r = await client.post("/api/v1/auth/login", json={"email": "amira@example.com", "password": "longenough1"})
    assert r.status_code == 200
    token = r.json()["token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["user"]["name"] == "Amira"


async def test_bad_credentials_and_duplicates(client):
    u = await make_user(client)
    r = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"
    r = await client.post("/api/v1/auth/signup", json={"email": u["email"], "password": "whatever12", "name": "x"})
    assert r.status_code == 409


async def test_validation_errors(client):
    r = await client.post("/api/v1/auth/signup", json={"email": "not-an-email", "password": "short", "name": ""})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_requires_auth(client):
    client.cookies.clear()
    assert (await client.get("/api/v1/projects")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401


async def test_login_rate_limit(client):
    statuses = []
    for _ in range(12):
        r = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x" * 10})
        statuses.append(r.status_code)
    assert 429 in statuses
    assert statuses[0] == 401
    # The limit is per account: another teacher on the same school IP is not blocked.
    r = await client.post("/api/v1/auth/login", json={"email": "someone-else@example.com", "password": "x" * 10})
    assert r.status_code == 401


async def test_admin_routes_forbidden_for_teachers(client, teacher):
    r = await client.get("/api/v1/admin/metrics", headers=teacher["headers"])
    assert r.status_code == 403


async def test_cross_tenant_access_is_blocked(client):
    a = await make_user(client)
    b = await make_user(client)
    r = await client.post("/api/v1/courses", headers=a["headers"], json={
        "topic": "Magnetism", "grade": "6", "subject": "Science", "num_lectures": 1, "slides_per_lecture": 6})
    assert r.status_code == 200, r.text
    project_id = r.json()["course"]["project_id"]
    course_id = r.json()["course"]["id"]
    assert (await client.get(f"/api/v1/projects/{project_id}", headers=b["headers"])).status_code == 403
    assert (await client.post(f"/api/v1/courses/{course_id}/generate", headers=b["headers"], json={})
            ).status_code == 403
    listing = (await client.get("/api/v1/projects", headers=b["headers"])).json()["items"]
    assert all(p["id"] != project_id for p in listing)


# --------------------------------------------------------------------------- upload validation


async def _upload(client, headers, name: str, data: bytes, kind: str = "style"):
    return await client.post("/api/v1/uploads", headers=headers, data={"kind": kind},
                             files={"file": (name, data, "application/octet-stream")})


async def test_upload_rejects_wrong_type(client, teacher):
    r = await _upload(client, teacher["headers"], "evil.pdf", b"MZ\x90\x00 not really a pdf")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "upload_rejected"


async def test_upload_rejects_macro_files(client, teacher):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types>presentationml.presentation.main+xml</Types>")
        z.writestr("ppt/presentation.xml", "<p/>")
        z.writestr("ppt/vbaProject.bin", b"\x00" * 10)
    r = await _upload(client, teacher["headers"], "macro.pptx", buf.getvalue())
    assert r.status_code == 400
    assert "Macro" in r.json()["error"]["message"]


async def test_upload_rejects_zip_bomb(client, teacher):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types>presentationml.presentation.main+xml</Types>")
        z.writestr("ppt/presentation.xml", "<p/>")
        z.writestr("ppt/media/huge.bin", b"\x00" * (40 * 1024 * 1024))
    r = await _upload(client, teacher["headers"], "bomb.pptx", buf.getvalue())
    assert r.status_code == 400
    assert "unsafe" in r.json()["error"]["message"]


async def test_upload_dedupes_identical_files(client, teacher):
    data = (SAMPLES / "maths_mr_raj.pptx").read_bytes()
    first = await _upload(client, teacher["headers"], "maths.pptx", data)
    assert first.status_code == 200, first.text
    second = await _upload(client, teacher["headers"], "maths-copy.pptx", data)
    assert second.json()["duplicate"] is True
    assert second.json()["file"]["id"] == first.json()["file"]["id"]


async def test_signed_file_urls(client, teacher):
    from app.core.storage import get_storage

    storage = get_storage()
    await storage.put("tests/hello.txt", b"hi")
    url = storage.signed_url("tests/hello.txt", "hello.txt")
    ok = await client.get(url)
    assert ok.status_code == 200 and ok.content == b"hi"
    tampered = url.replace("sig=", "sig=0")
    assert (await client.get(tampered)).status_code == 403
