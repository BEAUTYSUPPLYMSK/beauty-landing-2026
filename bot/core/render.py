"""Template rendering: substitute {placeholders}, leaving unknown ones intact."""

from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return "{" + key + "}"


def render_template(body: str, variables: dict[str, object] | None = None) -> str:
    """Render a template body.

    Known placeholders are substituted; unknown ones are left as-is so the
    admin can still fill them in manually before publishing.
    """
    variables = variables or {}
    return body.format_map(_SafeDict({k: str(v) for k, v in variables.items()}))


def extract_placeholders(body: str) -> list[str]:
    """Return the ordered, de-duplicated list of {placeholders} in a body."""
    seen: list[str] = []
    for match in _PLACEHOLDER_RE.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen
