# Clastio doodle product film

30 seconds · English · animated vector doodles · original procedural music and transition effects · burned-in captions.

## Deliverables

- `apps/web/public/videos/clastio-doodle-web.mp4`: 1920 × 1080, 16:9, website / YouTube / presentations.
- `apps/web/public/videos/clastio-doodle-vertical.mp4`: 1080 × 1920, 9:16, Reels / Shorts / Stories.
- Matching JPG posters and WebVTT/SRT captions.

The vertical version uses a separate composition, not a cropped widescreen export. Both use H.264 video, AAC audio, 24 fps, web fast-start and a 30-second timeline. The video uses illustrative product drawings, not a recording of the actual interface. There is no spoken narration; the captions carry the story with the sound off.

## Storyboard

| Time | Scene | Message |
| --- | --- | --- |
| 0–4.5 s | Teacher surrounded by paper and a clock | Big ideas. Too much prep? |
| 4.5–9.5 s | Old deck becomes a reusable design | Your slides. Your signature. |
| 9.5–14.5 s | Topic turns into a connected sequence | One topic. Connected lessons. |
| 14.5–19.5 s | Editable slide and assessment | Create. Review. Make it yours. |
| 19.5–24.5 s | Activity completes while the teacher moves on | Less waiting. More teaching. |
| 24.5–30 s | Brand and closing invitation | Plan. Teach. Shine. |

## Edit / render

`film.html` is the editable motion-graphics source. Change wording, timing, colours or illustrations in that file. `soundtrack.py` composes the soundtrack without external recordings. No stock footage, external music samples or uploaded customer data are used. The user-supplied Clastio artwork is used directly from `apps/web/public/brand/clastio-original.png`; the source image is preserved unchanged. The render uses the locally installed Chalkboard font; install an appropriately licensed substitute when rendering on another OS. Font files are not distributed.

From `apps/web`:

```sh
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node e2e/render-product-video.mjs
```

Set `VIDEO_FORMAT=web` or `VIDEO_FORMAT=vertical` to render only one layout. Run `BASE_URL=http://localhost:3008 npm run e2e:video` against the preview to check playback and responsive sizing.

Requires Python 3, ffmpeg with libx264, and Playwright/Chrome. Update caption files if the script changes. The exports are local assets; no social post or production deployment is performed.

## Suggested social caption

Big ideas. Less prep. Meet Clastio: connected lesson plans, editable slides in your design, and classroom resources you can review and make your own. Submit a task, carry on with your day, and find your results in Activity.

Plan. Teach. Shine.

#Clastio #TeacherTools #LessonPlanning #EdTech

Add your live website URL before publishing.
