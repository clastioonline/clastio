"""Real API/worker/database/render checks against the isolated offline QA stack.

Start with deploy/docker-compose.educator-qa.yml, then run this script with Python.
It deliberately uses only localhost:3004 and refuses live AI or production mode.
Demo credentials below belong only to the seeded QA fixture.
"""

import http.cookiejar
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BASE = "http://localhost:3004"
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
results = {}


def call(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + "/api/v1" + path,
        data=data,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json", "Origin": BASE},
    )
    try:
        with client.open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:2000]
        raise RuntimeError(f"{path} HTTP {error.code}: {detail}") from None


def wait(job):
    deadline = time.time() + 240
    last = None
    while time.time() < deadline:
        data = call("/jobs/" + job)
        state = (data["status"], data.get("stage"))
        if state != last:
            print("Job:", state, flush=True)
            last = state
        if data["status"] == "succeeded":
            return data
        if data["status"] in {"failed", "cancelled"}:
            raise RuntimeError(data.get("error") or "Job failed")
        time.sleep(2)
    raise RuntimeError("Job exceeded QA timeout")


def download(url, extension):
    target = urllib.parse.urljoin(BASE, url)
    with client.open(target, timeout=30) as response:
        data = response.read()
    assert data.startswith(b"%PDF-") if extension == "pdf" else data.startswith(b"PK"), extension
    if extension in {"docx", "pptx"}:
        with zipfile.ZipFile(io.BytesIO(data)) as file:
            assert (
                "word/document.xml" in file.namelist()
                if extension == "docx"
                else "ppt/presentation.xml" in file.namelist()
            )
    print("Downloaded valid", extension, len(data), "bytes", flush=True)
    return data


health = call("/health")
ready = call("/ready")
assert health["environment"] == "development", "Use the isolated development QA stack."
assert ready["status"] == "ready", "The QA dependencies and migrations must be ready."
assert ready["checks"]["ai"]["mode"] == "offline", "This test must never make paid model calls."
print("Ready: isolated offline QA stack", flush=True)
call("/auth/login", {"email": "sara@example.com", "password": "teacher-demo-123"})
scope = {
    "topic": "Ecosystems and UAE mangroves",
    "subject": "Science",
    "grade": "6",
    "curriculum": "british",
    "language": "en",
    "education_stage": "primary",
    "framework": "khda",
    "source_file_ids": [],
    "source_page_ranges": {},
}
created = call("/lesson-plans", {**scope, "duration_minutes": 45})
if created.get("job_id"):
    wait(created["job_id"])
plan = call("/lesson-plans/" + created["lesson_plan_id"])
assert (
    plan["status"] == "ready"
    and plan["content"]["differentiation"]["sen"]
    and plan["content"]["differentiation"]["ell"]
)
assert sum(phase["duration_minutes"] for phase in plan["content"]["lesson_sequence"]) == 45
for ext in ["pdf", "docx"]:
    download(plan["downloads"][ext], ext)
print("Standalone plan validated.", flush=True)

edited = dict(plan["content"])
edited["title"] = "Reviewed ecosystems lesson"
plan = call("/lesson-plans/" + plan["id"], {"version": plan["version"], "content": edited}, "PUT")
assert plan["version"] == 2 and not plan["downloads"]
review = call(
    "/lesson-plans/" + plan["id"] + "/review", {"version": plan["version"], "notes": "QA teacher review"}
)
assert review["status"] == "reviewed"
export = call("/lesson-plans/" + plan["id"] + "/export", {})
wait(export["job_id"])
plan = call("/lesson-plans/" + plan["id"])
download(plan["downloads"]["pdf"], "pdf")
results["plan_id"] = plan["id"]

resource_body = {key: value for key, value in scope.items() if key != "framework"}
resource_body.update(kind="subject_primer", chapter_count=3)
created = call("/digital-resources/generate", resource_body)
if created.get("job_id"):
    wait(created["job_id"])
