"""A small arithmetic expression evaluator (recursive descent, no eval)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

Number = int | float

TOKEN = re.compile(
    r"\s*(?:(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|(?P<name>[A-Za-z_]\w*)|(?P<op>\*\*|//|[-+*/%(),]))"
)


class CalcError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} at position {position}")
        self.message = message
        self.position = position


@dataclass
class Token:
    kind: str  # num, name, op, end
    text: str
    position: int


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while True:
        rest = text[index:]
        if not rest.strip():
            tokens.append(Token("end", "", len(text)))
            return tokens
        match = TOKEN.match(text, index)
        if match is None:
            bad = index + (len(rest) - len(rest.lstrip()))
            raise CalcError(f"unexpected character {text[bad]!r}", bad)
        kind = match.lastgroup or "op"
        start = match.start(kind)
        tokens.append(Token(kind, match.group(kind), start))
        index = match.end()


class Parser:
    def __init__(self, text: str, variables: dict[str, float]) -> None:
        self.text = text
        self.tokens = tokenize(text)
        self.index = 0
        self.variables = variables

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def parse(self) -> Number:
        if self.current.kind == "end":
            raise CalcError("empty expression", len(self.text))
        value = self.additive()
        if self.current.kind != "end":
            token = self.current
            if token.text == ")":
                raise CalcError("unmatched )", token.position)
            raise CalcError(f"unexpected {token.text!r}", token.position)
        return value

    def additive(self) -> Number:
        value = self.multiplicative()
        while self.current.text in ("+", "-") and self.current.kind == "op":
            operator = self.advance()
            right = self.multiplicative()
            value = value + right if operator.text == "+" else value - right
        return value

    def multiplicative(self) -> Number:
        value = self.unary()
        while self.current.kind == "op" and self.current.text in ("*", "/", "//", "%"):
            operator = self.advance()
            right = self.unary()
            value = self.apply(operator, value, right)
        return value

    def apply(self, operator: Token, left: Number, right: Number) -> Number:
        try:
            if operator.text == "*":
                return left * right
            if operator.text == "/":
                return left / right
            if operator.text == "//":
                return left // right
            return left % right
        except ZeroDivisionError:
            raise CalcError("division by zero", operator.position) from None
        except OverflowError:
            raise CalcError("number too large", operator.position) from None

    def unary(self) -> Number:
        if self.current.kind == "op" and self.current.text in ("+", "-"):
            sign = self.advance()
            value = self.unary()
            return -value if sign.text == "-" else +value
        return self.power()

    def power(self) -> Number:
        base = self.atom()
        if self.current.kind == "op" and self.current.text == "**":
            operator = self.advance()
            exponent = self.unary()  # right associative, and the exponent may be signed
            try:
                result: Any = base**exponent
            except ZeroDivisionError:
                raise CalcError("division by zero", operator.position) from None
            except OverflowError:
                raise CalcError("number too large", operator.position) from None
            if isinstance(result, complex):
                raise CalcError("result is not a real number", operator.position)
            return result  # type: ignore[no-any-return]
        return base

    def atom(self) -> Number:
        token = self.current
        if token.kind == "num":
            self.advance()
            text = token.text
            return float(text) if any(c in text for c in ".eE") else int(text)
        if token.kind == "name":
            self.advance()
            if self.current.kind == "op" and self.current.text == "(":
                return self.call(token)
            if token.text not in self.variables:
                raise CalcError(f"unknown variable {token.text!r}", token.position)
            return self.variables[token.text]
        if token.kind == "op" and token.text == "(":
            self.advance()
            value = self.additive()
            if self.current.kind == "end":
                raise CalcError("missing )", len(self.text))
            if self.current.text != ")":
                raise CalcError(f"unexpected {self.current.text!r}", self.current.position)
            self.advance()
            return value
        if token.kind == "end":
            raise CalcError("unexpected end of expression", len(self.text))
        raise CalcError(f"unexpected {token.text!r}", token.position)

    def call(self, name: Token) -> Number:
        self.advance()  # the (
        arguments: list[Number] = []
        if self.current.kind == "op" and self.current.text == ")":
            self.advance()
        else:
            while True:
                arguments.append(self.additive())
                if self.current.kind == "op" and self.current.text == ",":
                    self.advance()
                    continue
                if self.current.kind == "end":
                    raise CalcError("missing )", len(self.text))
                if self.current.text != ")":
                    raise CalcError(f"unexpected {self.current.text!r}", self.current.position)
                self.advance()
                break
        return self.invoke(name, arguments)

    def invoke(self, name: Token, args: list[Number]) -> Number:
        function = name.text
        count = len(args)
        if function in ("min", "max"):
            if count < 1:
                raise CalcError(f"{function} needs at least one argument", name.position)
            return min(args) if function == "min" else max(args)
        if function in ("abs", "sqrt"):
            if count != 1:
                raise CalcError(f"{function} takes exactly one argument", name.position)
            if function == "abs":
                return abs(args[0])
            if args[0] < 0:
                raise CalcError("sqrt of a negative number", name.position)
            return math.sqrt(args[0])
        if function == "round":
            if count not in (1, 2):
                raise CalcError("round takes one or two arguments", name.position)
            if count == 2 and not isinstance(args[1], int):
                raise CalcError("round digits must be an integer", name.position)
            try:
                return round(args[0]) if count == 1 else round(args[0], int(args[1]))
            except OverflowError:
                raise CalcError("number too large", name.position) from None
        raise CalcError(f"unknown function {function!r}", name.position)


def evaluate(text: str, variables: dict[str, float] | None = None) -> Number:
    return Parser(text, variables or {}).parse()
