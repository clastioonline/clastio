from types import SimpleNamespace

from app.services.presentation_files import presentation_properties


def test_teacher_name_and_page_numbers_are_optional_by_default():
    props = presentation_properties(SimpleNamespace(name='Sara'), {})
    assert props == {'author': 'Sara', 'page_numbers': 'false'}


def test_teacher_selects_visible_footer_independently_of_private_author_metadata():
    props = presentation_properties(SimpleNamespace(name='Sara'), {
        'teacher_footer_enabled': True, 'teacher_footer_text': 'Ms Sara · Physics',
        'include_author': False, 'page_numbers_enabled': True})
    assert props['author'] == ''
    assert props['teacher_footer_text'] == 'Ms Sara · Physics'
    assert props['page_numbers'] == 'true'


def test_enabled_teacher_footer_uses_profile_name_and_bounds_custom_text():
    user = SimpleNamespace(name='Sara')
    assert presentation_properties(user, {'teacher_footer_enabled': True})['teacher_footer_text'] == 'Sara'
    assert len(presentation_properties(user, {'teacher_footer_enabled': True,
        'teacher_footer_text': 'x' * 1000})['teacher_footer_text']) == 80
