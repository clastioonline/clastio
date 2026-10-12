import io
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pymupdf as fitz
import pytest
from PIL import Image

from app.jobs.queue import PermanentJobError
from app.services.pdf_ingestion import extract_scanned, scan_pages


def pdf_with_empty_and_scanned_pages():
    image = io.BytesIO()
    Image.new('RGB', (100, 100), 'navy').save(image, format='PNG')
    with fitz.open() as document:
        document.new_page().insert_text((40, 40), 'Readable textbook text.')
        document.new_page()
        page = document.new_page()
        page.insert_image(fitz.Rect(40, 40, 140, 140), stream=image.getvalue())
        page = document.new_page()
        page.draw_rect(fitz.Rect(40, 40, 140, 140), fill=(.1, .1, .1))
        page = document.new_page()
        page.add_freetext_annot(fitz.Rect(40, 40, 240, 140), 'A visible annotation.')
        return document.tobytes()


def test_only_nonextractable_pages_with_visible_content_need_ingestion():
    assert scan_pages(pdf_with_empty_and_scanned_pages(), {1}) == [3, 4, 5]


async def test_native_text_with_blank_pages_does_not_require_a_model(monkeypatch):
    with fitz.open() as document:
        document.new_page().insert_text((40, 40), 'Readable textbook text.')
        document.new_page()
        data = document.tobytes()
    get_ai = AsyncMock()
    monkeypatch.setattr('app.services.pdf_ingestion.get_ai', get_ai)
    pages = [(1, 'Readable textbook text.')]
    assert await extract_scanned(data, pages, uuid.uuid4()) == pages
    get_ai.assert_not_called()


async def test_fully_blank_pdf_leaves_no_text_for_the_source_indexer(monkeypatch):
    with fitz.open() as document:
        document.new_page()
        data = document.tobytes()
    get_ai = AsyncMock()
    monkeypatch.setattr('app.services.pdf_ingestion.get_ai', get_ai)
    assert await extract_scanned(data, [], uuid.uuid4()) == []
    get_ai.assert_not_called()


async def test_real_scan_still_requires_the_configured_ingestion_model(monkeypatch):
    monkeypatch.setattr('app.services.pdf_ingestion.get_ai', lambda: SimpleNamespace(mode='offline'))
    with pytest.raises(PermanentJobError, match='configured live ingestion model'):
        await extract_scanned(pdf_with_empty_and_scanned_pages(), [(1, 'Native text')], uuid.uuid4())
