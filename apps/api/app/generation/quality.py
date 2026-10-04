"""Deterministic classroom-content checks, without paid calls or claims of universal fact checking."""
from __future__ import annotations

import ast
import re
import uuid
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction

from app.generation.specs import AssessmentDoc, HomeworkDoc, QuizItem


class ContentQualityError(ValueError):
    """A bounded repair failed; don't keep retrying a paid job with unsafe content."""


def reference_count(sources: Iterable[dict]) -> int:
    """Count well-formed source identifiers/pages; skip malformed edited JSON."""
    references = set()
    for source in sources:
        file_id, page = source.get("file_id"), source.get("page")
        if not isinstance(file_id, str | uuid.UUID) or page is not None and (type(page) is not int or page < 1):
            continue
        try:
            parsed_id = uuid.UUID(str(file_id))
        except ValueError:
            continue
        references.add((parsed_id, page))
    return len(references)


def quiz_errors(quiz: QuizItem | None) -> list[str]:
    if quiz is None:
        return ["A quiz needs a question, four options and an answer."]
    errors = []
    options = [" ".join(option.split()).casefold() for option in quiz.options]
    if not quiz.question.strip():
        errors.append("The quiz question is empty.")
    if len(options) != 4 or any(not option for option in options) or len(set(options)) != 4:
        errors.append("A quiz must have four distinct, nonempty options.")
    if not 0 <= quiz.answer_index < len(options):
        errors.append("The answer index does not identify an existing option; do not guess the answer.")
    if not quiz.explanation.strip():
        errors.append("The correct answer needs a teacher explanation.")
    expected = arithmetic_answer(quiz.question)
    if expected is not None and 0 <= quiz.answer_index < len(options):
        numeric = [numeric_answer(option) for option in quiz.options]
        if all(number is not None for number in numeric):
            if numeric[quiz.answer_index] != expected or numeric.count(expected) != 1:
                errors.append("The answer key conflicts with the arithmetic question or has multiple correct options.")
    return errors


def numeric_answer(value: str) -> Decimal | None:
    value = value.strip().replace("−", "-")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value) or len(value) > 40:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def arithmetic_answer(question: str) -> Decimal | None:
    """Only an unambiguous numeric question; word problems/algebra/error-spotting stay for teacher review."""
    text = question.strip().rstrip("? ").replace("×", "*").replace("÷", "/").replace("−", "-")
    text = re.sub(r"^(?:what is|calculate|evaluate|find the value of)\s+", "", text, flags=re.I)
    text = re.sub(r"\s*=\s*$", "", text)
    if len(text) > 80 or not re.fullmatch(r"[\d.\s()+*/-]+", text) or not re.search(r"[+*/-]", text):
        return None
    try:
        tree = ast.parse(text, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 30:
            return None

        def number(node: ast.AST) -> Fraction:
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                segment = ast.get_source_segment(text, node) or ""
                parsed = numeric_answer(segment)
                if parsed is None:
                    raise ValueError
                return Fraction(parsed)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = number(node.operand)
                return -value if isinstance(node.op, ast.USub) else value
            if isinstance(node, ast.BinOp):
                left, right = number(node.left), number(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div) and right:
                    return left / right
            raise ValueError

        with localcontext() as context:
            context.prec = 200
            result = number(tree.body)
            # A rounded/repeating-decimal answer is ambiguous without a stated rounding rule.
            denominator = result.denominator
            for factor in (2, 5):
                while denominator % factor == 0:
                    denominator //= factor
            if denominator != 1:
                return None
            return Decimal(result.numerator) / Decimal(result.denominator)
    except (SyntaxError, ValueError, InvalidOperation, ArithmeticError, RecursionError):
        return None


def assessment_errors(doc: AssessmentDoc | HomeworkDoc, expected_count: int | None = None) -> list[str]:
    questions = doc.questions if isinstance(doc, HomeworkDoc) else [q for section in doc.sections for q in section.questions]
    errors = []
    if not questions or (expected_count is not None and len(questions) != expected_count):
        errors.append("The assessment must contain the requested number of questions.")
    seen = set()
    for index, question in enumerate(questions, 1):
        stem = " ".join(question.stem.split()).casefold()
        options = tuple(" ".join(option.split()).casefold() for option in question.options)
        signature = (question.qtype, stem, options)
        if not stem or signature in seen:
            errors.append(f"Question {index} is empty or repeated.")
        seen.add(signature)
        if not question.answer.strip() or not question.explanation.strip() or question.marks < 1:
            errors.append(f"Question {index} needs a nonempty answer, explanation and positive marks.")
        if question.qtype == "mcq":
            answer = " ".join(question.answer.split()).casefold()
            if answer not in options:
                errors.append(f"Question {index}'s correct answer must match a supplied option.")
            else:
                errors.extend(f"Question {index}: {message}" for message in quiz_errors(QuizItem(
                    question=question.stem, options=question.options, answer_index=options.index(answer),
                    explanation=question.explanation)))
    return errors
