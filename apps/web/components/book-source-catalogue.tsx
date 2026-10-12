"use client";

import { useState } from "react";
import { BOOK_CURRICULA } from "@/components/book-library-card";
import { Alert, Badge, Button, Card, Field, Input } from "@/components/ui";

export type TextbookCollection = {
  id: string; title: string; curriculum: string; publisher: string; source_url: string;
  access: string; note: string; education_stages: string[]; reviewed_on: string;
};
export type ReferenceBook = {
  id: string; title: string; publisher: string; curriculum: string; subjects: string[];
  grades: string[]; education_stages: string[]; language: string; edition: string;
  source_url: string; access: string; license: string; license_url: string;
  rights_note: string; curriculum_note: string; reviewed_on: string;
};
export type TextbookSources = { collections?: TextbookCollection[]; reference_books?: ReferenceBook[] };

const curriculumName = (code: string) => BOOK_CURRICULA.find(item => item.code === code)?.label || code;

export function BookSourceCatalogue({ catalogue, curriculum, subject, grade, language }: {
  catalogue: TextbookSources; curriculum: string; subject: string; grade: string; language: string;
}) {
  const [search, setSearch] = useState("");
  const [supplementary, setSupplementary] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const collections = (catalogue.collections || []).filter(item => item.curriculum === curriculum);
  const books = (catalogue.reference_books || []).filter(book =>
    (book.curriculum === curriculum || (supplementary && ["american", "other"].includes(book.curriculum))) &&
    (!subject || book.subjects.includes(subject)) && (!grade || !book.grades.length || book.grades.includes(grade)) &&
    (!language || book.language === language) &&
    (!search.trim() || `${book.title} ${book.publisher} ${book.subjects.join(" ")}`.toLowerCase().includes(search.trim().toLowerCase())));
  if (!catalogue.collections?.length && !catalogue.reference_books?.length) return null;
  return <section aria-label="Textbook source catalogue" className="space-y-4">
    <div><h2 className="text-lg font-semibold">Textbook catalogue · {curriculumName(curriculum)}</h2>
      <p className="text-sm text-muted">Open your school’s official collection or browse reviewed book titles. These links open the publisher; saved PDFs appear in your library below.</p></div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{collections.map(collection => <Card key={collection.id} className="flex min-w-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap gap-2"><Badge>{collection.access === "school_login" ? "School account" : "Official collection"}</Badge></div>
      <h3 className="font-semibold">{collection.title}</h3><p className="text-sm text-muted">{collection.note}</p>
      <a href={collection.source_url} target="_blank" rel="noopener noreferrer" className="focus-ring mt-auto text-sm font-semibold text-brand-700 underline">Browse official collection ↗</a>
    </Card>)}</div>
    <Card className="space-y-3 p-4">
      <Field label="Browse textbook titles" hint="Filter the catalogue instantly; no AI search is needed."><Input aria-label="Browse textbook titles" value={search} onChange={event => { setSearch(event.target.value); setShowAll(false); }} placeholder="Book title, subject or publisher…" /></Field>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={supplementary} onChange={event => { setSupplementary(event.target.checked); setShowAll(false); }} />Include supplementary references from other curricula</label>
      <p className="text-xs text-muted">{books.length} matching title{books.length === 1 ? "" : "s"}. References from another curriculum require a coverage check. Books with no exact school year appear by subject and level.</p>
    </Card>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{books.slice(0, showAll ? books.length : 12).map(book => <Card key={book.id} className="flex min-w-0 flex-col gap-3 p-4">
      <div className="flex flex-wrap gap-2"><Badge tone={book.access === "publisher" ? "neutral" : "brand"}>{book.access === "publisher" ? "Publisher access" : "Free online reading"}</Badge>{book.curriculum !== curriculum && <Badge>Supplementary reference</Badge>}</div>
      <h3 className="break-words font-semibold">{book.title}</h3>
      <p className="text-sm text-muted">{[book.publisher, book.subjects.join(" / "), book.grades.length ? `Grade ${book.grades.join(", ")}` : "Secondary / college reference", book.edition].filter(Boolean).join(" · ")}</p>
      <p className="text-xs text-muted">{book.curriculum_note}</p>
      <a href={book.source_url} target="_blank" rel="noopener noreferrer" className="focus-ring mt-auto text-sm font-semibold text-brand-700 underline">{book.access === "publisher" ? "View official book listing" : "Read on publisher website"} ↗</a>
      <details className="text-xs text-muted"><summary className="cursor-pointer font-medium">Usage rights & source</summary><div className="mt-2 space-y-2"><p>{book.rights_note}</p><a href={book.license_url} target="_blank" rel="noopener noreferrer" className="underline">{book.license}</a><p>Publisher source checked {book.reviewed_on}.</p></div></details>
    </Card>)}</div>
    {!books.length && <Alert tone="neutral">No reviewed title matches these filters. Browse the official collection above, or include supplementary references to find more reading.</Alert>}
    {books.length > 12 && <Button size="sm" variant="outline" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer titles" : `Show all ${books.length} matching titles`}</Button>}
  </section>;
}
