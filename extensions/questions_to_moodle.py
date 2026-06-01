#!/usr/bin/env python3
"""
Convert monolingual questions.md files to Moodle XML format.

Each Week*/questions.md holds the recap quiz for that week as plain markdown.
The questions are written once (single language) and exported to a Moodle XML
file that can be imported via Moodle's
    Question bank > Import > Moodle XML format

Markdown format
---------------
    # Week 1 — Recap            <- becomes the Moodle question category

    **1. What does `len(x)` return?**
    Optional extra lines (bold text, `code`, fenced code blocks or
    ![images](picture.png)) may follow before the answer list.
    - *A) The number of elements      <- a leading * marks the correct answer
    - B) The last element
    - C) The memory size

    **2. ...**

Notes
-----
- A line starting with `# ` defines the category (use one per file).
- A question starts with `**N. question text**` on its own line.
- Answers are `- LETTER) text`; prefix the letter with `*` for the correct one.
- Inline `code`, **bold** continuation lines, fenced code blocks and images
  are supported. Images are embedded into the XML as base64 so the export is
  self-contained.

Usage
-----
    # Convert a single file
    python extensions/questions_to_moodle.py Week1/questions.md

    # Convert all weeks
    python extensions/questions_to_moodle.py --all

    # Specify output directory
    python extensions/questions_to_moodle.py --all --output-dir moodle_xml

Output files are written next to the input by default (e.g. Week1/questions.xml).
"""

import argparse
import base64
import re
import html
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent, tostring


def markdown_inline_to_html(text: str) -> str:
    """Convert inline markdown (backticks) to HTML."""
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _unescape_code(text: str) -> str:
    """Restore <code> tags that html.escape turned into entities."""
    return text.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")


def extra_lines_to_html(lines: list[str]) -> tuple[str, list[str]]:
    """Convert extra question content (code blocks, images, bold continuations) to HTML.

    Returns:
        (html_string, list_of_image_filenames) — image filenames are relative
        paths as written in the markdown (e.g. "distributions_ttest.png").
    """
    parts: list[str] = []
    images: list[str] = []
    in_code = False
    code_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                parts.append(
                    "<pre><code>"
                    + html.escape("\n".join(code_lines))
                    + "</code></pre>"
                )
                code_lines = []
            in_code = not in_code
            continue

        if in_code:
            code_lines.append(line)
            continue

        # Markdown image: ![alt](filename.png)
        img_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if img_match:
            alt = html.escape(img_match.group(1))
            filename = img_match.group(2)
            images.append(filename)
            parts.append(
                f'<p><img src="@@PLUGINFILE@@/{html.escape(filename)}"'
                f' alt="{alt}" /></p>'
            )
            continue

        bold_match = re.match(r"\*\*(.+?)(\*\*)?$", line)
        if bold_match:
            inner = _unescape_code(markdown_inline_to_html(html.escape(bold_match.group(1))))
            parts.append(f"<p><strong>{inner}</strong></p>")
        elif line.strip():
            escaped = _unescape_code(markdown_inline_to_html(html.escape(line)))
            parts.append(f"<p>{escaped}</p>")

    return "\n".join(parts), images


def parse_questions_md(filepath: Path) -> tuple[str, list[dict]]:
    """Parse a monolingual questions.md file.

    Returns:
        (category, questions) where each question is
        {"text": str, "extra_html": str, "images": list[str], "answers": list}
    """
    content = filepath.read_text(encoding="utf-8")
    lines = content.strip().splitlines()

    category = ""
    questions: list[dict] = []
    current_question: dict | None = None
    extra_lines: list[str] = []
    in_code_block = False

    def flush_extra_lines():
        """Flush accumulated extra lines into the current question (before answers)."""
        nonlocal extra_lines
        if not extra_lines:
            return
        if current_question is not None and not current_question["answers"]:
            extra_html, images = extra_lines_to_html(extra_lines)
            current_question["extra_html"] = extra_html
            current_question.setdefault("images", []).extend(images)
        extra_lines = []

    def finalize_question():
        """Finalize and append the current question."""
        nonlocal current_question, extra_lines
        if current_question is None:
            return
        flush_extra_lines()
        questions.append(current_question)
        current_question = None
        extra_lines = []

    for line in lines:
        line = line.rstrip()

        # Track fenced code blocks — keep their contents as extra lines.
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if current_question is not None and not current_question["answers"]:
                extra_lines.append(line)
            continue

        if in_code_block:
            if current_question is not None and not current_question["answers"]:
                extra_lines.append(line)
            continue

        # Category from top-level heading: # Week 1 — Recap
        if line.startswith("# "):
            category = line.lstrip("# ").strip()
            continue

        # Question start: **N. Question text**
        q_match = re.match(r"\*\*\d+\.\s+(.+)\*\*", line)
        if q_match:
            finalize_question()
            current_question = {
                "text": q_match.group(1),
                "extra_html": "",
                "images": [],
                "answers": [],
            }
            continue

        # Answer option: - *B) correct  or  - A) incorrect
        answer_match = re.match(r"^-\s+(\*?)([A-Z])\)\s+(.+)$", line)
        if answer_match and current_question is not None:
            is_correct = answer_match.group(1) == "*"
            answer_text = answer_match.group(3).strip()
            if not current_question["answers"]:
                flush_extra_lines()
            current_question["answers"].append(
                {"text": answer_text, "correct": is_correct}
            )
            continue

        # Continuation lines (extra question content before the answers)
        if current_question is not None and not current_question["answers"]:
            extra_lines.append(line)

    finalize_question()

    return category, questions


