"""Minimal S-expression reader/writer for KiCad files (no dependencies).

Atoms are kept as Python str; quoted strings become `Q` instances so they are written back
quoted. Lists are Python lists. Good enough for KiCad 7 symbol libraries and schematics.
"""
from __future__ import annotations


class Q(str):
    """A string that was quoted in the source (and must be quoted when written)."""


def parse(text: str):
    i, n = 0, len(text)
    stack: list[list] = [[]]
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            stack.append([])
            i += 1
        elif c == ")":
            done = stack.pop()
            stack[-1].append(done)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append({"n": "\n", "t": "\t"}.get(text[j + 1], text[j + 1]))
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            stack[-1].append(Q("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    assert len(stack) == 1
    return stack[0]


def _atom(a) -> str:
    if isinstance(a, Q):
        return '"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(a, float):
        s = f"{a:.4f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(a)


def dumps(e, indent: int = 0) -> str:
    if not isinstance(e, list):
        return _atom(e)
    # short lists on one line
    flat = "(" + " ".join(dumps(x) for x in e) + ")"
    if len(flat) < 100 and not any(isinstance(x, list) and len(x) > 0 and isinstance(x[0], str)
                                   and x[0] in ("symbol", "pin", "property", "polyline") for x in e):
        return flat
    pad = "  " * (indent + 1)
    head = [x for x in e if not isinstance(x, list)]
    out = "(" + " ".join(_atom(h) for h in head)
    for x in e:
        if isinstance(x, list):
            out += "\n" + pad + dumps(x, indent + 1)
    return out + ")"


def find(e, key):
    """All direct children lists whose head is `key`."""
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def find1(e, key):
    r = find(e, key)
    return r[0] if r else None
