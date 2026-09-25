"""Offline (no-API-key) generators for demo mode and tests.

Content is structured and topic-aware but deliberately generic. It exists so every part of the
product - planning, rendering, QC, exports, planner, WhatsApp - works end to end without keys.
"""

from __future__ import annotations

import random
import re
from typing import Any

from pydantic import BaseModel

from app.ai.offline_provider import register_structured, register_text
from app.generation.specs import (
    AssessmentDoc,
    Bullet,
    Column,
    CoursePlan,
    Differentiation,
    Homework,
    HomeworkDoc,
    LecturePlan,
    LessonDeck,
    LessonPhase,
    LessonPlan,
    Misconception,
    Outcome,
    Question,
    QuestionSection,
    QuestionToAsk,
    QuizItem,
    SlideRewrite,
    SlideSpec,
    Step,
    TableData,
    Term,
    Visual,
)

ANGLES = [
    ("What is {t}?", ["meaning of {t}", "why {t} matters"]),
    ("The key parts of {t}", ["components of {t}", "vocabulary of {t}"]),
    ("How {t} works", ["process of {t}", "cause and effect in {t}"]),
    ("{T} in everyday life", ["real-world examples of {t}", "{t} in the UAE"]),
    ("Investigating {t}", ["fair testing with {t}", "measuring {t}"]),
    ("Solving problems with {t}", ["applying {t}", "common mistakes with {t}"]),
    ("{T}: making connections", ["links between {t} and other topics", "comparing ideas in {t}"]),
    ("Review: bringing {t} together", ["summary of {t}", "exam-style practice on {t}"]),
]


def _t(topic: str) -> tuple[str, str]:
    return topic.strip(), topic.strip()[:1].upper() + topic.strip()[1:]


def _angle(i: int, n: int) -> tuple[str, list[str]]:
    if i == n - 1 and n > 2:
        return ANGLES[-1]
    return ANGLES[i % (len(ANGLES) - 1)]


@register_structured("course_plan")
def course_plan(ctx: dict[str, Any], schema: type[BaseModel]) -> CoursePlan:
    t, T = _t(ctx.get("topic", "the topic"))
    n = int(ctx.get("num_lectures", 3))
    lectures = []
    for i in range(n):
        title_tpl, concepts = _angle(i, n)
        title = title_tpl.format(t=t, T=T)
        kc = [c.format(t=t) for c in concepts]
        lectures.append(LecturePlan(
            number=i + 1, title=title,
            objectives=[f"Explain the {kc[0]}", f"Use examples to describe the {kc[1]}"],
            success_criteria=[f"I can explain the {kc[0]} in my own words", f"I can give an example of the {kc[1]}"],
            key_concepts=kc, revisits=[c.format(t=t) for c in _angle(i - 1, n)[1]] if i else [],
            key_vocabulary=[f"{T} term {i * 3 + k + 1}" for k in range(3)],
            activity_idea=f"Pairs sort example cards about the {kc[0]}",
            assessment_idea="Three-question exit ticket", homework_idea=f"Find one example of {t} at home"))
    return CoursePlan(
        title=f"{T} — Grade {ctx.get('grade', '')} {ctx.get('subject', '')}".strip(),
        overview=f"A {n}-lesson sequence that builds understanding of {t} from first ideas to application.",
        big_idea=f"{T} helps us explain and predict what we see around us.",
        learning_outcomes=[Outcome(code=o.get("code") if isinstance(o, dict) else None,
                                   text=o.get("text") if isinstance(o, dict) else str(o))
                           for o in (ctx.get("outcomes") or [])] or
        [Outcome(text=f"Describe and explain the main ideas of {t}"), Outcome(text=f"Apply {t} to new situations")],
        prerequisites=[f"Basic vocabulary related to {t}"],
        diagnostic_questions=[f"What do you already know about {t}?", f"Where might you see {t} in daily life?"],
        lectures=lectures,
        revision_strategy="Each lesson opens with a short retrieval quiz on the previous lesson.",
        assessment_strategy="Exit tickets each lesson; an end-of-unit quiz in the final lesson.",
        cross_curricular_links=["Literacy: explaining ideas in full sentences"],
        local_context_links=[f"Examples of {t} in the UAE"] if ctx.get("country", "AE") == "AE" else [],
    )


def _deck_layouts(n: int, lecture_no: int, homework: bool) -> list[str]:
    middle = ["concept", "image_text", "process", "key_vocabulary", "comparison", "quiz", "activity", "discussion",
              "cycle", "timeline", "worked_example", "table", "two_column", "concept"]
    first = "objectives" if lecture_no == 1 else "quiz"
    end = ["summary"] + (["homework"] if homework else ["exit_ticket"])
    k = max(0, n - 1 - len(end))
    body = ([first] + middle)[:k]
    layouts = ["cover"] + body + end
    return layouts[:n] if n >= 2 else ["cover"]


