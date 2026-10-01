"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";

export function TemplatePreview({ src, name }: { src?: string; name: string }) {
  const [failed, setFailed] = useState<string | undefined>();
  return <div className="relative aspect-[16/9] w-full overflow-hidden rounded-xl border border-line bg-surface-2">
    {src && failed !== src ? <img src={src} alt={name} className="h-full w-full object-contain" loading="lazy" onError={() => setFailed(src)} />
      : <div className="flex h-full flex-col items-center justify-center gap-2 p-3 text-center text-sm text-muted"><ImageOff className="h-6 w-6" /><span>Preview unavailable</span><span className="text-xs">You can still view this design’s settings.</span></div>}
  </div>;
}
