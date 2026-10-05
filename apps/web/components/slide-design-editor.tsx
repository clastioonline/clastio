"use client";

import { useRef, useState } from "react";
import { Button, Field, Input, Select, Textarea } from "@/components/ui";

type ObjectInfo = { id: string; name: string; text?: string | null; x: number; y: number; width: number; height: number; font_size?: number; color?: string; font_family?: string; kind?: string; aspect_ratio?: number };
type Edits = Record<string, any>;

export function SlideDesignEditor({ objects, preview, edits, onChange }: { objects: ObjectInfo[]; preview?: string; edits: Edits; onChange: (value: Edits) => void }) {
  const [selected, setSelected] = useState("");
  const canvas = useRef<HTMLDivElement>(null);
  const active = objects.find((item) => item.id === selected);
  const value = active ? { ...active, ...edits[active.id] } : null;
  const patch = (id: string, change: any) => onChange({ ...edits, [id]: { ...edits[id], ...change } });
  const drag = (event: React.PointerEvent, item: ObjectInfo, resize = false) => {
    event.preventDefault(); event.stopPropagation(); setSelected(item.id);
    const bounds = canvas.current?.getBoundingClientRect();
    if (!bounds) return;
    const origin = { ...item, ...edits[item.id] };
    const startX = event.clientX, startY = event.clientY;
    const target = event.currentTarget as HTMLElement;
    target.setPointerCapture(event.pointerId);
    const move = (next: PointerEvent) => {
      const dx = (next.clientX - startX) / bounds.width, dy = (next.clientY - startY) / bounds.height;
      patch(item.id, resize ? { width: Math.max(.01, Math.min(1 - origin.x, origin.width + dx)), height: Math.max(.01, Math.min(1 - origin.y, origin.height + dy)) }
        : { x: Math.max(0, Math.min(1 - origin.width, origin.x + dx)), y: Math.max(0, Math.min(1 - origin.height, origin.y + dy)) });
    };
    const stop = () => { target.removeEventListener("pointermove", move); target.removeEventListener("pointerup", stop); target.removeEventListener("pointercancel", stop); };
    target.addEventListener("pointermove", move); target.addEventListener("pointerup", stop); target.addEventListener("pointercancel", stop);
  };
  return <div className="space-y-3 rounded-xl border border-line p-3">
    <h3 className="font-semibold">Design canvas</h3>
    <p className="text-xs text-muted">Select an object, drag its frame to move it, or drag the corner to resize. Save &amp; rebuild applies changes to the PPT and refreshes the preview.</p>
    {!objects.length && <p className="text-sm">Save this slide once to load its editable objects.</p>}
    <div ref={canvas} className="relative overflow-hidden rounded border border-line bg-surface-2" style={{ aspectRatio: objects[0]?.aspect_ratio || 16 / 9 }}>
      {preview && <img src={preview} alt="Current saved slide design" className="h-full w-full object-fill" draggable={false} />}
      {objects.map((item) => {
        const position = { ...item, ...edits[item.id] };
        return <div key={item.id} role="button" tabIndex={0} aria-label={`Select ${item.name}`} onClick={() => setSelected(item.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelected(item.id); }} onPointerDown={(event) => drag(event, item)}
          className={`absolute cursor-move touch-none border ${selected === item.id ? "border-brand-600 bg-brand-100/20" : "border-transparent hover:border-brand-300"}`}
          style={{ left: `${position.x * 100}%`, top: `${position.y * 100}%`, width: `${position.width * 100}%`, height: `${position.height * 100}%` }}>
          {selected === item.id && <span onPointerDown={(event) => drag(event, item, true)} className="absolute -bottom-1 -right-1 h-3 w-3 cursor-se-resize bg-brand-600" />}
        </div>;
      })}
    </div>
    <Field label="Slide object"><Select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">Select an object</option>{objects.map((item) => <option key={item.id} value={item.id}>{item.name}{item.text ? ` · ${item.text.slice(0, 40)}` : ""}</option>)}</Select></Field>
    {active && value && <>
      {(active.text != null || active.kind === "table") && <>{active.text != null && <Field label="Object text"><Textarea value={value.text || ""} onChange={(event) => patch(active.id, { text: event.target.value })} /></Field>}
        <div className="grid grid-cols-2 gap-2"><Field label="Text color"><Input type="color" value={value.color || "#000000"} onChange={(event) => patch(active.id, { color: event.target.value })} /></Field><Field label="Font size (pt)"><Input type="number" min={8} max={120} value={value.font_size || ""} placeholder="Template" onChange={(event) => patch(active.id, { font_size: event.target.value ? Number(event.target.value) : null })} /></Field></div>
        <Field label="Font family"><Input value={value.font_family || ""} placeholder="Template font" onChange={(event) => patch(active.id, { font_family: event.target.value || null })} /></Field>
        <Button size="sm" variant="outline" onClick={() => patch(active.id, { bold: !value.bold })}>{value.bold ? "Remove bold" : "Make bold"}</Button>
      </>}
      <div className="grid grid-cols-2 gap-2">{["x", "y", "width", "height"].map((key) => <Field key={key} label={`${key} (%)`}><Input type="number" min={key === "width" || key === "height" ? 1 : 0} max={100} step={.5} value={Math.round(value[key] * 1000) / 10} onChange={(event) => patch(active.id, { [key]: Number(event.target.value) / 100 })} /></Field>)}</div>
      <Button size="sm" variant="ghost" onClick={() => { const next = { ...edits }; delete next[active.id]; onChange(next); }}>Reset object to template</Button>
    </>}
  </div>;
}
