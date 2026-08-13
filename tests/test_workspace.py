from pathlib import Path

from planner_ai.workspace import get_workspace_cwd


def test_get_workspace_cwd_is_resolved_cwd(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    assert get_workspace_cwd() == tmp_path.resolve()
