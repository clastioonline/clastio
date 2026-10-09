"""Content-first classroom lessons, rendered as bounded slide batches."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.generation import prompts
from app.generation.quality import ContentQualityError
from app.generation.specs import LessonDeck, LessonPlan, SlideSpec


class TeachingBlock(BaseModel):
    number: int = Field(ge=1)
    title: str
    purpose: str
    definition: str = ''
    explanation: str = ''
    worked_example: str = ''
    student_question: str = ''
    expected_answer: str = ''
    misconception: str = ''
    visual_brief: str = ''
    source_references: list[str] = Field(default_factory=list)


class LessonMaterial(BaseModel):
    lesson_plan: LessonPlan
    blocks: list[TeachingBlock] = Field(min_length=4, max_length=30)


class SlideBatch(BaseModel):
    slides: list[SlideSpec] = Field(min_length=1, max_length=3)


def slide_bounds(req):
    target = int(req['slides_per_lecture'])
    return (max(4, target - 3), min(30, target + 3)) if req.get('flexible_slides') else (target, target)


async def generate(ai, *, req, context_text, course, lecture_number, budgets, carry_over=None,
                   homework=True, owner_id=None, job_id=None, reference_images=None):
    from app.generation import pipeline

    lecture = course.lectures[lecture_number - 1]
    low, high = slide_bounds(req)
    prompt = prompts.deck_prompt(req=req, context_text=context_text, course=course.model_dump(),
        lecture=lecture.model_dump(), previous=[item.model_dump() for item in course.lectures[:lecture_number - 1]],
        budgets=budgets, carry_over=carry_over, homework=homework)
    prompt += (f'\nCONTENT-FIRST WORKFLOW: create {low}–{high} numbered teaching blocks, '
               f'prefer {req["slides_per_lecture"]}. Include one opening cover block, prerequisites, '
               'definitions, reasoning, fully solved examples, guided practice, independent questions, '
               'misconceptions, a summary, exit check and homework when requested. Combine related '
               'stages where needed; never omit a required lecture objective just to fit a count. '
               'Keep each block below 180 words across its content fields, with complete rather than clipped examples. '
               'Students are new to this topic. Separate student-facing explanations from teacher '
               'guidance. Preserve factual source references. Mark illustrative UAE examples explicitly.')
    # Remove the legacy exact-count sentence when flexibility is explicitly enabled.
    if req.get('flexible_slides'):
        prompt = prompt.replace(f'Exactly {req["slides_per_lecture"]} slides.', f'Between {low} and {high} slides.')
    material = await ai.structured(task='lesson_teaching', tier='planning', system=prompts.DECK_SYSTEM+"\nFor this stage return LessonMaterial: lesson_plan and numbered teaching blocks, not slide JSON.",
        prompt=prompt, schema=LessonMaterial, max_tokens=14000, owner_id=owner_id, job_id=job_id,
        images=reference_images, cache=True, prompt_version=prompts.PROMPT_VERSION+'-content-v2')
    count = len(material.blocks)
    if not low <= count <= high or [block.number for block in material.blocks] != list(range(1,count+1)):
        raise ContentQualityError('The lesson content did not meet its agreed slide range or sequence. No deck was published.')
    content_errors = []
    if any(not block.title.strip() or not block.purpose.strip() for block in material.blocks):
        content_errors.append('Every teaching block needs a title and purpose.')
    if any(not any(value.strip() for value in [block.explanation, block.worked_example, block.student_question])
           for block in material.blocks[1:]):
        content_errors.append('Non-cover blocks need a concrete explanation, example or student task.')
    if not any(block.definition.strip() for block in material.blocks):
        content_errors.append('Include a student-friendly definition.')
    if not any(block.worked_example.strip() for block in material.blocks):
        content_errors.append('Include a fully worked example.')
    if not any(block.student_question.strip() and block.expected_answer.strip() for block in material.blocks):
        content_errors.append('Include a student check with its expected answer.')
    if any(block.student_question.strip() and not block.expected_answer.strip() for block in material.blocks):
        content_errors.append('Each student question needs an expected answer for the teacher.')
    if content_errors:
        raise ContentQualityError('Incomplete teaching content: '+' '.join(content_errors))
    actual_req = {**req, 'slides_per_lecture': count}
    outline = await ai.structured(task='lesson_outline', tier='content',
        system='Choose varied classroom layouts for the approved teaching content. Preserve all objectives, '
               'definitions, examples and student checks. Use exactly one first cover; the remaining layouts '
               'must suit the teaching blocks. Assign positive minutes totalling the lesson duration. '
               'Do not add generic filler or change sourced facts. Return the requested schema.',
        prompt=json.dumps({'request': actual_req, 'content': material.model_dump(), 'budgets': budgets}),
        schema=pipeline.DeckOutline, max_tokens=6500, owner_id=owner_id, job_id=job_id, cache=True)
    issues = pipeline.outline_issues(outline, actual_req)
    if issues:
        outline = await ai.structured(task='lesson_outline', tier='content',
            system='Repair the supplied layout plan using the approved teaching content. Return the requested schema.',
            prompt=json.dumps({'request': actual_req, 'content': material.model_dump(),
                               'previous_outline': outline.model_dump(), 'issues': issues}),
            schema=pipeline.DeckOutline, max_tokens=6500, owner_id=owner_id, job_id=job_id, cache=False)
        issues = pipeline.outline_issues(outline, actual_req)
    if issues:
        raise ContentQualityError('The content-first slide layout plan is invalid: '+' '.join(issues))
    pipeline.fit_outline_duration(outline, float(req['lecture_minutes']))
    slides = []
    for start in range(0, count, 3):
        planned = outline.slides[start:start+3]
        expected = [item.number for item in planned]
        batch_prompt = json.dumps({'grade': req['grade'], 'subject': req['subject'], 'language': req.get('language','en'),
            'curriculum': req['curriculum'], 'lesson_title': lecture.title, 'objectives': lecture.objectives,
            'approved_content': [item.model_dump() for item in material.blocks[start:start+3]],
            'layout_plan': [item.model_dump() for item in planned], 'budgets': budgets,
            'image_mode': req.get('image_mode','auto'), 'outcomes': req.get('outcomes', []),
            'previous_slides': [{'number': s.number,'title':s.title} for s in slides],
            'teacher_instructions':req.get('instructions')})
        for attempt in range(2):
            batch = await ai.structured(task='lesson_deck_batch', tier='content', system=prompts.DECK_SYSTEM+"\nFor this stage return SlideBatch containing only the requested slides.",
                prompt=batch_prompt+'\nReturn only these slide numbers: '+str(expected)+
                       '\nUse the planned layouts, minutes and full approved teaching content; cover only at slide 1. '
                       'Show worked-example solutions. Put independent-task expected answers in speaker notes.',
                schema=SlideBatch, max_tokens=6500, owner_id=owner_id, job_id=job_id,
                images=reference_images, cache=attempt==0, prompt_version=prompts.PROMPT_VERSION+'-batch-v2')
            if ([s.number for s in batch.slides] == expected and
                    [s.layout for s in batch.slides] == [p.layout for p in planned]):
                break
            batch_prompt += '\nRepair the previous sequence/layout mismatch; preserve the approved teaching content.'
        else:
            raise ContentQualityError(f'Slide batch {expected} failed its sequence/layout check. No deck was published.')
        for slide, planned_slide, block in zip(batch.slides, planned, material.blocks[start:start+3], strict=True):
            slide.timing_minutes = planned_slide.minutes
            # Attach only approved references for this block; do not stamp generic book pages on every slide.
            catalog = req.get('source_catalog', {})
            slide.sources = [dict(catalog[reference]) for reference in block.source_references if reference in catalog]
        slides.extend(batch.slides)
    deck = LessonDeck(lesson_plan=material.lesson_plan, slides=slides)
    issues = pipeline.deck_structure_issues(deck, actual_req, outline=outline)
    if issues:
        raise ContentQualityError('The lesson did not cover its content/layout requirements: '+' '.join(issues))
    return pipeline.normalize_deck(deck, req=actual_req, lecture_number=lecture_number,
                                   total=len(course.lectures), lecture_title=lecture.title)
