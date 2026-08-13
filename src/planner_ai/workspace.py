from pathlib import Path


def get_workspace_cwd() -> Path:
    """Absolute directory the CLI was launched in — same rule as Claude Code."""
    return Path.cwd().resolve()
