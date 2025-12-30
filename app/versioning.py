"""Helpers for sharing the App Blocker version string."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def _fallback_parse(pyproject_path: Path) -> str:
    """Fallback parser when tomllib is unavailable (Python < 3.11)."""
    try:
        with open(pyproject_path, "r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if stripped.startswith("version") and "=" in stripped:
                    # Split on the first "=" and strip quotes/spaces
                    _, value = stripped.split("=", 1)
                    return value.strip().strip('"')
    except FileNotFoundError as exc:  # pragma: no cover - surfaced via RuntimeError
        raise RuntimeError("pyproject.toml not found for version discovery") from exc

    raise RuntimeError("Version key not found in pyproject.toml")


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the canonical application version from pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"

    if tomllib is None:  # pragma: no cover - executed only on Python < 3.11
        return _fallback_parse(pyproject_path)

    try:
        with open(pyproject_path, "rb") as file:
            data = tomllib.load(file)
        return data["tool"]["poetry"]["version"]
    except FileNotFoundError as exc:
        raise RuntimeError("pyproject.toml not found for version discovery") from exc
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Invalid pyproject.toml structure") from exc


VERSION = get_version()
