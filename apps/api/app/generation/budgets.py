"""Text budgets derived from the teacher's template geometry and writing style.

Budgets are given to the model as hard limits and enforced again after generation, so slides fit the
template at the teacher's font sizes instead of being shrunk to unreadable text.
"""

from __future__ import annotations

from typing import Any


def compute_budgets(spec: dict[str, Any]) -> dict[str, Any]:
    W = spec["slide_size"]["w"] / 12700  # points
    H = spec["slide_size"]["h"] / 12700
    body = spec["zones"]["body"]
    title = spec["zones"]["title"]
    body_pt = spec["typography"]["body_pt"]
    title_pt = spec["typography"]["title_pt"]
    bw, bh = body[2] * W, body[3] * H
    char_w = body_pt * 0.52
    chars_per_line = max(20, int(bw * 0.93 / char_w))
    line_h = body_pt * 1.35
    max_lines = max(4, int(bh / (line_h * 1.25)))
    style = spec.get("content_style") or {}
    teacher_words = style.get("avg_words_per_bullet") or 9
    max_words_bullet = int(min(max(8, chars_per_line * 2 / 6.2), 28))
    max_bullets = int(min(6, max(3, max_lines // 2)))
    title_chars = max(24, int(title[2] * W * 0.93 / (title_pt * 0.55)))
    return {
        "title_max_words": min(9, max(5, title_chars // 7)),
        "bullets_max": max_bullets,
        "bullet_max_words": max_words_bullet,
        "image_text_bullets_max": max(3, max_bullets - 1),
        "image_text_bullet_max_words": max(10, int(max_words_bullet * 0.75)),
        "column_bullets_max": 4,
        "column_bullet_max_words": min(14, max(7, chars_per_line // 6)),
        "steps_max": 5,
        "step_label_max_words": 4,
        "step_detail_max_words": 12,
        "quiz_question_max_words": 22,
        "quiz_option_max_words": 8,
        "table_rows_max": 5,
        "table_cols_max": 4,
        "table_cell_max_words": 8,
        "terms_max": 6,
        "term_meaning_max_words": 12,
        "speaker_notes_max_words": 240,
        "teacher_style": {"avg_words_per_bullet": teacher_words,
                          "bullets_per_slide": style.get("bullets_per_slide", [3, 5]),
                          "question_titles_ratio": style.get("question_titles_ratio", 0)},
    }
