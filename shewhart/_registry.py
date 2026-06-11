"""Chart registry: the extension point everything plugs into.

Internal charts self-register via the decorator; external packages will later
register through the ``shewhart.plugins`` entry-point group. ``sw.chart()`` is
the dispatcher reserved for registry access — every core chart also has its
own top-level function.
"""

from __future__ import annotations

from typing import Callable

_CHARTS: dict[str, Callable] = {}


def register(alias: str) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        _CHARTS[alias] = fn
        return fn

    return decorator


def available() -> list[str]:
    return sorted(_CHARTS)


def chart(alias: str, *args, **kwargs):
    """Dispatch to a registered chart by its stable alias."""
    try:
        fn = _CHARTS[alias]
    except KeyError:
        options = ", ".join(available()) or "(none)"
        raise ValueError(
            f"Unknown chart {alias!r}. Registered charts: {options}. "
            'Example: sw.chart("imr", df, value="x")'
        ) from None
    return fn(*args, **kwargs)
