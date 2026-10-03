"use client";

import { useEffect, useRef, useState } from "react";
import { Upload, X } from "lucide-react";
import { Button, Card, CardHeader, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { errorMessage, useToast } from "@/components/toast";

export type TeacherImage = { asset_id: string; description: string };
export function TeacherImages({ value, onChange, onBlocked }: {
  value: TeacherImage[]; onChange: (images: TeacherImage[]) => void; onBlocked: (blocked: boolean) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const previews = useRef<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const { notify } = useToast();
  useEffect(() => { onBlocked(uploading || value.some((image) => image.description.trim().length < 2)); }, [uploading, value, onBlocked]);
  useEffect(() => () => { Object.values(previews.current).forEach(URL.revokeObjectURL); }, []);
  async function upload(files: FileList | null) {
    if (!files?.length || uploading) return;
    setUploading(true);
    let images = [...value];
    try {
      for (const file of Array.from(files)) {
        if (images.length >= 5) throw new Error("Choose up to 5 images per chapter.");
        if (file.size > 10 * 1024 * 1024) throw new Error("Each image must be 10 MB or smaller.");
        const form = new FormData(); form.append("file", file);
        const result = await api<{ asset_id: string }>("/slide-images", { form });
        if (images.some((image) => image.asset_id === result.asset_id)) continue;
        previews.current[result.asset_id] = URL.createObjectURL(file);
        images = [...images, { asset_id: result.asset_id, description: file.name.replace(/\.[^.]+$/, "").slice(0, 300).padEnd(2, " ") }];
        onChange(images);
      }
    } catch (error) {
      notify({ tone: "error", title: "Couldn't upload image", body: errorMessage(error) });
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }
  return <Card>
    <CardHeader title="Your images (optional)" subtitle="Upload photos, illustrations or diagrams for this chapter. Relevant images are preferred before search or generation." />
    <div className="space-y-4 p-5">
      <input ref={input} type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden" aria-label="Choose your PPT images" onChange={(e) => upload(e.target.files)} />
      <Button type="button" variant="outline" loading={uploading} disabled={uploading || value.length >= 5} onClick={() => input.current?.click()}><Upload className="h-4 w-4" /> Upload your images</Button>
      <p className="text-xs text-muted">Up to 5 PNG, JPEG or WebP images, 10 MB each (subject to your storage allowance). Describe what each picture shows and where you want it used. Upload images you have permission to use.</p>
      {value.map((image, i) => <div key={image.asset_id} className="flex items-start gap-3 rounded-xl border border-line p-3">
        {previews.current[image.asset_id] && <img src={previews.current[image.asset_id]} alt={`Uploaded image ${i + 1}`} className="h-20 w-24 rounded-lg object-contain" />}
        <div className="min-w-0 flex-1"><Field label={`Image ${i + 1}: content / placement`}><Input value={image.description} maxLength={300} disabled={uploading} onChange={(e) => onChange(value.map((item) => item.asset_id === image.asset_id ? {...item, description: e.target.value} : item))} placeholder="Leaf cross-section, use when explaining photosynthesis" /></Field></div>
        <button type="button" disabled={uploading} aria-label={`Remove image ${i + 1}`} onClick={() => { URL.revokeObjectURL(previews.current[image.asset_id]); delete previews.current[image.asset_id]; onChange(value.filter((item) => item.asset_id !== image.asset_id)); }}><X className="h-4 w-4" /></button>
      </div>)}
      <p className="text-xs text-muted">You can also upload or replace a picture on a specific slide in the lesson editor. Uploaded pictures do not consume AI image-generation credits.</p>
    </div>
  </Card>;
}
