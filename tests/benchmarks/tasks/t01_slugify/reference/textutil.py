import re
import unicodedata


def slugify(text: str, max_length: int | None = None) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if max_length is not None and max_length < 1:
        raise ValueError("max_length must be at least 1")
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
    if max_length is None or len(slug) <= max_length:
        return slug
    if slug[max_length] == "-":
        return slug[:max_length]
    head = slug[:max_length]
    return head.rsplit("-", 1)[0] if "-" in head else head
