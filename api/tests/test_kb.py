import json

from app.config import settings
from app.kb import load_sections, split_markdown

DOC = """# Payroll

## Pay date
Salaries are paid on the 9th.

## Payslips
Published by the 7th.
More text.

## Empty section
"""


def test_split_markdown_one_chunk_per_section():
    sections = split_markdown("hr/payroll", DOC)
    assert [s.section for s in sections] == ["Pay date", "Payslips"]  # empty section is dropped
    assert sections[0].doc_title == "Payroll"
    assert sections[1].content == "Published by the 7th.\nMore text."
    assert sections[0].source == "hr/payroll#Pay date"


def test_knowledge_base_loads():
    sections = load_sections(settings.kb_dir)
    assert len(sections) >= 40
    assert all(s.content for s in sections)


def test_every_eval_source_exists_in_the_kb():
    sources = {s.source for s in load_sections(settings.kb_dir)}
    items = [json.loads(line) for line in settings.eval_file.read_text().splitlines() if line.strip()]
    missing = [i["source"] for i in items if i["source"] and i["source"] not in sources]
    assert missing == []
