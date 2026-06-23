import hashlib


def compose_embed_text(row: dict, max_expl: int = 1000) -> str:
    text = (row.get("text") or "").strip()
    parts = [text]
    modern = (row.get("modern_text") or "").strip()
    if modern and modern != text:
        parts.append(modern)
    expl = (row.get("explanation") or "").strip()
    if expl:
        parts.append(expl[:max_expl])
    return "\n".join(parts)


def content_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()
