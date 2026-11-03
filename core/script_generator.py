# root/core/script_generator.py
"""Deterministic generation of RouterOS scripts from editable header declarations.

Only recognized string-literal assignments before the cutoff marker are changed.
The protected body is never text-substituted; RouterOS resolves $variables at runtime.
This is not a RouterOS parser or a safety certification for arbitrary commands.
"""
import re

MARKER = "### DO NOT EDIT FROM HERE ###"
NAME = r"[A-Za-z_][A-Za-z0-9_]*"
DECLARATION = re.compile(
    rf'^(?P<prefix>\s*:(?:global\s+(?P<global>{NAME})|set\s+\$(?P<set>{NAME}))\s+)'
    rf'(?P<value>"(?:\\.|[^"\\])*")(?P<suffix>\s*(?:\#.*)?)$'
)


def escape_routeros_string(value):
    """Encode an input as a RouterOS double-quoted literal.

    Reject line breaks rather than silently generating multi-line commands.
    """
    if not isinstance(value, str):
        raise ValueError("Parameter values must be strings")
    if any(c in value for c in ("\r", "\n", "\x00")):
        raise ValueError("Parameter values cannot contain line breaks or NUL")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '"'


def generate_script(source, values):
    if not isinstance(source, str) or not isinstance(values, dict):
        raise ValueError("Invalid script template or parameters")
    if source.count(MARKER) != 1:
        raise ValueError("Template must contain exactly one cutoff marker")
    header, body = source.split(MARKER, 1)
    requested = set(values)
    if any(not re.fullmatch(NAME, name) for name in requested):
        raise ValueError("Invalid parameter name")
    seen = set()
    output = []
    for line in header.splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        ending = line[len(raw):]
        match = DECLARATION.fullmatch(raw)
        if match:
            name = match.group("global") or match.group("set")
            if name in requested:
                seen.add(name)
                raw = match.group("prefix") + escape_routeros_string(values[name]) + match.group("suffix")
        output.append(raw + ending)
    missing = requested - seen
    if missing:
        raise ValueError("No supported string declaration for: " + ", ".join(sorted(missing)))
    return "".join(output) + MARKER + body