@register_structured("lesson_deck")
def lesson_deck(ctx: dict[str, Any], schema: type[BaseModel]) -> LessonDeck:
    t, T = _t(ctx.get("topic", "the topic"))
    lec = ctx.get("lecture") or {}
    no = int(lec.get("number", 1))
    total = int(ctx.get("total_lectures", 1))
    n = int(ctx.get("slides_per_lecture", 10))
    minutes = int(ctx.get("lecture_minutes", 45))
    title = lec.get("title") or f"{T}"
    kc = lec.get("key_concepts") or [f"meaning of {t}", f"examples of {t}"]
    vocab = lec.get("key_vocabulary") or [f"{T} term 1", f"{T} term 2", f"{T} term 3"]
    layouts = _deck_layouts(n, no, bool(ctx.get("homework", True)))
    per = round(minutes / max(1, n - 1), 1)
    slides: list[SlideSpec] = []
    for i, lay in enumerate(layouts, start=1):
        s = SlideSpec(number=i, layout=lay, purpose=lay, title=title, timing_minutes=per,
                      speaker_notes=f"Introduce this part of the lesson on {t}. Check understanding with a quick "
                                    f"show of hands before moving on.")
        if lay == "cover":
            s.subtitle = f"Grade {ctx.get('grade', '')} {ctx.get('subject', '')} • Lesson {no} of {total}"
            s.timing_minutes = 1
        elif lay == "objectives":
            s.title = "Learning objectives"
            s.bullets = [Bullet(text=o) for o in (lec.get("success_criteria") or [f"I can explain {t}"])[:4]]
        elif lay == "concept":
            s.title = f"Key idea: {kc[0]}" if i < n / 2 else f"Going further with {t}"
            s.bullets = [Bullet(text=f"{T} describes something we can observe and explain"),
                         Bullet(text=f"The {kc[0]} links to what we learned before"),
                         Bullet(text="Scientists and experts use evidence to test ideas"),
                         Bullet(text="We will practise with examples", level=0)]
            s.question_to_ask = f"Where have you seen {t} before?"
        elif lay == "image_text":
            s.title = f"Seeing {t} in action"
            s.bullets = [Bullet(text="Look carefully at the picture"), Bullet(text="What do you notice first?"),
                         Bullet(text=f"How does it show {t}?")]
            s.visual = Visual(kind="image", description=f"A clear photo illustrating {t}", image_query=t,
                              alt_text=f"Photo illustrating {t}")
        elif lay == "process":
            s.title = f"How {t} happens"
            s.steps = [Step(label="Start", detail=f"The first stage of {t}"),
                       Step(label="Change", detail="Something is transformed or moves"),
                       Step(label="Result", detail="We can observe the outcome"),
                       Step(label="Check", detail="Use evidence to confirm it")]
        elif lay == "cycle":
            s.title = f"The {t} cycle"
            s.steps = [Step(label=lab, detail="") for lab in ("Observe", "Predict", "Test", "Reflect")]
        elif lay == "timeline":
            s.title = f"How our ideas about {t} developed"
            s.steps = [Step(label=lab, detail=det) for lab, det in (
                ("Early ideas", "People made first observations"), ("Experiments", "Careful tests gave evidence"),
                ("Modern view", "Today's explanation"), ("Today", "How we use it now"))]
        elif lay == "key_vocabulary":
            s.title = "Key vocabulary"
            s.terms = [Term(term=v, meaning=f"A word we use when talking about {t}") for v in vocab[:4]]
        elif lay == "comparison":
            s.title = f"Compare: two sides of {t}"
            s.columns = [Column(heading="Idea A", bullets=["What it is", "Where we see it", "Why it matters"]),
                         Column(heading="Idea B", bullets=["What it is", "Where we see it", "Why it matters"])]
        elif lay == "two_column":
            s.title = f"{T}: facts and examples"
            s.columns = [Column(heading="Facts", bullets=["Fact one", "Fact two", "Fact three"]),
                         Column(heading="Examples", bullets=["Example one", "Example two", "Example three"])]
        elif lay == "table":
            s.title = f"{T} at a glance"
            s.table = TableData(headers=["Feature", "Description"],
                                rows=[["What", f"The meaning of {t}"], ["Where", "Places we find it"],
                                      ["Why", "Why it is important"]])
        elif lay == "quiz":
            s.title = "Quick check" if i > 2 else "Retrieval starter"
            s.quiz = QuizItem(question=f"Which statement about {t} is correct?",
                              options=[f"{T} can be explained using evidence", f"{T} never changes",
                                       f"{T} only happens in labs", f"{T} has no real-world uses"],
                              answer_index=0, explanation="Ideas in this topic are supported by evidence.")
            s.teacher_instruction = "Use mini whiteboards; ask students to hold up A–D."
        elif lay == "activity":
            s.title = f"Activity: explore {t}"
            s.subtitle = "Pairs"
            s.timing_minutes = max(5, round(minutes * 0.2))
            s.steps = [Step(label="Read the example card with your partner", detail=""),
                       Step(label=f"Decide how it shows {t}", detail=""),
                       Step(label="Share your answer with another pair", detail="")]
        elif lay == "discussion":
            s.title = "Think–pair–share"
            s.question = f"Why is it useful to understand {t}?"
            s.bullets = [Bullet(text="Think about your daily life"), Bullet(text="Give one clear example")]
        elif lay == "worked_example":
            s.title = "Worked example"
            s.steps = [Step(label="Read the question", detail="Underline the key words"),
                       Step(label="Recall the idea", detail=f"Which part of {t} applies?"),
                       Step(label="Answer", detail="Explain using a full sentence")]
        elif lay == "summary":
            s.title = "Summary"
            s.bullets = [Bullet(text=f"We explored the {kc[0]}"),
                         Bullet(text=f"We practised with examples of {t}"),
                         Bullet(text="We checked our understanding")]
        elif lay == "exit_ticket":
            s.title = "Exit ticket"
            s.bullets = [Bullet(text=f"One thing I learned about {t}"), Bullet(text="One question I still have")]
        elif lay == "homework":
            s.title = "Homework"
            s.bullets = [Bullet(text=lec.get("homework_idea") or f"Find one example of {t} at home"),
                         Bullet(text="Write two sentences explaining it"), Bullet(text="Bring it to the next lesson")]
        slides.append(s)
    plan = LessonPlan(
        lecture_number=no, title=title, duration_minutes=minutes,
        objectives=lec.get("objectives") or [f"Explain {t}"],
        success_criteria=lec.get("success_criteria") or [f"I can explain {t}"],
        phases=[LessonPhase(name="starter", minutes=round(minutes * 0.15), description="Retrieval / hook",
                            teacher_actions="Pose the starter question", student_actions="Answer on whiteboards"),
                LessonPhase(name="main", minutes=round(minutes * 0.45), description=f"Teach the {kc[0]}",
                            teacher_actions="Explain with examples and check understanding",
                            student_actions="Listen, answer questions, take notes"),
                LessonPhase(name="activity", minutes=round(minutes * 0.25), description="Pair activity",
                            teacher_actions="Circulate and support", student_actions="Complete the task in pairs"),
                LessonPhase(name="plenary", minutes=minutes - round(minutes * 0.15) - round(minutes * 0.45) -
                            round(minutes * 0.25), description="Summary and exit ticket",
                            teacher_actions="Review key points", student_actions="Complete exit ticket")],
        questions_to_ask=[QuestionToAsk(question=f"What is {t}?", bloom_level="remember",
                                        expected_response=f"A clear definition of {t}"),
                          QuestionToAsk(question=f"Why does {t} matter?", bloom_level="understand",
                                        expected_response="A reason linked to an example")],
        misconceptions=[Misconception(misconception=f"{T} only happens in special places",
                                      correction="It happens all around us; give local examples")],
        differentiation=Differentiation(support="Sentence starters and a word bank", core="Complete the main task",
                                        extension="Explain a tricky example to the class",
                                        eal="Key vocabulary with pictures and translations",
                                        send="Chunked instructions and visual steps"),
        resources=["Slides", "Mini whiteboards", "Example cards"],
        homework=Homework(task=lec.get("homework_idea") or f"Find one example of {t}", estimated_minutes=20),
        exit_ticket=[f"Define {t} in one sentence", "Give one example"],
    )
    return LessonDeck(lesson_plan=plan, slides=slides)


