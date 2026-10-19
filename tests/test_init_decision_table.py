"""Bảng quyết định của `init`: {OPCOS_WORKSPACES: vắng / có nhưng chưa là trạm / có và đã là trạm}
× {bố cục trạm nhúng trong repo: chưa có / chỉ có tên số ít cũ / đã có workspaces / có cả hai}
× {cách gọi}. Một bảng, một nơi: đổi hành vi thì phải đổi bảng này.

Tên trạm luôn là `voice`, thư mục gốc luôn là `workspaces`:
  · cài cạnh OpcOS (biến đặt) → `<biến>/voice`;
  · cài riêng lẻ → trạm nhúng `<repo>/workspaces`. Tên số ít cũ `<repo>/workspace` chỉ còn được
    NHẬN (khi nó đã là trạm mà `workspaces` chưa có); `init` mới không bao giờ tạo nó.

Luật chung:
  · `--yes` KHÔNG BAO GIỜ hỏi (có hay không có terminal) và dùng trạm nhúng, không bao giờ đặt vào
    thư mục dùng chung.
  · `--non-interactive` thiếu cả `--yes` lẫn `--mode` ⇒ mã 2 (không đoán chế độ).
  · Có người, biến đặt: một câu xác nhận/đổi — Enter ra `<biến>/voice`. Biến vắng: câu hỏi hai đường,
    Enter = trạm nhúng.
  · `--mode separate`: biến đặt ⇒ `<biến>/voice`; biến vắng ⇒ hỏi đường (có người) hoặc mã 2.
"""
import builtins
import json
import os
from collections import namedtuple

import pytest

from voice_studio import station
from voice_studio.contract import ContractError


class Boom(AssertionError):
    pass


def _boom(*_a, **_k):
    raise Boom("không được hỏi (input() bị gọi)")


