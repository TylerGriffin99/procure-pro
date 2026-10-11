"""Prompt and playbook text for harness phases.

Every prompt the harness sends lives as a ``.md`` file beside this module and is read
through :func:`load_prompt`; format playbooks live in ``../playbooks/formats`` and are
read through :func:`load_playbook`. Nothing else in the codebase builds prompt paths.
"""

from __future__ import annotations

import functools
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
PLAYBOOKS_DIR = PROMPTS_DIR.parent / "playbooks" / "formats"


@functools.cache
def load_prompt(name: str) -> str:
    """Return the text of ``prompts/<name>.md``. Raises FileNotFoundError naming the path."""
    return read_markdown(PROMPTS_DIR / f"{name}.md")


@functools.cache
def load_playbook(fmt: str) -> str:
    """Return the text of ``playbooks/formats/<fmt>.md``. FileNotFoundError names the path."""
    return read_markdown(PLAYBOOKS_DIR / f"{fmt}.md")


def read_markdown(path: Path) -> str:
    """Return the text at ``path``. OS errors propagate as-is; FileNotFoundError names
    the path."""
    return path.read_text()
