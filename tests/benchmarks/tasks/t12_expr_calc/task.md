Create a module `calc.py` that evaluates arithmetic expressions given as text, without using `eval`, `exec`, `ast.literal_eval` or `compile`.

`evaluate(text: str, variables: dict[str, float] | None = None) -> int | float`

**Syntax**
- Numbers: integers (`42`), decimals (`3.14`, `.5`, `5.`) and exponent forms (`1e3`, `2.5E-2`). Integers stay `int`; anything with a decimal point or exponent is a `float`.
- Binary operators, lowest to highest precedence: `+ -`, then `* / // %`, then `**`. All are left associative except `**`, which is right associative (`2 ** 3 ** 2 == 512`).
- Unary `+` and `-`. A unary minus binds looser than `**` on its left but a `**` exponent may itself be signed: `-2 ** 2 == -4`, `2 ** -1 == 0.5`, `2 ** -2 ** 2 == 0.0625`, `- - 3 == 3`.
- Parentheses. Whitespace between tokens is ignored.
- Names: letters, digits and underscores, not starting with a digit. A name is either a variable from `variables` or a function call.
- Functions: `min(a, b, ...)` and `max(a, b, ...)` (at least one argument), `abs(x)`, `sqrt(x)`, `round(x)` and `round(x, digits)`. Calling any other name, or a variable name as a function, is an error.
- Operators follow Python semantics for results: `/` always gives a float (`6 / 3 == 2.0`), `//` and `%` floor (`-7 // 2 == -4`, `-7 % 3 == 2`), `int ** negative int` gives a float. `round` follows Python's `round` (banker's rounding; `round(x)` gives an `int`).
- There is no implicit multiplication (`2(3)` and `2 3` are errors).

**Errors**
Every problem raises `CalcError`, a subclass of `ValueError`, with attributes `message` (a short text) and `position` (the 0-based character index in `text` that the problem is at), and `str(error)` is `"<message> at position <position>"`. Positions:
- an unexpected character or token: its index; an empty or all-whitespace expression: `len(text)`;
- an unexpected end of the expression (for example `1 +`): `len(text)`; a missing closing parenthesis: `len(text)`; an unmatched `)`: its index;
- an unknown variable or function: the index of the name; a wrong number of arguments: the index of the function name;
- division by zero (`/`, `//`, `%`): the index of the operator; `sqrt` of a negative number: the index of the name `sqrt`.
Nothing else may escape as a different exception type (no `ZeroDivisionError`, `OverflowError` and the like): an overflow such as `10.0 ** 1000` is a `CalcError` at the position of the `**`.

Write tests for it too. Use only the standard library.
