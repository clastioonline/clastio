"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ChapterSources } from "@/components/chapter-sources";
import { Alert, Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";
import { errorMessage, useToast } from "@/components/toast";

export default function BooksPage() {
  const {data,mutate,error}=useApi<any>("/books");
  const {notify}=useToast();
  const [selected,setSelected]=useState<string[]>([]);
  const [query,setQuery]=useState("");
  const [results,setResults]=useState("");
  const [cached,setCached]=useState(false);
  const [busy,setBusy]=useState("");
  const [jobId,setJobId]=useState<string|null>(null);
  const job=useJob(jobId, result=>{mutate();setJobId(null);if(result.status==="failed")notify({tone:"error",title:"Book import failed",body:result.error || "Check the PDF link."});});
  const [form,setForm]=useState({title:"",url:"",grade:"",subject:"",curriculum:"",edition:"",language:"en",rights_confirmed:false});
  const [chapters,setChapters]=useState<Record<string,{title:string;start:string;end:string}>>({});
  useEffect(()=>{if(!data?.items?.some((book:any)=>["queued","processing"].includes(book.status)))return;const timer=setInterval(()=>mutate(),2500);return()=>clearInterval(timer);},[data,mutate]);
  async function search(){setBusy("search");try{const result=await api<any>("/books/discover",{body:{query}});setResults(result.results);setCached(result.cached);}catch(error){notify({tone:"error",title:"Couldn't find books",body:errorMessage(error)});}finally{setBusy("");}}
  async function save(){setBusy("import");try{const result=await api<any>("/books/import",{body:form});setJobId(result.job_id);notify({tone:"info",title:"Saving your PDF",body:"The saved book will appear below and can be reused for future chapters."});}catch(error){notify({tone:"error",title:"Couldn't save book",body:errorMessage(error)});}finally{setBusy("");}}
  async function saveChapter(id:string){const item=chapters[id];if(!item)return;try{await api(`/books/${id}/chapters`,{body:{title:item.title,start:Number(item.start),end:Number(item.end)}});await mutate();notify({tone:"success",title:"Chapter pages saved"});}catch(error){notify({tone:"error",title:"Couldn't save chapter",body:errorMessage(error)});}}
  const links=Array.from(new Set(results.match(/https:\/\/[^\s<>\])]+/g)||[])).filter(link=>{try{return /\.pdf(?:\?|$)/i.test(link)&&!!new URL(link).hostname;}catch{return false;}});
  return <div className="mx-auto max-w-5xl space-y-5">
    <PageHeader title="Books & notes" subtitle="Save a PDF once. Reuse the saved book and its indexed chapters without searching or uploading again." />
    <Card className="space-y-4 p-5"><h2 className="font-semibold">Find a textbook online</h2><Field label="Book, curriculum, grade and language"><Input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Grade 10 UAE MoE mathematics, English, current edition" /></Field><Button loading={busy==="search"} disabled={query.trim().length<5||!!busy} onClick={search}>Find books</Button>
      {results&&<div className="space-y-3"><p className="text-xs text-muted">{cached?"Saved search results — no new research call.":"Check the publisher, curriculum and edition before saving."}</p><p className="whitespace-pre-wrap break-words text-sm">{results}</p>{links.map(link=><Button key={link} size="sm" variant="outline" onClick={()=>setForm({...form,url:link})}>Use PDF link: {new URL(link).hostname}</Button>)}</div>}
    </Card>
    <Card className="space-y-4 p-5"><h2 className="font-semibold">Save an online PDF</h2><div className="grid gap-3 sm:grid-cols-2">{([['title','Book title'],['url','Direct PDF URL'],['grade','Grade'],['subject','Subject'],['curriculum','Curriculum'],['edition','Edition / academic year'],['language','Language']] as const).map(([key,label])=><Field key={key} label={label}><Input value={form[key]} onChange={event=>setForm({...form,[key]:event.target.value})} /></Field>)}</div><label className="flex gap-2 text-sm"><input type="checkbox" checked={form.rights_confirmed} onChange={event=>setForm({...form,rights_confirmed:event.target.checked})}/>I have permission to use this PDF for teaching.</label><Button loading={busy==="import"} disabled={!form.title||!form.url||!form.rights_confirmed||!!busy||!!jobId} onClick={save}>Save PDF once</Button>{jobId&&<Alert tone="brand">{job?.stage||"Saving the PDF in the background"}. Follow progress in <Link href="/activity" className="underline">Activity</Link>.</Alert>}</Card>
    <ChapterSources uploadOnly value={selected} onChange={setSelected} onBlocked={()=>{}}/>
    {error&&<Alert tone="danger">Your saved books could not be loaded. <button onClick={()=>mutate()}>Retry</button></Alert>}
    {(data?.items||[]).map((book:any)=><Card key={book.id} className="space-y-3 p-5"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">{book.metadata?.title||book.filename}</h2><Button variant="outline" size="sm" href={book.download}>Open saved file</Button></div><p className="text-sm text-muted">{[book.metadata?.curriculum,book.metadata?.grade&&`Grade ${book.metadata.grade}`,book.metadata?.edition,book.metadata?.language,book.status,book.page_count&&`${book.page_count} PDF pages`].filter(Boolean).join(" · ")}</p>{book.error&&<Alert tone="warn">{book.error}</Alert>}{book.chapters?.map((chapter:any,index:number)=><p key={index} className="text-sm">{chapter.title} · PDF pages {chapter.start}–{chapter.end}</p>)}
      {book.status==="ready"&&<><p className="text-xs text-muted">Save chapter ranges using PDF page numbers, including the cover. Select a saved chapter when creating your lesson sequence.</p><div className="grid gap-2 sm:grid-cols-[1fr_100px_100px_auto]">{(['title','start','end'] as const).map(key=><Input key={key} aria-label={`${book.filename} chapter ${key}`} type={key==="title"?"text":"number"} min={1} max={book.page_count} placeholder={key==="title"?"Chapter name":key==="start"?"First page":"Last page"} value={chapters[book.id]?.[key]||""} onChange={event=>setChapters({...chapters,[book.id]:{...(chapters[book.id]||{title:"",start:"",end:""}),[key]:event.target.value}})}/>)}<Button variant="outline" onClick={()=>saveChapter(book.id)}>Save chapter</Button></div></>}
    </Card>)}
  </div>;
}
