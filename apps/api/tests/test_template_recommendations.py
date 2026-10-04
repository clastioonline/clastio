from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.models import Organization, Template, User
from app.seed import seed_core
from tests.conftest import make_user


async def test_template_recommendations_use_stated_profile_and_selected_class(client, teacher):
    headers = teacher["headers"]
    profile = await client.put("/api/v1/me/profile", headers=headers, json={
        "school_name": "Example British International School", "curriculum": "moe",
        "subjects": ["Social Studies & Moral Education"], "grades": ["5"], "teaching_languages": ["en"],
    })
    assert profile.status_code == 200
    result = (await client.get("/api/v1/templates", headers=headers)).json()
    assert len([item for item in result["items"] if item["builtin"]]) == 15
    assert all(len(item["previews"]) == 6 for item in result["items"] if item["builtin"]), "All curated designs have real rendered previews"
    assert result["context"]["curriculum"] == "moe", "School name cannot infer a curriculum"
    assert result["recommendations"][0]["name"] == "UAE Heritage"
    classroom = await client.post("/api/v1/classes", headers=headers, json={
        "name": "8A", "grade": "8", "subject": "Science", "curriculum": "cbse",
    })
    assert classroom.status_code == 200, classroom.text
    result = (await client.get(f"/api/v1/templates?class_id={classroom.json()['id']}", headers=headers)).json()
    assert result["context"]["curriculum"] == "cbse"
    assert result["recommendations"][0]["name"] == "CBSE Concept Builder"
    explicit_class = (await client.get(f"/api/v1/templates?class_id={classroom.json()['id']}&curriculum=british", headers=headers)).json()
    assert explicit_class["context"]["curriculum"] == "british", "Explicit lesson context takes priority over class defaults"
    assert explicit_class["recommendations"][0]["name"] == "Discovery Lab"
    explicit = (await client.get("/api/v1/templates?subject=Arabic&grade=6&language=ar", headers=headers)).json()
    assert explicit["recommendations"][0]["name"] == "Arabic Classroom"


async def test_template_suggestions_preserve_default_and_block_other_teachers_upload(client, teacher):
    other = await make_user(client)
    async with get_sessionmaker()() as db:
        base = (await db.execute(select(Template).where(Template.owner_id.is_(None), Template.name == "Warm Sand"))).scalars().one()
        private = Template(owner_id=uuid.UUID(other["id"]), org_id=None, name="Other teacher's private deck",
                           mode="native", base_storage_key=base.base_storage_key, spec=base.spec,
                           preview_keys=base.preview_keys, is_shared=True)
        db.add(private)
        await db.commit()
        private_id, saved_id = str(private.id), str(base.id)
    chosen = await client.post(f"/api/v1/templates/{saved_id}/default", headers=teacher["headers"])
    assert chosen.status_code == 200
    listed = (await client.get("/api/v1/templates?subject=Mathematics&grade=9", headers=teacher["headers"])).json()
    assert listed["recommendations"][0]["template_id"] == saved_id
    assert private_id not in {item["id"] for item in listed["items"]}
    denied = await client.get(f"/api/v1/templates/{private_id}", headers=teacher["headers"])
    assert denied.status_code == 404
    course_denied = await client.post("/api/v1/courses", headers=teacher["headers"], json={
        "topic": "Plants", "grade": "9", "subject": "Science", "num_lectures": 1,
        "slides_per_lecture": 10, "auto_generate": False, "template_id": private_id,
    })
    assert course_denied.status_code == 404
    foreign_class = await client.post("/api/v1/classes", headers=other["headers"], json={"name": "9C", "grade": "9", "subject": "Science"})
    denied = await client.get(f"/api/v1/templates?class_id={foreign_class.json()['id']}", headers=teacher["headers"])
    assert denied.status_code == 404


async def test_template_sharing_requires_the_same_non_null_organisation(client, teacher):
    other = await make_user(client)
    async with get_sessionmaker()() as db:
        organisation = Organization(name="Example School Team")
        db.add(organisation)
        await db.flush()
        base = (await db.execute(select(Template).where(Template.owner_id.is_(None)))).scalars().first()
        shared = Template(owner_id=uuid.UUID(other["id"]), org_id=organisation.id, name="Shared school style",
                          mode="native", base_storage_key=base.base_storage_key, spec=base.spec,
                          preview_keys=base.preview_keys, is_shared=True)
        db.add(shared)
        await db.commit()
        shared_id = str(shared.id)
        assert (await client.get(f"/api/v1/templates/{shared_id}", headers=teacher["headers"])).status_code == 404
        viewer = await db.get(User, uuid.UUID(teacher["id"]))
        viewer.org_id = organisation.id
        await db.commit()
    result = (await client.get("/api/v1/templates", headers=teacher["headers"])).json()
    item = next(item for item in result["items"] if item["id"] == shared_id)
    assert item["can_edit"] is False and item["recommendation"]
    assert "shared by your organisation" in item["recommendation"]["reason"]
    assert (await client.get(f"/api/v1/templates/{shared_id}", headers=teacher["headers"])).status_code == 200


async def test_builtin_reseed_preserves_ids_storage_keys_and_saved_default(client, teacher):
    async with get_sessionmaker()() as db:
        before = (await db.execute(select(Template).where(Template.owner_id.is_(None)))).scalars().all()
        snapshots = {item.id: (item.name, item.base_storage_key, item.preview_keys) for item in before}
    await seed_core(embed=False)
    async with get_sessionmaker()() as db:
        after = (await db.execute(select(Template).where(Template.owner_id.is_(None)))).scalars().all()
        assert {item.id: (item.name, item.base_storage_key, item.preview_keys) for item in after} == snapshots
