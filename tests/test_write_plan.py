from __future__ import annotations

from pathlib import Path

from planner_ai.write_plan import PLAN_BAK_FILENAME, PLAN_FILENAME, write_plan


def test_write_plan_creates_when_missing(tmp_path: Path) -> None:
    plan_path = write_plan("# New plan\n", cwd=tmp_path)
    assert plan_path == tmp_path / PLAN_FILENAME
    assert plan_path.read_text(encoding="utf-8") == "# New plan\n"
    assert not (tmp_path / PLAN_BAK_FILENAME).exists()


def test_write_plan_backs_up_existing(tmp_path: Path) -> None:
    existing = tmp_path / PLAN_FILENAME
    existing.write_text("# Old plan\n", encoding="utf-8")

    write_plan("# New plan\n", cwd=tmp_path)

    assert (tmp_path / PLAN_BAK_FILENAME).read_text(encoding="utf-8") == "# Old plan\n"
    assert (tmp_path / PLAN_FILENAME).read_text(encoding="utf-8") == "# New plan\n"


def test_write_plan_overwrites_bak_with_previous(tmp_path: Path) -> None:
    (tmp_path / PLAN_FILENAME).write_text("v1", encoding="utf-8")
    write_plan("v2", cwd=tmp_path)
    assert (tmp_path / PLAN_BAK_FILENAME).read_text(encoding="utf-8") == "v1"

    write_plan("v3", cwd=tmp_path)
    assert (tmp_path / PLAN_BAK_FILENAME).read_text(encoding="utf-8") == "v2"
    assert (tmp_path / PLAN_FILENAME).read_text(encoding="utf-8") == "v3"


def test_write_plan_default_cwd_is_workspace(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    plan_path = write_plan("from cwd")
    assert plan_path == tmp_path.resolve() / PLAN_FILENAME
    assert plan_path.read_text(encoding="utf-8") == "from cwd"
