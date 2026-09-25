"""Grounding sources: teacher-uploaded textbook chapters / syllabi, chunked + embedded for retrieval."""

from __future__ import annotations

import io
import re
import uuid
from typing import Any

import pymupdf as fitz
from docx import Document as DocxDocument
from pptx import Presentation
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import get_ai
from app.core.db import get_sessionmaker
from app.core.storage import get_storage
from app.models import SourceChunk, UploadedFile

CHUNK_CHARS = 900


def extract_pages(data: bytes, ext: str) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    if ext == "pdf":
        doc = fitz.open(stream=data, filetype="pdf")
        for i, p in enumerate(doc, start=1):
            pages.append((i, p.get_text("text")))
    elif ext == "pptx":
        prs = Presentation(io.BytesIO(data))
        for i, s in enumerate(prs.slides, start=1):
            texts = [sh.text_frame.text for sh in s.shapes if getattr(sh, "has_text_frame", False) and sh.has_text_frame]
            if s.has_notes_slide:
                texts.append(s.notes_slide.notes_text_frame.text)
            pages.append((i, "\n".join(texts)))
    elif ext == "docx":
        doc = DocxDocument(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
        pages = [(i + 1, text[i * 3000:(i + 1) * 3000]) for i in range(max(1, len(text) // 3000 + 1))]
    elif ext == "txt":
        text = data.decode("utf-8", "ignore")
        pages = [(i + 1, text[i * 3000:(i + 1) * 3000]) for i in range(max(1, len(text) // 3000 + 1))]
    return [(n, re.sub(r"[ \t]+", " ", t).strip()) for n, t in pages if t and t.strip()]


def chunk(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for page, text in pages:
        paras = [p.strip() for p in re.split(r"\n{2,}|\n(?=[A-Z•\-])", text) if p.strip()]
        buf = ""
        for para in paras:
            if len(buf) + len(para) > CHUNK_CHARS and buf:
                out.append((page, buf.strip()))
                buf = ""
            buf += para + "\n"
        if buf.strip():
            out.append((page, buf.strip()))
    return out


async def index_source(file_id: uuid.UUID) -> dict[str, Any]:
    async with get_sessionmaker()() as s:
        f = await s.get(UploadedFile, file_id)
        if f is None:
            raise ValueError("source not found")
        f.status, f.stage = "processing", "Reading document"
        await s.commit()
        owner_id, key = f.owner_id, f.storage_key
    ext = key.rsplit(".", 1)[-1]
    data = await get_storage().get(key)
    chunks = chunk(extract_pages(data, ext))
    vectors = await get_ai().embed([c[1] for c in chunks], owner_id=owner_id) if chunks else []
    async with get_sessionmaker()() as s:
        await s.execute(delete(SourceChunk).where(SourceChunk.file_id == file_id))
        for (page, text), vec in zip(chunks, vectors, strict=False):
            s.add(SourceChunk(file_id=file_id, owner_id=owner_id, page=page, text=text, embedding=vec))
        f = await s.get(UploadedFile, file_id)
        f.status, f.stage, f.page_count = "ready", "Ready", len({c[0] for c in chunks})
        await s.commit()
    return {"chunks": len(chunks)}


async def retrieve(db: AsyncSession, owner_id: uuid.UUID, query: str, k: int = 6) -> list[dict[str, Any]]:
    has_any = (await db.execute(select(SourceChunk.id).where(SourceChunk.owner_id == owner_id).limit(1))).first()
    if not has_any:
        return []
    vec = (await get_ai().embed([query], owner_id=owner_id))[0]
    rows = (await db.execute(
        select(SourceChunk, UploadedFile.filename).join(UploadedFile, UploadedFile.id == SourceChunk.file_id)
        .where(SourceChunk.owner_id == owner_id, SourceChunk.embedding.is_not(None))
        .order_by(SourceChunk.embedding.cosine_distance(vec)).limit(k))).all()
    return [{"file_id": str(c.file_id), "file": fn, "page": c.page, "text": c.text} for c, fn in rows]
