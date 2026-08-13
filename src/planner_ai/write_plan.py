from __future__ import annotations

import shutil
from pathlib import Path

from planner_ai.workspace import get_workspace_cwd

PLAN_FILENAME = "plan.md"
PLAN_BAK_FILENAME = "plan.md.bak"


def write_plan(plan: str, cwd: Path | None = None) -> Path:
    cwd = cwd or get_workspace_cwd()
    plan_path = cwd / PLAN_FILENAME
    bak_path = cwd / PLAN_BAK_FILENAME
    if plan_path.exists():
        shutil.copyfile(plan_path, bak_path)
    plan_path.write_text(plan, encoding="utf-8")
    return plan_path
