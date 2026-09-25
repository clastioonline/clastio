import { Fragment, type ReactNode } from "react";

/** Minimal, safe markdown renderer for assistant replies (bold, italics, bullet lists, paragraphs, links). */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|https?:\/\/[^\s)]+)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={i++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("*")) out.push(<em key={i++}>{tok.slice(1, -1)}</em>);
    else out.push(<a key={i++} href={tok} className="text-brand-600 underline" target="_blank" rel="noreferrer">{tok.length > 48 ? tok.slice(0, 48) + "…" : tok}</a>);
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={blocks.length}>{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>);
      list = [];
    }
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*[-*•]\s+/.test(line)) list.push(line.replace(/^\s*[-*•]\s+/, ""));
    else {
      flush();
      if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>);
    }
  }
  flush();
  return <div className="prose-chat text-sm">{blocks.map((b, i) => <Fragment key={i}>{b}</Fragment>)}</div>;
}
