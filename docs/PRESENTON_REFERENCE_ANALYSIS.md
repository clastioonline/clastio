# Presenton reference analysis — Step 1

Cloned with `git clone https://github.com/presenton/presenton.git /private/tmp/clastio-presenton-reference` outside the Clastio workspace. Inspected upstream commit `7376573fb30e4faf6225ff77d2cc74d06634b2e0` on 10 October 2026. Application code has not been changed by this analysis.

## Relevant FastAPI implementation

- `templates/presentation_layout.py`: `SlideLayoutModel` stores per-layout JSON schemas; `PresentationLayoutModel.get_slide_layout_index` resolves stable layout IDs and rejects missing IDs. `to_string(with_schema=True)` exposes layout constraints for content generation.
- `templates/v2/schema.py`, `templates/v2/content.py`: schema-driven element content, recursive Markdown removal (`infographic_markdown_to_plain_text`), and repeated-group hydration (`hydrate_repeated_top_level_groups`). These operate on Presenton's element structures, not python-pptx placeholder objects.
- `templates/pptx_font_utils.py`: OOXML font inspection including theme typefaces, master/layout placeholder styles and used font variants (`extract_used_font_variants_from_pptx`). Font replacement is a separate operation and should not be called for an original-font-preserving Clastio workflow.
- `templates/preview.py`, `templates/fonts_and_slides_preview.py`: uploaded PPTX/font inspection and preview orchestration; these have significant application/export dependencies.
- `utils/process_slides.py`: maps generated image/icon prompts to content paths and measures image slots using `image_target_sizes_from_template`. It uses temporary asset markers and deep copies to avoid modifying template/content inputs while calculating sizes.
- `services/image_generation_service.py`: target aspect-ratio and pixel-size helpers and image-provider integrations. Its placeholder fallback is not suitable for the user's requirement for relevant educational visuals.
- `services/export_task_service.py`: invokes a separate `presentation-export/runner.mjs` runtime. Current exports are not a self-contained Python template-injection service.

## Integration implications

The current checkout differs from the proposed assumption that its FastAPI backend contains a ready-made python-pptx placeholder-injection renderer. Copying its full backend services into Clastio would require Presenton's models, storage, UI/export runtime and other dependencies, and would not establish preservation of uploaded template fonts, colours or shapes.

Clastio already depends on python-pptx, Pillow and httpx in `apps/api/pyproject.toml`. Its current native rendering code is `apps/api/app/engine/render/renderer.py`; OOXML helpers and template analysis already exist. The next stage should adapt small applicable Presenton helpers with Apache-2.0 attribution, then implement explicit original-template placeholder injection and verify original OOXML formatting/geometry. Layout-dependent content schemas should constrain the model to existing slots; template styling should stay under deterministic code control.

Both the repository root and FastAPI LICENSE files are Apache-2.0. Any copied implementation must retain the applicable licence/copyright notices and identify modifications. No upstream code has yet been copied into Clastio.

The request's example model IDs must be checked for current OpenRouter availability and schema support before changing routing. Generation must retain existing price-card checks, spending reservations, source grounding and bounded retries. This analysis does not select a replacement model or claim a generated presentation has been tested.

Step 1 is complete. Backend/frontend integration, dependency installation, local generation checks and startup instructions are now implemented; see PRESENTON_INTEGRATION.md.
