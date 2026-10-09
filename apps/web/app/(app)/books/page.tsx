"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BOOK_CURRICULA, BookLibraryCard, bookCurriculum, bookLanguage, type LibraryBook } from "@/components/book-library-card";
import { ChapterSources } from "@/components/chapter-sources";
import { Alert, Badge, Button, Card, Field, Input, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useCan, useJob } from "@/lib/hooks";
import { errorMessage, useToast } from "@/components/toast";
import { GRADES, SUBJECTS } from "@/lib/utils";

type Source = {label:string;url:string;access:string;note:string};
type Catalog = {items:(LibraryBook & {catalogue_id:string;license:string;license_url:string})[];
  directories:Record<string,{subject:string;sources:Source[]}[]>};
type SearchResult = {title:string;publisher:string;source_url:string;pdf_url:string|null;access:string;
  subject:string;grade:string;language:string;edition:string;curriculum:string};

export default function BooksPage() {
  const {data,mutate,error} = useApi<{items:LibraryBook[]}>("/books");
  const {data:catalog,mutate:refreshCatalog,error:catalogError} = useApi<Catalog>("/books/catalogue");
  const can = useCan();
  const {notify} = useToast();
  const [selected,setSelected] = useState<string[]>([]);
  // UAE is a location: choose a curriculum explicitly instead of guessing from a search query.
  const [curriculum,setCurriculum] = useState("moe");
  const [subject,setSubject] = useState("");
  const [grade,setGrade] = useState("");
  const [language,setLanguage] = useState("");
  const [availability,setAvailability] = useState("all");
  const [query,setQuery] = useState("");
  const [searchBooks,setSearchBooks] = useState<SearchResult[]>([]);
  const [searchMessage,setSearchMessage] = useState("");
  const [cached,setCached] = useState(false);
  const [busy,setBusy] = useState("");
  const [jobId,setJobId] = useState<string|null>(null);
  const [form,setForm] = useState({title:"",url:"",grade:"",subject:"",curriculum:"moe",edition:"",language:"en",rights_confirmed:false});
  const [importOpen,setImportOpen] = useState(false);
  const refresh = async () => { await Promise.all([mutate(),refreshCatalog()]); };
  const job = useJob(jobId, async result => {
    await refresh(); setJobId(null);
    if (result.status === "failed") notify({tone:"error",title:"Couldn't add book",body:result.error || "Check the PDF link or storage allowance."});
  });
  useEffect(() => {
    if (!data?.items.some(book => ["queued","processing"].includes(book.status))) return;
    const timer = setInterval(() => mutate(),2500); return () => clearInterval(timer);
  },[data,mutate]);
  function changeScope(value:string, set:(value:string)=>void) { set(value); setSearchBooks([]); setSearchMessage(""); }
  async function search() {
    setBusy("search");
    try { const result = await api<any>("/books/discover",{body:{query,curriculum,subject,grade,language}});
      setSearchBooks(result.books || []); setSearchMessage(result.unavailable_reason || ""); setCached(result.cached);
    } catch(error) { notify({tone:"error",title:"Couldn't find books",body:errorMessage(error)}); }
    finally { setBusy(""); }
  }
  async function save() {
    setBusy("import");
    try { const result = await api<any>("/books/import",{body:form}); setJobId(result.job_id);
      notify({tone:"info",title:"Saving your PDF",body:"The book will stay in your library for future lessons."});
    } catch(error) { notify({tone:"error",title:"Couldn't save book",body:errorMessage(error)}); }
    finally { setBusy(""); }
  }
  async function addShared(id:string) {
    setBusy(id);
    try { const result = await api<any>(`/books/catalogue/${id}/save`,{body:{}}); setJobId(result.job_id); }
    catch(error) { notify({tone:"error",title:"Couldn't add book",body:errorMessage(error)}); }
    finally { setBusy(""); }
  }
  const scopeMatches = (book:LibraryBook) => bookCurriculum(book) === curriculum &&
    (!subject || book.metadata?.subject === subject) && (!grade || book.metadata?.grade === grade) &&
    (!language || bookLanguage(book) === language);
  const saved = (data?.items || []).filter(scopeMatches);
  const shared = (catalog?.items || []).filter(scopeMatches);
  const visibleSaved = saved.filter(book => availability !== "ready" || book.status === "ready");
  const unclassified = (data?.items || []).filter(book => !bookCurriculum(book));
  const directories = (catalog?.directories?.[curriculum] || []).filter(item => !subject || item.subject === subject);
  const label = BOOK_CURRICULA.find(item => item.code === curriculum)?.label;
  const sharedAvailable = shared.filter(book => !saved.some(item => item.metadata?.catalogue_source_id === book.id || item.id === book.id));
  const available = [...saved.filter(book => book.status === "ready"), ...sharedAvailable];
  const readyCount = available.length;
  return <div className="mx-auto max-w-6xl space-y-5">
    <PageHeader title="Books & notes" subtitle="Browse by curriculum and subject. Saved PDFs and published catalogue books are ready to reuse without a new search."/>
    <Card className="space-y-4 p-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Field label="Book curriculum"><Select aria-label="Book curriculum" value={curriculum} onChange={e => changeScope(e.target.value,setCurriculum)}>{BOOK_CURRICULA.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}</Select></Field>
        <Field label="Book subject"><Select aria-label="Book subject" value={subject} onChange={e => changeScope(e.target.value,setSubject)}><option value="">All subjects</option>{SUBJECTS.map(item => <option key={item}>{item}</option>)}</Select></Field>
        <Field label="Book grade / year"><Select aria-label="Book grade / year" value={grade} onChange={e => changeScope(e.target.value,setGrade)}><option value="">All grades / years</option>{[...GRADES,"13"].map(item => <option key={item}>{item}</option>)}</Select></Field>
        <Field label="Book language"><Select aria-label="Book language" value={language} onChange={e => changeScope(e.target.value,setLanguage)}><option value="">All languages</option><option value="en">English</option><option value="ar">Arabic</option></Select></Field>
        <Field label="Book availability"><Select aria-label="Book availability" value={availability} onChange={e => setAvailability(e.target.value)}><option value="all">Books and official sources</option><option value="ready">Saved PDFs only</option></Select></Field>
      </div>
      <p className="text-sm text-muted">{label} · {readyCount} saved PDF{readyCount === 1 ? "" : "s"} available in this selection. NCERT appears only under Indian — CBSE.</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => {setForm({...form,curriculum,subject,grade,language:language || "en"});setImportOpen(!importOpen);}}>Save a PDF</Button><Button variant="outline" href="/projects/new">Create lessons from a saved book</Button></div>
    </Card>
    {catalogError && <Alert tone="danger">The shared catalogue could not be loaded. <button className="underline" onClick={() => refreshCatalog()}>Retry</button></Alert>}
    {error && <Alert tone="danger">Your saved books could not be loaded. <button className="underline" onClick={() => mutate()}>Retry</button></Alert>}
    {jobId && <Alert tone="brand">{job?.stage || "Adding your book in the background"}. Follow progress in <Link href="/activity" className="underline">Activity</Link>.</Alert>}
    <section className="space-y-3" aria-label="Available book PDFs">
      <h2 className="text-lg font-semibold">Available PDFs · {label}</h2>
      {visibleSaved.map(book => <BookLibraryCard key={book.id} book={book} canPublish={can("settings.modify")} onSaved={refresh}/>)}
      {sharedAvailable.map(book => <Card key={book.id} className="space-y-3 p-5">
        <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="break-words font-semibold">{book.metadata?.title || book.filename}</h3><Badge tone="success">Shared PDF ready</Badge></div>
        <p className="text-sm text-muted">{[book.metadata?.subject,`Grade ${book.metadata?.grade}`,book.metadata?.language,book.metadata?.edition].join(" · ")}</p>
        <p className="break-words text-xs text-muted">{book.license} · <a href={book.license_url} target="_blank" rel="noopener noreferrer" className="underline">Licence / permission</a></p>
        <div className="flex flex-wrap gap-2"><Button href={book.download} variant="outline">Open catalogue PDF</Button><Button loading={busy === book.id} disabled={!!busy || !!jobId} onClick={() => addShared(book.id)}>Add to my library</Button></div>
      </Card>)}
      {visibleSaved.length === 0 && shared.length === 0 && <Alert tone="neutral" title="No saved PDF in this selection">The subject directory below shows official sources. A source link does not mean its PDF is stored in Clastio. Save an authorised copy once, or use a book published by your administrator.</Alert>}
    </section>
    {availability !== "ready" && <section className="space-y-3" aria-label="Curriculum subject directory">
      <h2 className="text-lg font-semibold">Subject directory · {label}</h2>
      <p className="text-sm text-muted">Official library and publisher destinations. Books, grade coverage and editions depend on your school; a directory is not a complete textbook collection.</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{directories.map(item => {
        const count = available.filter(book => book.metadata?.subject === item.subject).length;
        return <Card key={item.subject} className="flex min-w-0 flex-col gap-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><button className="text-left font-semibold" onClick={() => setSubject(item.subject)}>{item.subject}</button><Badge tone={count ? "success" : "neutral"}>{count} saved PDF{count === 1 ? "" : "s"}</Badge></div>
          {item.sources.map(source => <div key={source.url} className="space-y-1 text-sm"><a href={source.url} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-700 underline">{source.label}</a><p className="text-xs text-muted">{source.note}</p></div>)}
          {!item.sources.length && <p className="text-sm text-muted">Use the textbook prescribed by your school.</p>}
          <Button variant="outline" size="sm" onClick={() => {setForm({...form,curriculum,subject:item.subject,grade,language:language || "en"});setImportOpen(true);}}>Save {item.subject} PDF</Button>
        </Card>;
      })}</div>
    </section>}
    {importOpen && <Card className="space-y-4 p-5">
      <h2 className="font-semibold">Save an online PDF</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {([["title","Book title"],["url","Direct PDF URL"],["grade","Grade"],["edition","Edition / academic year"],["language","Language"]] as const).map(([key,text]) => <Field key={key} label={text}><Input value={form[key]} onChange={e => setForm({...form,[key]:e.target.value})}/></Field>)}
        <Field label="PDF curriculum"><Select aria-label="PDF curriculum" value={form.curriculum} onChange={e => setForm({...form,curriculum:e.target.value})}>{BOOK_CURRICULA.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}</Select></Field>
        <Field label="PDF subject"><Select aria-label="PDF subject" value={form.subject} onChange={e => setForm({...form,subject:e.target.value})}><option value="">Choose subject</option>{SUBJECTS.map(item => <option key={item}>{item}</option>)}</Select></Field>
      </div>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={form.rights_confirmed} onChange={e => setForm({...form,rights_confirmed:e.target.checked})}/>I have permission to use this PDF for teaching.</label>
      <Button loading={busy === "import"} disabled={!form.title || !form.url || !form.subject || !form.grade || !form.rights_confirmed || !!busy || !!jobId} onClick={save}>Save PDF once</Button>
    </Card>}
    <ChapterSources uploadOnly value={selected} onChange={setSelected} onBlocked={() => {}}/>
    {unclassified.length > 0 && <details className="space-y-3 rounded-xl border border-line p-5"><summary className="cursor-pointer font-semibold">Uncategorised saved files ({unclassified.length})</summary><p className="my-3 text-sm text-muted">Choose a curriculum, subject, grade and edition in book details. Files are not assumed to be UAE MoE books.</p>{unclassified.map(book => <div key={book.id} className="mt-3"><BookLibraryCard book={book} canPublish={can("settings.modify")} onSaved={refresh}/></div>)}</details>}
    <details className="rounded-xl border border-line p-5">
      <summary className="cursor-pointer font-semibold">Find an additional book online</summary>
      <div className="mt-4 space-y-3"><p className="text-sm text-muted">Search only {label}{subject ? ` · ${subject}` : ""}{grade ? ` · Grade ${grade}` : ""}. Searches are cached; browsing the catalogue makes no AI search call.</p>
        <Field label="Book, curriculum, grade and language"><Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Enter the prescribed book title or edition"/></Field>
        <Button loading={busy === "search"} disabled={query.trim().length < 5 || !!busy} onClick={search}>Find books</Button>
        {cached && <p className="text-xs text-muted">Saved search results — no new research call.</p>}
        {searchMessage && <Alert tone="neutral">{searchMessage}</Alert>}
        {searchBooks.map((book,index) => <Card key={index} className="space-y-2 p-4"><h3 className="font-semibold">{book.title}</h3><p className="text-sm text-muted">{book.publisher} · {book.grade} · {book.edition} · {book.access.replaceAll("_"," ")}</p><a href={book.source_url} target="_blank" rel="noopener noreferrer" className="text-sm text-brand-700 underline">Open source</a>
          {book.pdf_url && <Button size="sm" variant="outline" onClick={() => {setForm({...form,title:book.title,url:book.pdf_url!,grade:book.grade,subject:book.subject,curriculum:book.curriculum,edition:book.edition,language:book.language,rights_confirmed:false});setImportOpen(true);}}>Use PDF link: {new URL(book.pdf_url).hostname}</Button>}
        </Card>)}
      </div>
    </details>
  </div>;
}
