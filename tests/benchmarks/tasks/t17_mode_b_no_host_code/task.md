There is no existing code: create `anonymise.py` from scratch (standard library only). It removes personal data from application log text before it is shared, with strict, predictable rules.

**Functions**
- `anonymise_line(line: str, salt: str = "") -> str` and `anonymise_text(text: str, salt: str = "") -> str` (same rules; the text version works on many lines and keeps every line ending, `\n` and `\r\n`, exactly as it was; nothing may ever cross a line break).
- `anonymise_with_report(text: str, salt: str = "") -> tuple[str, dict[str, int]]` returns the anonymised text and how many replacements were made, as a dict with exactly the keys `"ip"`, `"email"`, `"user"`, `"secret"` (0 when none).

**Pseudonyms.** A pseudonym is `<KIND:hhhhhhhh>` where `KIND` is `IP`, `EMAIL` or `USER` and `hhhhhhhh` is the first 8 lowercase hex characters of the SHA-256 of the UTF-8 text `salt|kind|value` (`kind` in lower case: `ip`, `email`, `user`). The same value with the same salt always gives the same pseudonym; another salt gives another one. Everything else in the line stays exactly as it was (timestamps, numbers, other words, spacing).

**Rules** (the passes run in this order, and text produced by an earlier pass is never changed by a later one)
1. **Secrets.** A key/value pair whose key *ends with* one of `token`, `password`, `passwd`, `secret`, `apikey`, `api_key`, `api-key` (any case; the key is made of letters, digits, `_` and `-`, so `access_token`, `Client-Secret` and `DB_PASSWORD` count, but `tokenizer` and `tokens` do not). The key may be followed by a closing double quote (JSON style), then optional spaces/tabs, `=` or `:`, optional spaces/tabs, then the value: a double-quoted string, a single-quoted string, or a run of characters up to the next whitespace, `&`, `,`, `;` or quote. The value (inside the quotes, when quoted) becomes `<REDACTED>`; the key, the separator and the quotes stay. Also `Bearer <credential>` (word `Bearer` in any case, spaces/tabs, then a credential of 8 or more characters from `A-Za-z0-9-._~+/=`) becomes `Bearer <REDACTED>`. Each redaction counts as `secret`.
2. **Users.** Keys `user`, `username` or `user_id` (any case, the whole key, same quoting/separator/value shapes as above) get the value replaced by `<USER:...>` (hash of the value exactly as written, inside the quotes when quoted).
3. **Emails.** `local@domain.tld`: local part from `A-Za-z0-9._%+-`, domain labels from `A-Za-z0-9-` separated by dots, last label letters only and at least 2 long. Replaced by `<EMAIL:...>`, hashing the lower-cased address. A full stop that ends a sentence after an address is not part of it.
4. **IPv4.** Four decimal numbers 0 to 255 without leading zeros (except `0` itself) separated by dots, not touching another word character or dot-digit on either side (so `1.2.3.4.5`, `v1.2.3.4`, `256.1.1.1` and `01.2.3.4` are left alone, but `10.0.0.1:8080` and `from 10.0.0.1.` are replaced). Replaced by `<IP:...>`.

**Details**
- An empty value (`password=`, `user=""`) is left alone and not counted.
- Already-anonymised input is left alone: a value that is exactly `<REDACTED>` or a pseudonym of the right shape is not changed or counted again, so running the function twice gives the same result as running it once.
- A value inside a secret or user pair is handled by that pair's rule only (an email in `user=bob@example.com` counts as `user`, not `email`).

Write tests for it too (`test_anonymise.py`).
