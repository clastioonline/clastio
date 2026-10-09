"use client";

import { useState } from "react";
import { Alert, Button, Card, Field, Input, Select } from "@/components/ui";
import { errorMessage, useToast } from "@/components/toast";
import { api } from "@/lib/api";
import { CURRICULA, GRADES, SUBJECTS } from "@/lib/utils";

export type LibraryBook = {
  id: string; filename: string; status: string; stage?: string; error?: string;
  page_count?: number; download: string;
  metadata?: Record<string, string>;
  catalogue?: { published?: boolean; license?: string; license_url?: string };
  chapters?: {title: string; start: number; end: number}[];
};
export const BOOK_CURRICULA = CURRICULA.filter(item => item.code !== "uae_ai");
export function bookCurriculum(book: LibraryBook) {
  const raw = (book.metadata?.curriculum || "").toLowerCase().trim();
  const matched = BOOK_CURRICULA.find(item => item.code === raw || item.label.toLowerCase() === raw);
  if (/ncert/i.test(`${book.filename} ${book.metadata?.title || ""}`)) return "cbse";
  if (matched) return matched.code;
  if (raw.includes("moe") || raw.includes("ministry")) return "moe";
  return "";
}

export function bookLanguage(book: LibraryBook) {
  const raw = (book.metadata?.language || "").toLowerCase().trim();
  return raw === "english" ? "en" : raw === "arabic" ? "ar" : raw;
}

