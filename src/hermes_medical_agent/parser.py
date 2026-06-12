from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptionMetadata:
    document_type: str | None
    document_date: str | None
    comment: str | None


def parse_caption(caption: str | None) -> CaptionMetadata:
    if not caption:
        return CaptionMetadata(document_type=None, document_date=None, comment=None)

    fields: dict[str, str] = {}
    free_lines: list[str] = []
    for line in caption.splitlines():
        match = re.match(r"^\s*([\wа-яА-ЯёЁ_-]+)\s*:\s*(.+?)\s*$", line)
        if match:
            fields[match.group(1).lower()] = match.group(2)
        else:
            free_lines.append(line.strip())

    document_type = fields.get("type") or fields.get("тип")
    document_date = fields.get("date") or fields.get("дата")
    comment = fields.get("comment") or fields.get("комментарий") or "\n".join(
        line for line in free_lines if line
    ) or None
    return CaptionMetadata(document_type=document_type, document_date=document_date, comment=comment)
