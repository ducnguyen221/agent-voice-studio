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
import os

import pytest

from voice_studio import station
from voice_studio.contract import ContractError


class Boom(AssertionError):
    pass


def _boom(*_a, **_k):
    raise Boom("không được hỏi (input() bị gọi)")


@pytest.fixture
def world(tmp_path, monkeypatch):
    def build(layout, var):
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
        ws = tmp_path / "ws"
        if var != "unset":
            (ws / "voice").mkdir(parents=True)
            monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
            if var == "marked":
                (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
        typed = tmp_path / "go-vao"
        return {"embedded": ("embedded", str(old if layout == "old" else new)),
                "oc": ("separate", str(ws / "voice")),
                "typed": ("separate", str(typed)),
                "typed_path": str(typed),
                "exit2": None}
    return build


def _answers(*items):
    it = iter(items)

    def ask(_prompt):
        try:
            return next(it)
        except StopIteration:
            raise Boom("hỏi nhiều hơn dự kiến")
    return ask


SKIP = "skip"


def _enter(var):
    return "oc" if var != "unset" else "embedded"


# tên -> (kwargs cho choose_mode, cách dựng câu trả lời giả (typed_path -> list) hoặc None, mong đợi(var))
SCENARIOS = {
    "tuong-tac Enter": (dict(), lambda t: [""], _enter),
    "tuong-tac 1 (biến vắng)": (dict(), lambda t: ["1"],
                                lambda var: SKIP if var != "unset" else "embedded"),
    "tuong-tac 2 roi Enter": (dict(), lambda t: ["2", ""],
                              lambda var: SKIP if var != "unset" else "exit2"),
    "tuong-tac 2 roi go duong": (dict(), lambda t: ["2", t],
                                 lambda var: SKIP if var != "unset" else "typed"),
    "tuong-tac (biến đặt) go duong": (dict(), lambda t: [t],
                                      lambda var: "typed" if var != "unset" else SKIP),
    "tuong-tac 3": (dict(), lambda t: ["3"], lambda var: SKIP if var != "unset" else "exit2"),
    "--yes": (dict(yes=True), None, lambda var: "embedded"),
    "--non-interactive": (dict(non_interactive=True), None, lambda var: "exit2"),
    "--non-interactive --yes": (dict(non_interactive=True, yes=True), None, lambda var: "embedded"),
    "--mode embedded": (dict(mode="embedded"), None, lambda var: "embedded"),
    "--mode separate (co nguoi)": (dict(mode="separate"), lambda t: [""],
                                   lambda var: "oc" if var != "unset" else "exit2"),
    "--mode separate --non-interactive": (dict(mode="separate", non_interactive=True), None,
                                          lambda var: "oc" if var != "unset" else "exit2"),
    "--mode separate --yes": (dict(mode="separate", yes=True), None,
                              lambda var: "oc" if var != "unset" else "exit2"),
}


CASES = [(name, layout, var)
         for name in sorted(SCENARIOS)
         for layout in ("none", "old", "new", "both")
         for var in ("unset", "unmarked", "marked")
         if SCENARIOS[name][2](var) != SKIP]            # câu hỏi không xuất hiện ở tổ hợp này thì không có ca


@pytest.mark.parametrize("name,layout,var", CASES, ids=[f"{n}|{l}|{v}" for n, l, v in CASES])
def test_decision_table(name, layout, var, world, monkeypatch, capsys):
    kwargs, build_answers, expect = SCENARIOS[name]
    table = world(layout, var)
    key = expect(var)
    # Có terminal nhưng KHÔNG ai ngồi đó: mọi đường không-hỏi mà gọi input() là lỗi.
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr(builtins, "input", _boom)
    ask = _answers(*build_answers(table["typed_path"])) if build_answers else None
    want = table[key]
    if want is None:
        with pytest.raises(ContractError):
            station.choose_mode(ask=ask, **kwargs)
    else:
        mode, st, _why = station.choose_mode(ask=ask, **kwargs)
        assert (mode, os.path.normcase(st)) == (want[0], os.path.normcase(want[1]))
    _out, err = capsys.readouterr()
    # không bao giờ nhắc tới thư mục ẩn dưới home: không còn khái niệm đó
    assert "." + "voice" not in err


@pytest.mark.parametrize("layout", ["none", "old", "new", "both"])
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