@register_structured("slide_rewrite")
def slide_rewrite(ctx: dict[str, Any], schema: type[BaseModel]) -> SlideRewrite:
    slide = SlideSpec.model_validate(ctx["slide"])
    instr = (ctx.get("instruction") or "").lower()
    if any(k in instr for k in ("simpl", "easier", "shorten", "reduce", "fit")):
        slide.bullets = slide.bullets[:3]
        for b in slide.bullets:
            b.text = " ".join(b.text.split()[:8])
    if "example" in instr:
        slide.bullets.append(Bullet(text="Example: think of something you saw this week"))
    if "visual" in instr and slide.layout == "concept":
        slide.layout = "image_text"
        slide.visual = Visual(kind="image", description=slide.title, image_query=slide.title, alt_text=slide.title)
    if "activity" in instr:
        slide.layout = "activity"
        slide.steps = [Step(label="Discuss with a partner", detail=""), Step(label="Write your answer", detail="")]
    return SlideRewrite(slide=slide)


def _material_facts(ctx: dict[str, Any]) -> tuple[list[tuple[str, str]], list[str]]:
    terms: list[tuple[str, str]] = []
    facts: list[str] = []
    for s in ctx.get("slides", []):
        for term in s.get("terms", []):
            terms.append((term["term"], term["meaning"]))
        for b in s.get("bullets", []):
            if len(b["text"].split()) >= 4:
                facts.append(b["text"])
    return terms, facts


