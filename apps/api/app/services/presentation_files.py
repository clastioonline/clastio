"""Teacher-controlled attribution shared by chapter and demo presentation exports."""


def presentation_properties(user, policy):
    policy = policy or {}
    props = {'author': user.name if policy.get('include_author', True) else '',
             'page_numbers': 'true' if policy.get('page_numbers_enabled', False) else 'false'}
    if policy.get('ai_disclosure'):
        props['comments'] = 'Prepared with AI assistance and reviewed by the teacher.'
    if policy.get('watermark_enabled'):
        props['watermark_text'] = str(policy.get('watermark_text') or user.name).strip()[:120]
        props['watermark_position'] = str(policy.get('watermark_position') or 'footer')
    if policy.get('teacher_footer_enabled', False):
        props['teacher_footer_text'] = str(policy.get('teacher_footer_text') or user.name).strip()[:80]
    return props
