# OpenRouter for PPT generation

Set `OPENROUTER_API_KEY` in the root `.env`, then restart the API and worker. The key stays on the server. This workspace is configured with `OPENROUTER_ONLY=true` and `AI_OFFLINE_MODE=false`; direct-provider keys are preserved but excluded from paid routing, including transcription.

| Task | Model |
| --- | --- |
| Curriculum planning | anthropic/claude-sonnet-4.6 |
| Slide content and structured JSON | openai/gpt-5.4-mini |
| Fast chat and routing | google/gemini-3.5-flash-lite |
| Content quality and reflection | openai/gpt-5.4-mini |
| Source documents and rendered-slide review | google/gemini-3.5-flash |
| Illustrations | google/gemini-3.1-flash-image |
| Factual web search | perplexity/sonar |
| Embeddings | openai/text-embedding-3-small |

Routing syntax is `openrouter:<vendor>/<model>`. Admin → AI costs & model routing → **Load OpenRouter PPT preset**, then **Save routing**, replaces any older database overrides. Environment routes apply when there is no admin override.

Paid calls remain disabled until you approve rate cards and enable live spending in the budget controls. Use `docs/openrouter-rate-cards.json` as a draft, verify prices against OpenRouter, and choose daily/monthly/job limits before saving. These are starting limits, not guarantees of provider billing. Image and search charges may include non-token fees; search usage and image usage retain the entire per-call reservation until reconciliation. Large courses may require a higher job limit than the default $2.

Strict JSON routes require supporting endpoints and still validate output against the application's schemas. Stable Claude system prompts use explicit caching; other models use provider-managed caching where eligible. Existing source grounding, native diagrams, template preservation, rendering, geometric repairs and rendered-slide review remain active. A completed PPT still needs teacher review for factual and teaching suitability.

Stock images are tried before generated illustrations. Configure rendering (Gotenberg or LibreOffice) for slide previews and visual review. This adapter does not implement OpenRouter video or voice transcription; OpenRouter-only mode returns an explicit error for those features rather than charging another provider.

Verified references: [structured output](https://openrouter.ai/docs/guides/features/structured-outputs), [image generation](https://openrouter.ai/docs/guides/overview/multimodal/image-generation), [model catalog and prices](https://openrouter.ai/api/v1/models).

## Cost-balanced preset

Slide writing uses GPT-5.4 Mini at medium reasoning effort. Strong Claude planning and Gemini visual review remain enabled. Routine chat uses Flash Lite at low effort. Paid searches are requested only for current facts; images reuse existing assets, then licensed stock, before paid generation. Schema checks and bounded repairs remain in place.

Compared with the earlier GPT-5.4 slide-writing route, Mini has 70% lower listed input and output token prices ($0.75/$4.50 versus $2.50/$15 per million). This is a per-token saving, not a guaranteed reduction in total course cost: output length, reasoning, repairs and images affect the bill. Validate teaching quality on representative courses before drawing performance conclusions.