guide = call("/digital-resources/" + created["resource_id"])
assert guide["status"] == "ready" and len(guide["content"]["chapters"]) == 3
assert guide["origin"] == "generated"
download(guide["downloads"]["pdf"], "pdf")
repeat = call("/digital-resources/generate", resource_body)
assert repeat["cached"] and repeat["job_id"] is None and repeat["resource_id"] == guide["id"]
print("Guide cache reuse validated.", flush=True)
results["resource_id"] = guide["id"]

created = call("/demo-classes", {**scope, "duration_minutes": 15})
if created.get("job_id"):
    wait(created["job_id"])
demo = call("/demo-classes/" + created["demo_class_id"])
assert demo["status"] == "ready" and demo["lesson_id"]
assert demo["content"]["teacher_script"][-1]["end_seconds"] == 900
assert abs(sum(slide["timing_minutes"] for slide in demo["content"]["slide_payload"]["slides"]) - 15) < 0.01
for ext in ["pdf", "docx", "pptx"]:
    download(demo["downloads"][ext], ext)
lesson = call("/lessons/" + demo["lesson_id"])
assert len(lesson["slides"]) == len(demo["content"]["slide_payload"]["slides"])
assert all(slide["preview"] for slide in lesson["slides"])
print("Demo script, PPT and editor previews validated.", flush=True)
results["demo_id"] = demo["id"]
results["lesson_id"] = demo["lesson_id"]

copilot_body = {
    "request": "Generate a differentiated reading task for Grade 6 Science about ecosystems, linking it to UAE mangroves. Include SEN scaffolds and ELL sentence frames.",
    **{key: value for key, value in scope.items() if key != "framework"},
}
created = call("/copilot/resources", copilot_body)
if created.get("job_id"):
    wait(created["job_id"])
task = call("/digital-resources/" + created["resource"]["id"])
assert task["status"] == "ready" and task["content"]["printable_task"]["support"]["sen"]
download(task["downloads"]["pdf"], "pdf")
conversation = call("/copilot/conversations/" + created["conversation_id"])
assert [message["role"] for message in conversation["messages"]][-1] == "assistant"
assert any(
    action["type"] == "copilot_resource"
    for message in conversation["messages"]
    for action in message.get("actions", [])
)
print("Copilot saved conversation and printable task validated.", flush=True)
results["copilot_id"] = task["id"]
results["conversation_id"] = created["conversation_id"]
repeat = call("/copilot/resources", copilot_body)
assert repeat["cached"] and repeat["job_id"] is None
assert repeat["resource"]["id"] == task["id"]
assert repeat["conversation_id"] != created["conversation_id"]
print("Copilot cache reused across new conversations.", flush=True)

follow = call(
    "/copilot/resources",
    {
        **copilot_body,
        "request": "Make the reading task easier and add visual support.",
        "conversation_id": created["conversation_id"],
    },
)
wait(follow["job_id"])
conversation = call("/copilot/conversations/" + created["conversation_id"])
assert any(
    message["content"] == "Make the reading task easier and add visual support."
    for message in conversation["messages"]
)
print("Contextual follow-up conversation persisted.", flush=True)
results["followup_id"] = follow["resource"]["id"]

# Owner isolation: a separate authenticated demo admin must not read a teacher's private rows.
call("/auth/logout", {})
call("/auth/login", {"email": "admin@example.com", "password": "admin-demo-123"})
for path in [
    "/lesson-plans/" + results["plan_id"],
    "/demo-classes/" + results["demo_id"],
    "/digital-resources/" + results["resource_id"],
    "/copilot/conversations/" + results["conversation_id"],
]:
    try:
        call(path)
    except RuntimeError as error:
        assert "HTTP 404" in str(error), str(error)
    else:
        raise AssertionError("Private owner-scoped row was exposed: " + path)
print("Private owner isolation validated.", flush=True)
print(
    "PASS: all educator phases work with real jobs, PostgreSQL, printable PDFs, PPT rendering, cache reuse and conversation persistence.",
    flush=True,
)
