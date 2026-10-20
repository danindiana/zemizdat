"""Load KiCad 7 library symbols (resolving `extends`) and report their pins."""
from __future__ import annotations
import copy
import os
from sexp import parse, find, find1, Q

KICAD_SYM = "/usr/share/kicad/symbols"
_cache: dict[str, list] = {}


def _lib(path: str):
    if path not in _cache:
        _cache[path] = parse(open(path, encoding="utf-8").read())[0]
    return _cache[path]


def _raw(lib_path: str, name: str):
    for s in find(_lib(lib_path), "symbol"):
        if s[1] == name:
            return s
    raise KeyError(f"{name} not in {lib_path}")


def load_symbol(lib_id: str, local_libs: dict[str, str] | None = None):
    """Return a flattened symbol S-expr named `lib_id` (e.g. 'Device:R'), ready for lib_symbols."""
    lib, name = lib_id.split(":", 1)
    path = (local_libs or {}).get(lib) or os.path.join(KICAD_SYM, lib + ".kicad_sym")
    s = copy.deepcopy(_raw(path, name))
    ext = find1(s, "extends")
    if ext:
        parent = copy.deepcopy(_raw(path, ext[1]))
        # child properties override parent's; graphics/pins come from the parent units
        props = {p[1]: p for p in find(s, "property")}
        merged = [parent[0], Q(name)]
        for item in parent[2:]:
            if isinstance(item, list) and item and item[0] == "property" and item[1] in props:
                merged.append(props.pop(item[1]))
            elif isinstance(item, list) and item and item[0] == "symbol":
                unit = copy.deepcopy(item)
                unit[1] = Q(unit[1].replace(ext[1], name, 1))
                merged.append(unit)
            else:
                merged.append(item)
        merged.extend(props.values())
        s = merged
    s[1] = Q(f"{lib}:{name}")
    return s


def pins(sym):
    """[(number, name, x, y, angle, length, etype)] over all units (unit numbers ignored)."""
    out = []

    def walk(e):
        for x in e:
            if isinstance(x, list) and x:
                if x[0] == "pin":
                    at = find1(x, "at")
                    ln = find1(x, "length")
                    nm = find1(x, "name")
                    nu = find1(x, "number")
                    out.append((str(nu[1]), str(nm[1]), float(at[1]), float(at[2]),
                                float(at[3]) if len(at) > 3 else 0.0, float(ln[1]), x[1]))
                elif x[0] == "symbol":
                    walk(x)

    walk(sym)
    return out


if __name__ == "__main__":
    import sys
    for lid in sys.argv[1:]:
        s = load_symbol(lid)
        print(lid)
        for p in sorted(pins(s), key=lambda p: (len(p[0]), p[0])):
            print("   ", p)
