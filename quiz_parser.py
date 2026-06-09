import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

OPTION_LINE = re.compile(r"^([A-ZА-Я])\)\s*(.+)$", re.IGNORECASE)
ANSWER_LINE = re.compile(r"^ответ\s*:\s*(.+)$", re.IGNORECASE)
QUESTION_LINE = re.compile(r"^вопрос\s*:\s*(.+)$", re.IGNORECASE)

LATIN_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CYRILLIC_LETTERS = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"

QUIZ_FORMAT_HINT = (
    "Вопрос: Текст?\n"
    "A) Вариант 1\n"
    "B) Вариант 2\n"
    "Ответ: B"
)


def _answer_token_to_index(token, options_count):
    token = (token or "").strip().upper()
    if not token:
        raise ValueError("Не указан правильный ответ")

    if token.isdigit():
        index = int(token) - 1
        if 0 <= index < options_count:
            return index
        raise ValueError(f"Номер ответа должен быть от 1 до {options_count}")

    letter = token[0]
    if letter in LATIN_LETTERS:
        index = LATIN_LETTERS.index(letter)
    elif letter in CYRILLIC_LETTERS:
        index = CYRILLIC_LETTERS.index(letter)
    else:
        raise ValueError(f"Некорректный ответ: {token}")

    if index >= options_count:
        raise ValueError(f"Ответ {letter} не соответствует количеству вариантов")
    return index


def _normalize_lines(text):
    return [
        line.strip()
        for line in (text or "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def parse_quiz_text(text):
    """Парсит текст с вопросами и вариантами ответов (из .docx или .txt)."""
    lines = _normalize_lines(text)
    questions = []
    question_text = None
    options = []
    correct_index = None

    def append_question():
        nonlocal question_text, options, correct_index
        if question_text and options and correct_index is not None:
            questions.append({
                "question": question_text,
                "options": list(options),
                "correct_index": correct_index,
            })
        question_text = None
        options = []
        correct_index = None

    for line in lines:
        question_match = QUESTION_LINE.match(line)
        if question_match:
            append_question()
            question_text = question_match.group(1).strip()
            continue

        option_match = OPTION_LINE.match(line)
        if option_match:
            options.append(option_match.group(2).strip())
            continue

        answer_match = ANSWER_LINE.match(line)
        if answer_match and options:
            correct_index = _answer_token_to_index(
                answer_match.group(1), len(options)
            )
            append_question()

    if not questions:
        raise ValueError(
            "Файл не содержит корректных вопросов. Используйте формат:\n"
            f"{QUIZ_FORMAT_HINT}"
        )
    return questions


DOCX_TEXT_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
DOCX_PARAGRAPH_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"


def _read_docx_text(path):
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise ValueError("Не удалось прочитать файл .docx") from exc

    root = ET.fromstring(document_xml)
    paragraphs = []
    for paragraph in root.iter(DOCX_PARAGRAPH_TAG):
        parts = [
            node.text
            for node in paragraph.iter(DOCX_TEXT_TAG)
            if node.text
        ]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)
    if not paragraphs:
        raise ValueError("Файл .docx пуст или не содержит текста")
    return "\n".join(paragraphs)


def parse_quiz_file(path):
    file_path = Path(path)
    extension = file_path.suffix.lower()
    if extension == ".docx":
        text = _read_docx_text(file_path)
    elif extension == ".txt":
        with open(file_path, encoding="utf-8") as handle:
            text = handle.read()
    else:
        raise ValueError("Тестовый файл должен быть в формате .docx")

    return parse_quiz_text(text)


def quiz_to_json(questions):
    return json.dumps(questions, ensure_ascii=False)


def quiz_from_json(raw):
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Некорректные данные теста")
    return data


def quiz_public_view(questions):
    return [
        {"question": item["question"], "options": item["options"]}
        for item in questions
    ]
