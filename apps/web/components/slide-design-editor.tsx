"use client";

import { useRef, useState } from "react";
import { Button, Field, Input, Select, Textarea } from "@/components/ui";

type ObjectInfo = { id: string; name: string; text?: string | null; x: number; y: number; width: number; height: number; font_size?: number; color?: string; font_family?: string; kind?: string; aspect_ratio?: number };
type Edits = Record<string, any>;

export function SlideDesignEditor({ objects, preview, edits, onChange }: { objects: ObjectInfo[]; preview?: string; edits: Edits; onChange: (value: Edits) => void }) {
  const [selected, setSelected] = useState("");
  const canvas = useRef<HTMLDivElement>(null);
  const draft = useRef(edits); draft.current = edits;
  const [past, setPast] = useState<Edits[]>([]);
  const [future, setFuture] = useState<Edits[]>([]);
  const [zoom, setZoom] = useState(100);
  const [snap, setSnap] = useState(true);
  const commit = (next: Edits, remember = true) => {
    if (remember) { setPast((items) => [...items.slice(-49), draft.current]); setFuture([]); }
    draft.current = next; onChange(next);
  };
  const undo = () => { const previous = past.at(-1); if (!previous) return; setFuture((items) => [...items, draft.current]); setPast(past.slice(0, -1)); commit(previous, false); };
  const redo = () => { const next = future.at(-1); if (!next) return; setPast((items) => [...items, draft.current]); setFuture(future.slice(0, -1)); commit(next, false); };
  const added = Object.entries(edits).filter(([id, edit]) => id.startsWith("custom-") && edit.object_type && !objects.some((item) => item.id === id)).map(([id, edit]) => ({ id, name: `Added ${edit.object_type}`, kind: edit.object_type, text: edit.text ?? "", x: .1, y: .1, width: .4, height: .15, ...edit } as ObjectInfo));
  const order = (id: string) => edits[id]?.layer === "back" ? -1 : edits[id]?.layer === "front" ? 1 : 0;
  const items = [...objects, ...added].filter((item) => !edits[item.id]?.hidden).sort((a, b) => order(a.id) - order(b.id));
  const insert = (kind: string) => { const id = `custom-${crypto.randomUUID()}`; commit({ ...draft.current, [id]: { object_type: kind, x: .15, y: .2, width: .4, height: .15, text: kind === "text" ? "Your text" : "", font_size: 24, color: "#1f2937", ...(kind !== "text" ? { fill: "#dbeafe" } : {}) } }); setSelected(id); };
  const active = items.find((item) => item.id === selected);
  const value = active ? { ...active, ...edits[active.id] } : null;
  const patch = (id: string, change: any, remember = true) => commit({ ...draft.current, [id]: { ...draft.current[id], ...change } }, remember);
  const drag = (event: React.PointerEvent, item: ObjectInfo, resize = false) => {
    event.preventDefault(); event.stopPropagation(); setSelected(item.id);
    const bounds = canvas.current?.getBoundingClientRect();
    if (!bounds) return;
    const before = draft.current;
    const origin = { ...item, ...draft.current[item.id] };
    const startX = event.clientX, startY = event.clientY;
    const target = event.currentTarget as HTMLElement;
    target.setPointerCapture(event.pointerId);
    const move = (next: PointerEvent) => {
      const quantize = (value: number) => snap ? Math.round(value * 100) / 100 : value;
      const dx = quantize((next.clientX - startX) / bounds.width), dy = quantize((next.clientY - startY) / bounds.height);
      patch(item.id, resize ? { width: Math.max(.01, Math.min(1 - origin.x, origin.width + dx)), height: Math.max(.01, Math.min(1 - origin.y, origin.height + dy)) }
        : { x: Math.max(0, Math.min(1 - origin.width, origin.x + dx)), y: Math.max(0, Math.min(1 - origin.height, origin.y + dy)) }, false);
    };
    const stop = () => { if (draft.current !== before) { setPast((items) => [...items.slice(-49), before]); setFuture([]); } target.removeEventListener("pointermove", move); target.removeEventListener("pointerup", stop); target.removeEventListener("pointercancel", stop); };
    target.addEventListener("pointermove", move); target.addEventListener("pointerup", stop); target.addEventListener("pointercancel", stop);
  };
  return <div className="space-y-3 rounded-xl border border-line p-3">
    <div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto font-semibold">Design canvas</h3>
      <Button size="sm" variant="outline" disabled={!past.length} onClick={undo}>Undo</Button>
      <Button size="sm" variant="outline" disabled={!future.length} onClick={redo}>Redo</Button>
      <label className="text-xs"><input type="checkbox" checked={snap} onChange={(e) => setSnap(e.target.checked)} /> Snap to grid</label>
      <Select aria-label="Canvas zoom" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} className="w-24 shrink-0">{[75, 100, 125, 150, 200].map((n) => <option key={n} value={n}>{n}%</option>)}</Select>
    </div>
    <p className="text-xs text-muted">Select an object to edit its text and formatting below. Double-click text to start editing. Drag its frame to move it, or drag the corner to resize. Draft overlays appear over the saved slide; Save &amp; rebuild refreshes the exact PowerPoint preview.</p>
    <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => insert("text")}>Insert text box</Button><Button size="sm" variant="outline" onClick={() => insert("rectangle")}>Rectangle</Button><Button size="sm" variant="outline" onClick={() => insert("ellipse")}>Ellipse</Button></div>
    {!objects.length && <p className="text-sm">Save this slide once to load its editable objects.</p>}
    <div className="overflow-auto rounded-lg bg-surface-2 p-2"><div ref={canvas} className="relative overflow-hidden rounded border border-line bg-surface-2" style={{ aspectRatio: objects[0]?.aspect_ratio || 16 / 9, width: `${zoom}%`, minWidth: 0 }}>
      {preview && <img src={preview} alt="Current saved slide design" className="h-full w-full object-fill" draggable={false} />}
      {items.map((item) => {
        const position = { ...item, ...edits[item.id] };
        return <div key={item.id} role="button" tabIndex={0} aria-label={`Select ${item.name}`} onClick={() => setSelected(item.id)} onDoubleClick={() => { setSelected(item.id); window.setTimeout(() => document.getElementById(`object-text-${item.id}`)?.focus(), 0); }} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelected(item.id); }} onPointerDown={(event) => drag(event, item)}
          className={`absolute cursor-move touch-none border ${selected === item.id ? "border-brand-600 bg-brand-100/20" : "border-transparent hover:border-brand-300"}`}
          style={{ left: `${position.x * 100}%`, top: `${position.y * 100}%`, width: `${position.width * 100}%`, height: `${position.height * 100}%`, transform: `rotate(${position.rotation || 0}deg)`, background: position.fill, borderRadius: position.object_type === "ellipse" ? "50%" : undefined }}>
          {edits[item.id]?.text !== undefined && <div className="h-full w-full overflow-hidden whitespace-pre-wrap p-1" style={{ background: position.object_type ? "transparent" : "white", fontStyle: position.italic ? "italic" : "normal", color: position.color || "#000000", fontFamily: position.font_family, fontSize: `${(position.font_size || 20) * 0.8}px`, fontWeight: position.bold ? "bold" : "normal" }}>{position.text}</div>}
          {selected === item.id && <span onPointerDown={(event) => drag(event, item, true)} className="absolute -bottom-1 -right-1 h-3 w-3 cursor-se-resize bg-brand-600" />}
        </div>;
      })}
    </div></div>
    <Field label="Slide object"><Select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">Select an object</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name}{item.text ? ` · ${item.text.slice(0, 40)}` : ""}</option>)}</Select></Field>
    {active && value && <>
      {(active.text != null || active.kind === "table") && <>{active.text != null && <Field label="Object text"><Textarea id={`object-text-${active.id}`} value={value.text || ""} onChange={(event) => patch(active.id, { text: event.target.value })} /></Field>}
        <div className="grid grid-cols-2 gap-2"><Field label="Text color"><Input type="color" value={value.color || "#000000"} onChange={(event) => patch(active.id, { color: event.target.value })} /></Field><Field label="Font size (pt)"><Input type="number" min={8} max={120} value={value.font_size || ""} placeholder="Template" onChange={(event) => patch(active.id, { font_size: event.target.value ? Number(event.target.value) : null })} /></Field></div>
        <Field label="Font family"><Input value={value.font_family || ""} placeholder="Template font" onChange={(event) => patch(active.id, { font_family: event.target.value || null })} /></Field>
        <Button size="sm" variant="outline" onClick={() => patch(active.id, { bold: !value.bold })}>{value.bold ? "Remove bold" : "Make bold"}</Button>
      </>}
      <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => patch(active.id, { italic: !value.italic })}>Italic</Button><Button size="sm" variant="outline" onClick={() => patch(active.id, { layer: "front" })}>Bring to front</Button><Button size="sm" variant="outline" onClick={() => patch(active.id, { layer: "back" })}>Send to back</Button><Button size="sm" variant="ghost" onClick={() => { patch(active.id, { hidden: true }); setSelected(""); }}>Remove object</Button></div>
      <div className="grid grid-cols-2 gap-2"><Field label="Fill color"><Input type="color" value={value.fill || "#ffffff"} onChange={(event) => patch(active.id, { fill: event.target.value })} /></Field><Field label="Rotation (degrees)"><Input type="number" min={0} max={360} value={value.rotation || 0} onChange={(event) => patch(active.id, { rotation: Number(event.target.value) })} /></Field></div>
      <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => patch(active.id, { x: (1 - value.width) / 2 })}>Center horizontally</Button><Button size="sm" variant="outline" onClick={() => patch(active.id, { y: (1 - value.height) / 2 })}>Center vertically</Button></div>
      <div className="grid grid-cols-2 gap-2">{["x", "y", "width", "height"].map((key) => <Field key={key} label={`${key} (%)`}><Input type="number" min={key === "width" || key === "height" ? 1 : 0} max={100} step={.5} value={Math.round(value[key] * 1000) / 10} onChange={(event) => patch(active.id, { [key]: Number(event.target.value) / 100 })} /></Field>)}</div>
      <Button size="sm" variant="ghost" onClick={() => { const next = { ...edits }; delete next[active.id]; commit(next); }}>Reset object to template</Button>
    </>}
  </div>;
}
