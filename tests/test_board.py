"""The board tool: the checked-in board is valid, and the overlap rule that keeps claimed work apart."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("board", Path(__file__).resolve().parents[1] / "tools" / "board.py")
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)

FILES = ["solarbench/tasks/clamp_env.py", "solarbench/tasks/skills.py", "docs/tasks.md", "ASSUMPTIONS.md"]


def item(*touches):
    return {"touches": list(touches)}


def test_checked_in_board_is_valid():
    assert board.check(board.load(), {}) == []


def test_same_file_overlaps():
    a, b = item("solarbench/tasks/clamp_env.py"), item("solarbench/tasks/clamp_env.py", "tests/x.py")
    assert board.overlap(a, b, FILES) == ["solarbench/tasks/clamp_env.py"]


def test_glob_overlaps_a_file_it_matches():
    assert board.overlap(item("solarbench/tasks/*"), item("solarbench/tasks/skills.py"), FILES)


def test_disjoint_paths_do_not_overlap():
    assert board.overlap(item("solarbench/agents/endpoint.py"), item("solarbench/tasks/skills.py"), FILES) == []


def test_append_only_files_never_overlap():
    assert board.overlap(item("ASSUMPTIONS.md", "docs/tasks.md"), item("ASSUMPTIONS.md", "docs/tasks.md"), FILES) == []


def test_next_lists_only_what_can_be_started_with_the_compute_at_hand():
    def it(id, needs, size, status="todo", deps=()):
        return {"id": id, "needs": needs, "size": size, "status": status, "depends_on": list(deps),
                "priority": "core", "milestone": "v1"}

    items = {i["id"]: i for i in (it("a", "none", "medium"), it("b", "gpu", "small"), it("c", "cpu", "small"),
                                  it("d", "cpu", "small", deps=["a"]), it("e", "none", "small", status="done"))}
    rows = board.startable(items, {"c": items["c"]}, {"none", "cpu"}, set(board.SIZES))
    assert [r["id"] for r in rows] == ["a"]  # b needs a GPU, c is claimed, d waits on a, e is done