@pytest.fixture
def world(tmp_path, monkeypatch):
    def build(layout, var, recorded=None):
        repo = tmp_path / "repo"
        (repo / "voice_studio").mkdir(parents=True)
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        monkeypatch.setenv("VOICE_STUDIO_REPO", str(repo))
        (tmp_path / "home").mkdir(exist_ok=True)
        old, new = repo / "workspace", repo / "workspaces"
        if layout in ("old", "both"):
            (old / "omnivoice" / "voices").mkdir(parents=True)
        if layout in ("new", "both"):
            new.mkdir(parents=True)
        if layout == "marked":                       # trạm nhúng ĐÃ mang dấu ở tên mới
            (new / "omnivoice" / "voices").mkdir(parents=True)
        ws = tmp_path / "ws"
        if var != "unset":
            (ws / "voice").mkdir(parents=True)
            monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
            if var == "marked":
                (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
        typed = tmp_path / "go-vao"
        if recorded is not None:                     # lựa chọn đã ghi trong studio.local.json
            rec = {k: (str(typed) if v == "@typed" else v) for k, v in recorded.items()}
            (repo / "studio.local.json").write_text(json.dumps(rec), encoding="utf-8")
        return {"embedded": ("embedded", str(old if layout == "old" else new)),
                "oc": ("separate", str(ws / "voice")),
                "typed": ("separate", str(typed)),
                "typed_path": str(typed),
                "exit2": None}
    return build


def _answers(seen, *items):
    """Câu trả lời giả. `seen` ghi lại MỌI lần hỏi (kể cả lần nổ vì hết câu trả lời)."""
    it = iter(items)

    def ask(prompt):
        seen.append(prompt)
        try:
            return next(it)
        except StopIteration:
            raise Boom("hỏi nhiều hơn dự kiến")
    return ask


SKIP = "skip"

# kwargs cho choose_mode · cách dựng câu trả lời giả (typed_path -> list) hoặc None · mong đợi(var, layout)
# · SỐ CÂU HỎI mong đợi(var, layout) — test đếm bằng ĐÚNG số này (hỏi ít hơn cũng đỏ) · tty (stdin có phải terminal).
Sc = namedtuple("Sc", "kwargs answers expect asks tty")


def sc(kwargs, answers, expect, asks=0, tty=True):
    return Sc(kwargs, answers, expect, asks if callable(asks) else (lambda var, layout, _n=asks: _n), tty)


def _enter(var, layout):
    return "oc" if var != "unset" else "embedded"


SCENARIOS = {
    "tuong-tac Enter": sc(dict(), lambda t: [""], _enter, 1),
    "tuong-tac 1 (biến vắng)": sc(dict(), lambda t: ["1"],
                                  lambda var, layout: SKIP if var != "unset" else "embedded", 1),
    "tuong-tac 2 roi Enter": sc(dict(), lambda t: ["2", ""],
                                lambda var, layout: SKIP if var != "unset" else "exit2", 2),
    "tuong-tac 2 roi go duong": sc(dict(), lambda t: ["2", t],
                                   lambda var, layout: SKIP if var != "unset" else "typed", 2),
    "tuong-tac (biến đặt) go duong": sc(dict(), lambda t: [t],
                                        lambda var, layout: "typed" if var != "unset" else SKIP, 1),
    "tuong-tac 3": sc(dict(), lambda t: ["3"],
                      lambda var, layout: SKIP if var != "unset" else "exit2", 1),
    "--yes": sc(dict(yes=True), None, lambda var, layout: "embedded"),
    "--non-interactive": sc(dict(non_interactive=True), None, lambda var, layout: "exit2"),
    "--non-interactive --yes": sc(dict(non_interactive=True, yes=True), None,
                                  lambda var, layout: "embedded"),
    "--mode embedded": sc(dict(mode="embedded"), None, lambda var, layout: "embedded"),
    "--mode separate (co nguoi)": sc(dict(mode="separate"), lambda t: [""],
                                     lambda var, layout: "oc" if var != "unset" else "exit2",
                                     lambda var, layout: 0 if var == "marked" else 1),
    "--mode separate --non-interactive": sc(dict(mode="separate", non_interactive=True), None,
                                            lambda var, layout: "oc" if var != "unset" else "exit2"),
    "--mode separate --yes": sc(dict(mode="separate", yes=True), None,
                                lambda var, layout: "oc" if var != "unset" else "exit2"),
}


CASES = [(name, layout, var)
         for name in sorted(SCENARIOS)
         for layout in ("none", "old", "new", "both", "marked")
         for var in ("unset", "unmarked", "marked")
         if SCENARIOS[name].expect(var, layout) != SKIP]   # câu hỏi không xuất hiện ở tổ hợp này thì không có ca


@pytest.mark.parametrize("name,layout,var", CASES, ids=[f"{n}|{l}|{v}" for n, l, v in CASES])
def test_decision_table(name, layout, var, world, monkeypatch, capsys):
    s = SCENARIOS[name]
    table = world(layout, var)
    key = s.expect(var, layout)
    # `tty` của từng ca: mọi đường không-hỏi mà gọi input() là lỗi.
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: s.tty)
    monkeypatch.setattr(builtins, "input", _boom)
    seen = []
    ask = _answers(seen, *s.answers(table["typed_path"])) if s.answers else None
    want = table[key]
    if want is None:
        with pytest.raises(ContractError):
            station.choose_mode(ask=ask, **s.kwargs)
    else:
        mode, st, _why = station.choose_mode(ask=ask, **s.kwargs)
        assert (mode, os.path.normcase(st)) == (want[0], os.path.normcase(want[1]))
    assert len(seen) == s.asks(var, layout), f"số câu hỏi: {len(seen)} ≠ {s.asks(var, layout)}"
    _out, err = capsys.readouterr()
    # không bao giờ nhắc tới thư mục ẩn dưới home: không còn khái niệm đó
    assert "." + "voice" not in err


@pytest.mark.parametrize("layout", ["none", "old", "new", "both", "marked"])
def test_embedded_layout_rules(layout, world, capsys):
    table = world(layout, "unset")
    mode, st, _ = station.choose_mode(yes=True)
    assert (mode, os.path.normcase(st)) == (table["embedded"][0], os.path.normcase(table["embedded"][1]))
    err = capsys.readouterr().err
    if layout in ("old", "both"):
        assert "workspaces" in err                    # đúng một dòng khuyến nghị về bố cục
    else:
        assert "workspaces" not in err


@pytest.mark.parametrize("var", ["unset", "unmarked", "marked"])
def test_label_names_the_real_path(var, world):
    """Câu hỏi in đúng đường mà Enter sẽ dùng."""
    table = world("none", var)
    prompts = []

    def ask(p):
        prompts.append(p)
        return ""
    mode, st, _ = station.choose_mode(ask=ask)
    assert os.path.normcase(st) in os.path.normcase(prompts[0])
    want = table["oc"] if var != "unset" else table["embedded"]
    assert (mode, os.path.normcase(st)) == (want[0], os.path.normcase(want[1]))