export function BookLibraryCard({book, canPublish, onSaved}: {
  book: LibraryBook; canPublish: boolean; onSaved: () => Promise<unknown>;
}) {
  const {notify} = useToast();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState("");
  const [metadata, setMetadata] = useState({title: book.metadata?.title || book.filename,
    curriculum: bookCurriculum(book) || "moe", subject: book.metadata?.subject || "",
    grade: book.metadata?.grade || "", language: book.metadata?.language || "en", edition: book.metadata?.edition || ""});
  const [chapter, setChapter] = useState({title: "", start: "", end: ""});
  const [publication, setPublication] = useState({sharing_rights_confirmed: false,
    license: book.catalogue?.license || "", license_url: book.catalogue?.license_url || ""});
  async function action(name: string, work: () => Promise<unknown>, title: string) {
    setBusy(name);
    try { await work(); await onSaved(); notify({tone: "success", title}); }
    catch(error) { notify({tone: "error", title: "Couldn't save book details", body: errorMessage(error)}); }
    finally { setBusy(""); }
  }
  const label = BOOK_CURRICULA.find(item => item.code === bookCurriculum(book))?.label;
  return <Card className="space-y-3 p-5">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="min-w-0 break-words font-semibold">{book.metadata?.title || book.filename}</h3>
      <Button variant="outline" size="sm" href={book.download}>Open saved file</Button>
    </div>
    <p className="text-sm text-muted">{[label || "Curriculum not classified", book.metadata?.subject,
      book.metadata?.grade && `Grade ${book.metadata.grade}`, book.metadata?.edition,
      book.metadata?.language, book.status, book.page_count && `${book.page_count} PDF pages`].filter(Boolean).join(" · ")}</p>
    {book.error && <Alert tone="warn">{book.error}</Alert>}
    {book.catalogue?.published && <Alert tone="success">Published in the shared book catalogue.</Alert>}
    <Button variant="outline" size="sm" onClick={() => setEditing(!editing)}>{editing ? "Close book details" : "Edit book details"}</Button>
    {editing && <div className="space-y-3 rounded-xl border border-line p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={`Book title for ${book.filename}`}><Input value={metadata.title} onChange={e => setMetadata({...metadata, title:e.target.value})}/></Field>
        <Field label={`Curriculum for ${book.filename}`}><Select aria-label={`Curriculum for ${book.filename}`} value={metadata.curriculum} onChange={e => setMetadata({...metadata,curriculum:e.target.value})}>{BOOK_CURRICULA.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}</Select></Field>
        <Field label={`Subject for ${book.filename}`}><Select aria-label={`Subject for ${book.filename}`} value={metadata.subject} onChange={e => setMetadata({...metadata,subject:e.target.value})}><option value="">Choose subject</option>{SUBJECTS.map(item => <option key={item}>{item}</option>)}</Select></Field>
        <Field label={`Grade for ${book.filename}`}><Select aria-label={`Grade for ${book.filename}`} value={metadata.grade} onChange={e => setMetadata({...metadata,grade:e.target.value})}><option value="">Choose grade / year</option>{[...GRADES,"13"].map(item => <option key={item}>{item}</option>)}</Select></Field>
        <Field label={`Language for ${book.filename}`}><Input value={metadata.language} onChange={e => setMetadata({...metadata,language:e.target.value})}/></Field>
        <Field label={`Edition for ${book.filename}`}><Input placeholder="e.g. 2026–2027, Term 1" value={metadata.edition} onChange={e => setMetadata({...metadata,edition:e.target.value})}/></Field>
      </div>
      <Button loading={busy === "metadata"} disabled={!!busy || !metadata.title || !metadata.subject || !metadata.grade || !metadata.language}
        onClick={() => action("metadata", () => api(`/books/${book.id}/metadata`, {method:"PUT",body:metadata}), "Book details saved")}>Save book details</Button>
    </div>}
    {book.chapters?.map((item,index) => <p key={index} className="text-sm">{item.title} · PDF pages {item.start}–{item.end}</p>)}
    {book.status === "ready" && <>
      <p className="text-xs text-muted">Save chapter ranges using PDF page numbers, including the cover.</p>
      <div className="grid gap-2 sm:grid-cols-[1fr_100px_100px_auto]">
        {(["title","start","end"] as const).map(key => <Input key={key} aria-label={`${book.filename} chapter ${key}`} type={key === "title" ? "text" : "number"} min={1} max={book.page_count}
          placeholder={key === "title" ? "Chapter name" : key === "start" ? "First page" : "Last page"} value={chapter[key]} onChange={e => setChapter({...chapter,[key]:e.target.value})}/>)}
        <Button variant="outline" disabled={!!busy || !chapter.title || !chapter.start || !chapter.end} loading={busy === "chapter"}
          onClick={() => action("chapter", () => api(`/books/${book.id}/chapters`, {body:{title:chapter.title,start:Number(chapter.start),end:Number(chapter.end)}}), "Chapter pages saved")}>Save chapter</Button>
      </div>
    </>}
    {canPublish && book.status === "ready" && <details className="rounded-xl border border-line p-4">
      <summary className="cursor-pointer text-sm font-semibold">Share in the school book catalogue</summary>
      <div className="mt-3 space-y-3">
        <p className="text-sm text-muted">Classify the book and record its edition first. Only books with permission for all teachers can be shared.</p>
        <Field label={`Sharing licence for ${book.filename}`}><Input value={publication.license} onChange={e => setPublication({...publication,license:e.target.value})}/></Field>
        <Field label={`Permission reference URL for ${book.filename}`}><Input value={publication.license_url} onChange={e => setPublication({...publication,license_url:e.target.value})}/></Field>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={publication.sharing_rights_confirmed} onChange={e => setPublication({...publication,sharing_rights_confirmed:e.target.checked})}/>I have permission to share this PDF and reuse its content with all Clastio teachers.</label>
        <Button disabled={!!busy || !publication.sharing_rights_confirmed || !publication.license || !publication.license_url} loading={busy === "publish"}
          onClick={() => action("publish", () => api(`/books/${book.id}/publication`,{method:"PUT",body:{...publication,published:true}}), "Book published to the catalogue")}>Publish book</Button>
        {book.catalogue?.published && <Button variant="outline" disabled={!!busy} onClick={() => action("unpublish", () => api(`/books/${book.id}/publication`,{method:"PUT",body:{published:false}}),"Book removed from the catalogue")}>Unpublish book</Button>}
      </div>
    </details>}
  </Card>;
}
