"""Parameter schemas for API methods. A schema is {name: spec}; a spec is a type name with an optional '?' (optional):
  "str" "int" "num" "bool" "obj" "list" "bytes" "any"      and   ("enum", [values])   ("list", spec)   ("opt", spec)
"id" is a 64-bit integer carried as a decimal string (Unity path ids do not fit a JavaScript number).
validate() returns the cleaned params or raises SchemaError listing every problem. Unknown parameters are refused."""
import re

ID = re.compile(r"-?\d{1,20}")


class SchemaError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def _check(name, spec, v):
    if isinstance(spec, tuple):
        if spec[0] == "enum":
            return None if v in spec[1] else "%s must be one of %s" % (name, ", ".join(map(str, spec[1])))
        if spec[0] == "list":
            if not isinstance(v, list):
                return "%s must be a list" % name
            for i, x in enumerate(v):
                p = _check("%s[%d]" % (name, i), spec[1], x)
                if p:
                    return p
            return None
        raise ValueError("bad spec for %s" % name)
    ok = {"str": lambda: isinstance(v, str),
          "int": lambda: isinstance(v, int) and not isinstance(v, bool),
          "num": lambda: isinstance(v, (int, float)) and not isinstance(v, bool),
          "bool": lambda: isinstance(v, bool),
          "obj": lambda: isinstance(v, dict),
          "list": lambda: isinstance(v, list),
          "bytes": lambda: isinstance(v, (bytes, bytearray)),
          "id": lambda: isinstance(v, str) and bool(ID.fullmatch(v)),
          "any": lambda: True}[spec]()
    return None if ok else "%s must be %s" % (name, {"id": "a path id as a decimal string", "obj": "an object", "num": "a number"}.get(spec, spec))


def _split(spec):
    """(optional, base spec)"""
    if isinstance(spec, tuple) and spec[0] == "opt":
        return True, spec[1]
    if isinstance(spec, str) and spec.endswith("?"):
        return True, spec[:-1]
    return False, spec


def validate(schema, params):
    if not isinstance(params, dict):
        raise SchemaError(["params must be an object"])
    problems = ["unknown parameter %s" % k for k in params if k not in schema]
    for name, spec in schema.items():
        optional, base = _split(spec)
        if name not in params or params[name] is None:
            if not optional:
                problems.append("missing parameter %s" % name)
            continue
        p = _check(name, base, params[name])
        if p:
            problems.append(p)
    if problems:
        raise SchemaError(problems)
    return {k: v for k, v in params.items() if v is not None}


def describe(schema):
    """{name: {"type", "required"}} for documentation."""
    out = {}
    for name, spec in schema.items():
        optional, base = _split(spec)
        t = base if isinstance(base, str) else ("enum: " + " | ".join(map(str, base[1])) if base[0] == "enum" else "list of " + str(base[1]))
        out[name] = {"type": t, "required": not optional}
    return out
