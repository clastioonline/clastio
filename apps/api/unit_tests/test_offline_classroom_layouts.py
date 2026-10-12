"""Offline classroom journeys must satisfy the same structural checks as live decks."""
import pytest

from app.generation.offline import course_plan, lesson_deck
from app.generation.pipeline import deck_structure_issues
from app.generation.specs import CoursePlan, LessonDeck


@pytest.mark.parametrize('count', [8, 10, 20])
@pytest.mark.parametrize('lecture_number', [1, 2])
@pytest.mark.parametrize('homework', [False, True])
def test_offline_classroom_deck_satisfies_teaching_requirements(count, lecture_number, homework):
    request = {'topic': 'Energy transfer', 'grade': '8', 'subject': 'Science', 'num_lectures': 2,
               'slides_per_lecture': count, 'lecture_minutes': 45, 'daily_teaching': True, 'homework': homework}
    plan = course_plan(request, CoursePlan)
    deck = lesson_deck({**request, 'lecture': plan.lectures[lecture_number - 1].model_dump(),
                        'total_lectures': 2}, LessonDeck)
    assert deck_structure_issues(deck, request) == []
    assert len(deck.slides) == count
    assert all(slide.speaker_notes for slide in deck.slides)
    assert any(slide.quiz and slide.quiz.explanation for slide in deck.slides)
