from __future__ import annotations

import hashlib

import pytest

from anonymise import anonymise_line, anonymise_text, anonymise_with_report


def h(kind: str, value: str, salt: str = "") -> str:
    digest = hashlib.sha256(f"{salt}|{kind}|{value}".encode()).hexdigest()[:8]
    return f"<{kind.upper()}:{digest}>"


def test_plain_line_is_unchanged() -> None:
    line = "2026-03-01 12:00:01 INFO worker-3 processed 1500 items in 2.5s (version 1.2.3)"
    assert anonymise_line(line) == line


def test_ip_addresses() -> None:
    assert anonymise_line("from 10.0.0.1 to 192.168.1.255") == f"from {h('ip', '10.0.0.1')} to {h('ip', '192.168.1.255')}"
    assert anonymise_line("peer 10.0.0.1:8080 ok") == f"peer {h('ip', '10.0.0.1')}:8080 ok"
    assert anonymise_line("connect from 10.0.0.1.") == f"connect from {h('ip', '10.0.0.1')}."
    assert anonymise_line("ip=0.0.0.0") == f"ip={h('ip', '0.0.0.0')}"


@pytest.mark.parametrize(
    "text",
    ["1.2.3.4.5", "v1.2.3.4", "256.1.1.1", "01.2.3.4", "1.2.3", "a1.2.3.4b", "10.0.0.1.5", "1.2.3.4a", "0.1.2.3.4"],
)
def test_things_that_are_not_ipv4_stay(text: str) -> None:
    assert anonymise_line(f"id {text} end") == f"id {text} end"


def test_emails() -> None:
    assert anonymise_line("mail ana.p+x@Example.co.uk now") == f"mail {h('email', 'ana.p+x@example.co.uk')} now"
    assert anonymise_line("Contact ana@x.org.") == f"Contact {h('email', 'ana@x.org')}."
    assert anonymise_line("A@B.com and a@b.COM") == f"{h('email', 'a@b.com')} and {h('email', 'a@b.com')}"


@pytest.mark.parametrize("text", ["user@localhost", "@handle", "a@b", "x@y.1", "name at example.com"])
def test_non_emails_stay(text: str) -> None:
    assert anonymise_line(f"see {text} here") == f"see {text} here"


def test_same_value_same_pseudonym_other_salt_other_pseudonym() -> None:
    a = anonymise_line("a@b.org 1.2.3.4", salt="s1")
    assert a == anonymise_line("a@b.org 1.2.3.4", salt="s1")
    assert a == f"{h('email', 'a@b.org', 's1')} {h('ip', '1.2.3.4', 's1')}"
    assert a != anonymise_line("a@b.org 1.2.3.4", salt="s2")


def test_secret_pairs() -> None:
    assert anonymise_line("login password=hunter2 ok") == "login password=<REDACTED> ok"
    assert anonymise_line("PASSWORD: hunter2") == "PASSWORD: <REDACTED>"
    assert anonymise_line("access_token = abc.def-1 next") == "access_token = <REDACTED> next"
    assert anonymise_line("Client-Secret:xyz") == "Client-Secret:<REDACTED>"
    assert anonymise_line("DB_PASSWORD=p@ss&x=1") == "DB_PASSWORD=<REDACTED>&x=1"
    assert anonymise_line("api_key=k1,other=2") == "api_key=<REDACTED>,other=2"
    assert anonymise_line("apikey=k1;next") == "apikey=<REDACTED>;next"
    assert anonymise_line("x-api-key: k1") == "x-api-key: <REDACTED>"
    assert anonymise_line("passwd=a") == "passwd=<REDACTED>"


def test_quoted_secret_values() -> None:
    assert anonymise_line('password="hunter two" rest') == 'password="<REDACTED>" rest'
    assert anonymise_line("secret='a b' rest") == "secret='<REDACTED>' rest"
    assert anonymise_line('{"password": "pw1", "n": 3}') == '{"password": "<REDACTED>", "n": 3}'
    assert anonymise_line('{"token":"t"}') == '{"token":"<REDACTED>"}'


