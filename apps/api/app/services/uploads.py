"""Upload validation and storage.

Checks (before anything touches a parser): size limit, magic bytes, OOXML structure, macro content,
zip-bomb ratios, optional ClamAV scan. Files are stored immutably under a content hash; the original
is never modified.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import re
import struct
import uuid
import zipfile
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.storage import get_storage
from app.models import UploadedFile

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"
PPT_MIME = "application/vnd.ms-powerpoint"

ALLOWED = {"style": {"pdf", "pptx", "ppt"}, "source": {"pdf", "pptx", "ppt", "docx", "txt"}}


@dataclass
class Detected:
    ext: str
    mime: str


class UploadRejected(AppError):
    def __init__(self, message: str):
        super().__init__("upload_rejected", message, 400)


def _check_zip(data: bytes, required: str, main_ct_ok: tuple[str, ...]) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise UploadRejected("The file is damaged or not a valid Office document.") from e
    infos = zf.infolist()
    if len(infos) > 5000:
        raise UploadRejected("The document contains too many parts.")
    total = sum(i.file_size for i in infos)
    packed = sum(i.compress_size for i in infos) or 1
    if total > 600 * 1024 * 1024 or total / packed > 250:
        raise UploadRejected("The document expands to an unsafe size.")
    names = {i.filename for i in infos}
    if "[Content_Types].xml" not in names or required not in names:
        raise UploadRejected("The file is not a valid Office document.")
    if any(n.lower().endswith("vbaproject.bin") for n in names):
        raise UploadRejected("Macro-enabled files are not accepted. Please save as a regular .pptx and try again.")
    ct = zf.read("[Content_Types].xml").decode("utf-8", "ignore")
    if "macroEnabled" in ct:
        raise UploadRejected("Macro-enabled files are not accepted.")
    if not any(m in ct for m in main_ct_ok):
        raise UploadRejected("Unsupported Office document type.")


def detect(filename: str, data: bytes) -> Detected:
    head = data[:8]
    if head.startswith(b"%PDF-"):
        return Detected("pdf", PDF_MIME)
    if head.startswith(b"PK\x03\x04"):
        names = zipfile.ZipFile(io.BytesIO(data)).namelist() if len(data) < 800 * 1024 * 1024 else []
        if "ppt/presentation.xml" in names:
            _check_zip(data, "ppt/presentation.xml", ("presentationml.presentation.main+xml",
                                                      "presentationml.slideshow.main+xml",
                                                      "presentationml.template.main+xml"))
            return Detected("pptx", PPTX_MIME)
        if "word/document.xml" in names:
            _check_zip(data, "word/document.xml", ("wordprocessingml.document.main+xml",))
            return Detected("docx", DOCX_MIME)
        raise UploadRejected("Unsupported ZIP-based file.")
    if head == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        if filename.lower().endswith((".ppt", ".pps", ".pot")):
            return Detected("ppt", PPT_MIME)
        raise UploadRejected("Legacy Office files other than .ppt are not supported.")
    if filename.lower().endswith(".txt"):
        try:
            data[:200_000].decode("utf-8")
            return Detected("txt", "text/plain")
        except UnicodeDecodeError as e:
            raise UploadRejected("Text files must be UTF-8.") from e
    raise UploadRejected("Unsupported file type. Please upload a PDF, PPT or PPTX file.")


async def clamav_scan(data: bytes) -> None:
    s = get_settings()
    if not s.clamd_host:
        return
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(s.clamd_host, s.clamd_port), 5)
    except (OSError, TimeoutError) as e:
        raise AppError("scan_unavailable", "Virus scanning is temporarily unavailable. Try again shortly.", 503) from e
    writer.write(b"zINSTREAM\0")
    for i in range(0, len(data), 64 * 1024):
        chunk = data[i: i + 64 * 1024]
        writer.write(struct.pack(">I", len(chunk)) + chunk)
    writer.write(struct.pack(">I", 0))
    await writer.drain()
    reply = (await asyncio.wait_for(reader.read(1024), 60)).decode(errors="ignore")
    writer.close()
    if "FOUND" in reply:
        raise UploadRejected("The file was flagged by the virus scanner and was not uploaded.")


_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    name = _SAFE.sub("_", name).strip() or "upload"
    return name[:180]


async def store_upload(db: AsyncSession, *, owner_id: uuid.UUID, filename: str, data: bytes, kind: str,
                       rights_confirmed: bool = False) -> tuple[UploadedFile, bool]:
    """Validate + store. Returns (file, is_new). Re-uploading the same bytes returns the existing row."""
    settings = get_settings()
    if len(data) == 0:
        raise UploadRejected("The file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadRejected(f"Files must be smaller than {settings.max_upload_mb} MB.")
    det = detect(filename, data)
    if det.ext not in ALLOWED.get(kind, set()):
        raise UploadRejected(f"{det.ext.upper()} files can't be used here.")
    await clamav_scan(data)
    sha = hashlib.sha256(data).hexdigest()
    existing = (await db.execute(select(UploadedFile).where(
        UploadedFile.owner_id == owner_id, UploadedFile.sha256 == sha, UploadedFile.kind == kind))).scalars().first()
    if existing:
        return existing, False
    clean = safe_filename(filename)
    if not clean.lower().endswith("." + det.ext):
        clean = f"{clean}.{det.ext}"
    key = f"uploads/{owner_id}/{sha[:2]}/{sha}.{det.ext}"
    await get_storage().put(key, data, det.mime)
    row = UploadedFile(owner_id=owner_id, filename=clean, mime=det.mime, kind=kind, size_bytes=len(data), sha256=sha,
                       storage_key=key, status="queued", stage="Uploaded", content_rights_confirmed=rights_confirmed)
    db.add(row)
    await db.flush()
    return row, True