@register_structured("assessment")
def assessment(ctx: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
    t, T = _t(ctx.get("topic", "the topic"))
    n = int(ctx.get("num_questions", 10))
    rnd = random.Random(f"{t}-{n}-{ctx.get('kind')}")
    terms, facts = _material_facts(ctx)
    qs: list[Question] = []
    for i in range(n):
        kind = ["mcq", "true_false", "short_answer", "fill_blank", "application"][i % 5]
        if kind == "mcq":
            if terms:
                term, meaning = terms[i % len(terms)]
                wrong = [m for _, m in terms if m != meaning][:3]
                while len(wrong) < 3:
                    wrong.append(f"Not related to {t}")
                opts = [meaning] + wrong
                rnd.shuffle(opts)
                qs.append(Question(qtype="mcq", difficulty="easy", bloom="remember", stem=f"What does '{term}' mean?",
                                   options=opts, answer=meaning, explanation=f"'{term}' means: {meaning}."))
            else:
                opts = [f"{T} can be explained using evidence", f"{T} never changes", f"{T} only happens in labs",
                        f"{T} has no uses"]
                qs.append(Question(qtype="mcq", difficulty="easy", bloom="understand",
                                   stem=f"Which statement about {t} is correct?", options=opts, answer=opts[0],
                                   explanation="Ideas in this topic are supported by evidence."))
        elif kind == "true_false":
            fact = facts[i % len(facts)] if facts else f"{T} can be observed in everyday life"
            qs.append(Question(qtype="true_false", difficulty="easy", bloom="remember", stem=f"True or false: {fact}",
                               options=["True", "False"], answer="True", explanation="This was covered in class."))
        elif kind == "short_answer":
            qs.append(Question(qtype="short_answer", difficulty="medium", bloom="understand",
                               stem=f"Explain in two sentences why {t} is important.",
                               answer=f"A clear explanation of why {t} matters, with one example.",
                               explanation="Look for a reason plus an example.", marks=2))
        elif kind == "fill_blank":
            term = terms[i % len(terms)][0] if terms else T
            qs.append(Question(qtype="fill_blank", difficulty="medium", bloom="remember",
                               stem=f"Complete the sentence: ________ is a key word in this topic about {t}.",
                               answer=term, explanation="Key vocabulary from the lesson."))
        else:
            qs.append(Question(qtype="application", difficulty="hard", bloom="apply",
                               stem=f"Describe a situation at home or school where you could use what you learned "
                                    f"about {t}.", answer="Any reasonable, explained example.",
                               explanation="Reward clear links between the example and the idea.", marks=3))
    title_kind = {"worksheet": "Worksheet", "quiz": "Quiz", "assessment": "Test"}.get(ctx.get("kind"), "Worksheet")
    if schema is HomeworkDoc:
        return HomeworkDoc(title=f"Homework: {T}", instructions="Complete all tasks. Show your thinking.",
                           tasks=[f"Find one example of {t} at home", "Answer the questions below"],
                           estimated_minutes=20, questions=qs[: max(3, n // 2)],
                           extension_task=f"Research one surprising fact about {t}.",
                           support_hint="Use your class notes and the key vocabulary list.")
    sections = [QuestionSection(title="Section A: Recall", instructions="Answer all questions.",
                                questions=[q for q in qs if q.difficulty == "easy"]),
                QuestionSection(title="Section B: Understanding and application",
                                instructions="Write in full sentences.",
                                questions=[q for q in qs if q.difficulty != "easy"])]
    return AssessmentDoc(title=f"{title_kind}: {T}", instructions="Read each question carefully.",
                         sections=[s for s in sections if s.questions],
                         case_study=f"A class investigates {t} at school and records what they observe."
                         if ctx.get("include_case_study") else None,
                         rubric=["Accurate use of key vocabulary", "Clear explanations with examples"])


@register_text("assistant_chat")
def assistant_chat(ctx: dict[str, Any], req) -> str:
    return ctx.get("fallback_answer") or (
        "I'm in offline demo mode, so I can only run app actions (planning, creating lessons, worksheets and "
        "quizzes). Connect an AI provider key to get full conversational answers.")


_NUM = re.compile(r"(\d+)")
