"""A short sample deck used to preview a template in the teacher's style."""

from __future__ import annotations

from app.generation.specs import Bullet, Column, QuizItem, SlideSpec, Step

PREVIEW_SLIDES: list[SlideSpec] = [
    SlideSpec(number=1, layout="cover", purpose="cover", title="The Water Cycle",
              subtitle="Grade 7 Science • Lesson 1 of 4"),
    SlideSpec(number=2, layout="objectives", purpose="objectives", title="Learning objectives",
              bullets=[Bullet(text="Describe the stages of the water cycle"),
                       Bullet(text="Explain how the sun drives evaporation"),
                       Bullet(text="Link the water cycle to weather in the UAE")]),
    SlideSpec(number=3, layout="cycle", purpose="diagram", title="Water on the move",
              steps=[Step(label="Evaporation", detail=""), Step(label="Condensation", detail=""),
                     Step(label="Precipitation", detail=""), Step(label="Collection", detail="")]),
    SlideSpec(number=4, layout="comparison", purpose="compare", title="Evaporation vs condensation",
              columns=[Column(heading="Evaporation", bullets=["Liquid to gas", "Needs heat energy"]),
                       Column(heading="Condensation", bullets=["Gas to liquid", "Happens when air cools"])]),
    SlideSpec(number=5, layout="quiz", purpose="check", title="Quick check",
              quiz=QuizItem(question="Which stage turns water vapour into clouds?",
                            options=["Evaporation", "Condensation", "Collection", "Runoff"], answer_index=1,
                            explanation="Cooling vapour condenses into droplets.")),
    SlideSpec(number=6, layout="process", purpose="process", title="How rain forms",
              steps=[Step(label="Warm air rises", detail="Carrying water vapour"),
                     Step(label="Air cools", detail="Vapour condenses on dust"),
                     Step(label="Droplets grow", detail="They join together"),
                     Step(label="Rain falls", detail="When drops are heavy enough")]),
]