@pytest.mark.parametrize("text", ["tokenizer=bpe", "tokens=5", "token_count=9", "secretary=Ann", "mypasswordless=1", "token"])
def test_keys_that_do_not_end_with_a_secret_word_stay(text: str) -> None:
    assert anonymise_line(f"cfg {text} end") == f"cfg {text} end"


def test_empty_values_are_left_alone_and_not_counted() -> None:
    text, counts = anonymise_with_report('password=\ntoken=""\nuser="" ok')
    assert text == 'password=\ntoken=""\nuser="" ok'
    assert counts == {"ip": 0, "email": 0, "user": 0, "secret": 0}


def test_bearer() -> None:
    assert anonymise_line("Authorization: Bearer abc123XYZ.def-ghi") == "Authorization: Bearer <REDACTED>"
    assert anonymise_line("authorization: BEARER  abcdefgh12") == "authorization: BEARER  <REDACTED>"
    assert anonymise_line("the bearer of bad news") == "the bearer of bad news"
    assert anonymise_line("Bearer short") == "Bearer short"  # under 8 characters


def test_users() -> None:
    assert anonymise_line("login user=alice ok") == f"login user={h('user', 'alice')} ok"
    assert anonymise_line("USERNAME: Alice") == f"USERNAME: {h('user', 'Alice')}"
    assert anonymise_line("user_id=42,") == f"user_id={h('user', '42')},"
    assert anonymise_line('{"user": "bob"}') == f'{{"user": "{h("user", "bob")}"}}'
    assert anonymise_line("user='b c'") == f"user='{h('user', 'b c')}'"


@pytest.mark.parametrize("text", ["db_user=root", "users=3", "userland=1", "superuser=x", "user_name=x"])
def test_other_user_like_keys_stay(text: str) -> None:
    assert anonymise_line(f"cfg {text} end") == f"cfg {text} end"


def test_a_pair_rule_wins_over_email_and_ip() -> None:
    line = "user=bob@example.com password=1.2.3.4 note=carl@example.com"
    assert anonymise_line(line) == f"user={h('user', 'bob@example.com')} password=<REDACTED> note={h('email', 'carl@example.com')}"
    assert anonymise_with_report(line)[1] == {"ip": 0, "email": 1, "user": 1, "secret": 1}


def test_report_counts() -> None:
    text = "a@b.org c@d.org 1.1.1.1 user=x token=y Bearer abcdefghij\nlast 2.2.2.2"
    result, counts = anonymise_with_report(text)
    assert counts == {"ip": 2, "email": 2, "user": 1, "secret": 2}
    assert result == anonymise_text(text)


def test_line_endings_are_preserved() -> None:
    text = "a 1.2.3.4\r\nb x@y.org\nc password=abc\r\n\r\nend"
    out = anonymise_text(text)
    assert out == f"a {h('ip', '1.2.3.4')}\r\nb {h('email', 'x@y.org')}\nc password=<REDACTED>\r\n\r\nend"


def test_nothing_crosses_a_line_break() -> None:
    assert anonymise_text('msg="open\npassword=zz"') == 'msg="open\npassword=<REDACTED>"'
    assert anonymise_text("password=\nuser=carl") == f"password=\nuser={h('user', 'carl')}"
    assert anonymise_text("token:  \nabc") == "token:  \nabc"


def test_idempotent() -> None:
    text = "user=alice a@b.org 1.2.3.4 password=pw Bearer abcdefghij token='x y'"
    once = anonymise_text(text, "s")
    assert anonymise_text(once, "s") == once
    assert anonymise_with_report(once, "s")[1] == {"ip": 0, "email": 0, "user": 0, "secret": 0}


def test_repeated_keys_and_adjacent_pairs() -> None:
    line = "password=a password=b token=c"
    assert anonymise_line(line) == "password=<REDACTED> password=<REDACTED> token=<REDACTED>"


def test_unicode_and_spacing_untouched() -> None:
    line = "  café ☃   user=Zürich\t1.2.3.4  "
    assert anonymise_line(line) == f"  café ☃   user={h('user', 'Zürich')}\t{h('ip', '1.2.3.4')}  "


def test_empty_input() -> None:
    assert anonymise_text("") == ""
    assert anonymise_with_report("") == ("", {"ip": 0, "email": 0, "user": 0, "secret": 0})
