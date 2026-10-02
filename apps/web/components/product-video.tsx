import { ArrowDownToLine, Play } from "lucide-react";

export function ProductVideo() {
  return <section id="product-video" aria-labelledby="product-video-title" className="mx-auto max-w-6xl scroll-mt-8 px-4 pb-20 sm:px-6">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl"><p className="flex items-center gap-2 text-sm font-semibold text-[#1b7446]"><Play className="h-4 w-4" aria-hidden="true" /> The 30-second tour</p><h2 id="product-video-title" className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Big ideas. A little less prep.</h2><p className="mt-3 text-[var(--l-muted)]">See how Clastio helps turn a teaching idea into resources you can review and make your own.</p></div>
    </div>
    <div className="overflow-hidden rounded-2xl border border-[var(--l-line)] bg-[#f8f5ed] shadow-lg sm:rounded-[2rem]">
      <video className="aspect-video w-full" controls playsInline preload="none" poster="/videos/clastio-doodle-web-poster.jpg" aria-label="Clastio: a 30-second animated product tour" aria-describedby="video-description">
        <source src="/videos/clastio-doodle-web.mp4" type="video/mp4" />
        <track kind="captions" src="/videos/clastio-doodle.vtt" srcLang="en" label="English" />
        Your browser cannot play this video. <a href="/videos/clastio-doodle-web.mp4">Download the product tour</a>.
      </video>
    </div>
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--l-muted)]"><p id="video-description">Illustrated product tour · Music and on-screen captions · No autoplay</p><a href="/videos/clastio-doodle-vertical.mp4" download className="focus-ring inline-flex items-center gap-2 rounded-lg px-2 py-2 font-medium text-[#1b7446]"><ArrowDownToLine className="h-4 w-4" aria-hidden="true" /> Download vertical version</a></div>
    <details className="mt-3 rounded-xl border border-[var(--l-line)] p-4 text-sm"><summary className="focus-ring cursor-pointer rounded font-medium">Read the video transcript</summary><div className="mt-3 space-y-2 leading-relaxed text-[var(--l-muted)]"><p>A teacher is surrounded by papers and a clock: big ideas, too much prep.</p><p>Upload an existing deck and reuse its colours, fonts and layouts. Choose a topic and grade to plan connected lessons.</p><p>Create editable PowerPoints, worksheets and quizzes. Review the materials and make them your own before teaching.</p><p>Submitted work continues in the background. Return to Activity for your results.</p><p>Clastio: Plan. Teach. Shine. Start your next lesson.</p></div></details>
  </section>;
}
