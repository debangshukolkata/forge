from __future__ import annotations

import codecs

import pytest

from forge.workspace.text_format import FileFormat, decode_text, detect_format, encode_text

SAMPLES = {
    "lf": b"a = 1\nb = 2\n",
    "crlf": b"a = 1\r\nb = 2\r\n",
    "cr": b"a = 1\rb = 2\r",
    "mixed": b"a = 1\r\nb = 2\nc = 3\r\n",
    "bom": codecs.BOM_UTF8 + "naïve = 1\r\n".encode(),
    "utf16": codecs.BOM_UTF16_LE + "x = 'é'\r\n".encode("utf-16-le"),
    "cp1252": b"caf\xe9\n",
    "latin1": b"\x81\x8d odd bytes\n",
    "no_newline": b"single line",
}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_decode_then_encode_is_byte_exact(name: str) -> None:
    data = SAMPLES[name]
    file_format = detect_format(data)

    assert encode_text(decode_text(data, file_format), file_format) == data


def test_detection() -> None:
    assert detect_format(SAMPLES["crlf"]).newline == "crlf"
    assert detect_format(SAMPLES["mixed"]).newline == "mixed"
    assert detect_format(SAMPLES["bom"]) == FileFormat(encoding="utf-8", bom=True, newline="crlf")
    assert detect_format(SAMPLES["cp1252"]).encoding == "cp1252"
    assert detect_format(SAMPLES["latin1"]).encoding == "latin-1"
    assert detect_format(b"\x89PNG\r\n\x1a\n\x00\x00").binary


def test_crlf_file_edited_with_lf_text_stays_crlf() -> None:
    file_format = detect_format(SAMPLES["crlf"])

    text = decode_text(SAMPLES["crlf"], file_format) + "c = 3\n"

    assert encode_text(text, file_format) == b"a = 1\r\nb = 2\r\nc = 3\r\n"


def test_mixed_endings_are_not_normalised() -> None:
    file_format = detect_format(SAMPLES["mixed"])

    assert "\r\n" in decode_text(SAMPLES["mixed"], file_format)
