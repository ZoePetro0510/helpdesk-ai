"""Load the knowledge base: Markdown files split into one chunk per `##` section."""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.embeddings import Embedder
from app.models import KbChunk


@dataclass
class Section:
    doc_id: str
    doc_title: str
    section: str
    content: str

    @property
    def source(self) -> str:
        return f"{self.doc_id}#{self.section}"


def split_markdown(doc_id: str, markdown: str) -> list[Section]:
    title = doc_id
    sections: list[Section] = []
    current: str | None = None
    lines: list[str] = []

    def flush():
        body = "\n".join(lines).strip()
        if current and body:
            sections.append(Section(doc_id, title, current, body))

    for line in markdown.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            current, lines = line[3:].strip(), []
        else:
            lines.append(line)
    flush()
    return sections


def load_sections(kb_dir: Path) -> list[Section]:
    sections: list[Section] = []
    for path in sorted(kb_dir.rglob("*.md")):
        doc_id = path.relative_to(kb_dir).with_suffix("").as_posix()
        sections.extend(split_markdown(doc_id, path.read_text(encoding="utf-8")))
    return sections


def rebuild_index(session: Session, kb_dir: Path, embedder: Embedder) -> int:
    """Replace all chunks with a fresh index of the KB folder. Returns the chunk count."""
    sections = load_sections(kb_dir)
    # Embed title + section + body so short sections still match their topic
    vectors = embedder.embed([f"{s.doc_title}. {s.section}. {s.content}" for s in sections])
    session.execute(delete(KbChunk))
    session.add_all(
        KbChunk(doc_id=s.doc_id, doc_title=s.doc_title, section=s.section, content=s.content, embedding=v)
        for s, v in zip(sections, vectors, strict=True)
    )
    session.commit()
    return len(sections)