def _embed_image_files(parent_el: Element, image_filenames: list[str], source_dir: Path) -> None:
    """Add base64-encoded <file> elements for images into a questiontext element."""
    seen = set()
    for filename in image_filenames:
        if filename in seen:
            continue
        seen.add(filename)
        img_path = source_dir / filename
        if not img_path.exists():
            print(f"    Warning: image not found: {img_path}")
            continue
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        file_el = SubElement(parent_el, "file", name=filename, encoding="base64")
        file_el.text = b64


def build_moodle_xml(category: str, questions: list[dict], source_dir: Path) -> Element:
    """Build a Moodle XML ElementTree from parsed questions."""
    quiz = Element("quiz")

    # Category question
    cat_q = SubElement(quiz, "question", type="category")
    cat_text = SubElement(SubElement(cat_q, "category"), "text")
    cat_text.text = f"$course$/top/{category}"

    for i, q in enumerate(questions, 1):
        question_el = SubElement(quiz, "question", type="multichoice")

        # Name
        name_el = SubElement(question_el, "name")
        name_text = SubElement(name_el, "text")
        name_text.text = f"{category} — Q{i}"

        # Question text as HTML
        qtext_el = SubElement(question_el, "questiontext", format="html")
        qtext_text = SubElement(qtext_el, "text")

        header_html = f"<p>{_unescape_code(markdown_inline_to_html(html.escape(q['text'])))}</p>"
        extra = q.get("extra_html", "")
        qtext_text.text = header_html + ("\n" + extra if extra else "")

        # Embed referenced images as base64 files
        _embed_image_files(qtext_el, q.get("images", []), source_dir)

        for ans in q["answers"]:
            fraction = "100" if ans["correct"] else "0"
            answer_el = SubElement(
                question_el, "answer", fraction=fraction, format="html"
            )
            ans_text_el = SubElement(answer_el, "text")
            ans_html = _unescape_code(markdown_inline_to_html(html.escape(ans["text"])))
            ans_text_el.text = f"<p>{ans_html}</p>"
            fb = SubElement(answer_el, "feedback", format="html")
            SubElement(fb, "text")

        # General settings
        SubElement(question_el, "defaultgrade").text = "1.0000000"
        SubElement(question_el, "penalty").text = "0.3333333"
        SubElement(question_el, "hidden").text = "0"
        SubElement(question_el, "single").text = "true"
        SubElement(question_el, "shuffleanswers").text = "true"
        SubElement(question_el, "answernumbering").text = "abc"

        # General feedback (empty)
        gf = SubElement(question_el, "generalfeedback", format="html")
        SubElement(gf, "text")

        # Correct / partially correct / incorrect feedback (empty)
        for fb_tag in [
            "correctfeedback",
            "partiallycorrectfeedback",
            "incorrectfeedback",
        ]:
            fb = SubElement(question_el, fb_tag, format="html")
            SubElement(fb, "text")

    return quiz


def convert_file(input_path: Path, output_path: Path) -> None:
    """Convert a single questions.md to Moodle XML."""
    category, questions = parse_questions_md(input_path)
    if not questions:
        print(f"  Skipping {input_path} — no questions found")
        return

    quiz = build_moodle_xml(category, questions, source_dir=input_path.parent)
    tree = ElementTree(quiz)
    indent(tree, space="  ")

    # Serialize to string, then wrap HTML content in CDATA sections
    # so Moodle renders the HTML instead of displaying escaped tags.
    xml_str = tostring(quiz, encoding="unicode")

    def _to_cdata(match: re.Match) -> str:
        raw_html = html.unescape(match.group(1))
        return f"<text><![CDATA[{raw_html}]]></text>"

    # Only match <text> elements whose content starts with &lt; (escaped HTML)
    xml_str = re.sub(
        r"<text>(&lt;.+?)</text>", _to_cdata, xml_str, flags=re.DOTALL
    )

    with open(output_path, "w", encoding="UTF-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_str)
        f.write("\n")

    print(f"  {input_path} -> {output_path} ({len(questions)} questions)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert questions.md files to Moodle XML format."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Path(s) to questions.md files to convert",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Convert all Week*/questions.md files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for XML files (default: same directory as input)",
    )
    args = parser.parse_args()

    # Determine project root (script lives in extensions/)
    project_root = Path(__file__).resolve().parent.parent

    if args.all:
        files = sorted(project_root.glob("Week*/questions.md"))
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        parser.print_help()
        return

    if not files:
        print("No questions.md files found.")
        return

    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting {len(files)} file(s)...")
    for filepath in files:
        filepath = filepath.resolve()
        if not filepath.exists():
            print(f"  Skipping {filepath} — file not found")
            continue

        if output_dir:
            out = output_dir / f"{filepath.parent.name}_questions.xml"
        else:
            out = filepath.with_suffix(".xml")

        convert_file(filepath, out)

    print("Done.")


if __name__ == "__main__":
    main()
