"""Bảng quyết định của `init`: {trạm cũ dưới home có/không} × {OPCOS_WORKSPACES: vắng / có nhưng chưa
là trạm / có và đã là trạm} × {cách gọi}. Một bảng, một nơi: đổi hành vi thì phải đổi bảng này.

Luật chung:
  · `--yes` KHÔNG BAO GIỜ hỏi (có hay không có terminal) và dùng trạm mới = `<repo>/workspace`.
  · `--non-interactive` thiếu cả `--yes` lẫn `--mode` ⇒ mã 2 (không đoán chế độ).
  · Có người: Enter ở câu hỏi ba đường = [1] "trạm mới" — `<OPCOS_WORKSPACES>/voice` nếu biến đặt, không
    thì `<repo>/workspace`; nhãn [1] in đúng đường đó.
  · `--mode separate`: biến đặt ⇒ `<biến>/voice`; biến vắng ⇒ hỏi đường (có người) hoặc mã 2.
  · Trạm cũ KHÔNG BAO GIỜ được tự nhận; chỉ `--station <đường>` hoặc trả lời [2].
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
    def build(legacy, var):
        repo = tmp_path / "repo"
        (repo / "voice_studio").mkdir(parents=True)
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        monkeypatch.setenv("VOICE_STUDIO_REPO", str(repo))
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        if legacy:
            (home / ".voice" / "omnivoice" / "voices").mkdir(parents=True)
        ws = tmp_path / "ws"
        if var != "unset":
            (ws / "voice").mkdir(parents=True)
            monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
            if var == "marked":
                (ws / "voice" / "station.json").write_text("{}", encoding="utf-8")
        return {"embedded": ("embedded", str(repo / "workspace")),
                "oc": ("separate", str(ws / "voice")),
                "old": ("separate", str(home / ".voice")),
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


# scenario -> (kwargs cho choose_mode, câu trả lời giả hoặc None, hàm mong đợi(legacy, var) -> khoá kết quả)
def _enter_or_1(legacy, var):
    if legacy:
        return "oc" if var != "unset" else "embedded"
    return "embedded"                       # câu hỏi hai đường: 1/Enter = embedded


SCENARIOS = {
    "tuong-tac Enter": (dict(), [""], _enter_or_1),
    "tuong-tac 1": (dict(), ["1"], _enter_or_1),
    "tuong-tac 2": (dict(), ["2", ""],
                    lambda legacy, var: "old" if legacy else ("oc" if var != "unset" else "exit2")),
    "tuong-tac 3": (dict(), ["3"], lambda legacy, var: "exit2"),
    "--yes": (dict(yes=True), None, lambda legacy, var: "embedded"),
    "--non-interactive": (dict(non_interactive=True), None, lambda legacy, var: "exit2"),
    "--non-interactive --yes": (dict(non_interactive=True, yes=True), None, lambda legacy, var: "embedded"),
    "--mode embedded": (dict(mode="embedded"), None, lambda legacy, var: "embedded"),
    "--mode separate (co nguoi)": (dict(mode="separate"), [""],
                                   lambda legacy, var: "oc" if var != "unset" else "exit2"),
    "--mode separate --non-interactive": (dict(mode="separate", non_interactive=True), None,
                                          lambda legacy, var: "oc" if var != "unset" else "exit2"),
    "--mode separate --yes": (dict(mode="separate", yes=True), None,
                              lambda legacy, var: "oc" if var != "unset" else "exit2"),
}


@pytest.mark.parametrize("var", ["unset", "unmarked", "marked"])
@pytest.mark.parametrize("legacy", [False, True], ids=["khong-tram-cu", "co-tram-cu"])
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_decision_table(name, legacy, var, world, monkeypatch, capsys):
    kwargs, answers, expect = SCENARIOS[name]
    table = world(legacy, var)
    # Có terminal nhưng KHÔNG ai ngồi đó: mọi đường không-hỏi mà gọi input() là lỗi.
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr(builtins, "input", _boom)
    ask = _answers(*answers) if answers is not None else None
    want = table[expect(legacy, var)]
    if want is None:
        with pytest.raises(ContractError):
            station.choose_mode(ask=ask, **kwargs)
    else:
        mode, st, _why = station.choose_mode(ask=ask, **kwargs)
        assert (mode, os.path.normcase(st)) == (want[0], os.path.normcase(want[1]))
    _out, err = capsys.readouterr()
    if legacy and answers is None:
        # không có người: trạm cũ được NÓI RÕ và cách nhận nó, không bao giờ được nhận
        old = table["old"][1]
        assert old in err and f"--station {old}" in err
    if want is not None and legacy and name.startswith("tuong-tac") and name != "tuong-tac 2":
        assert os.path.normcase(want[1]) != os.path.normcase(table["old"][1])


@pytest.mark.parametrize("var", ["unset", "unmarked", "marked"])
def test_label_one_prints_the_real_path(var, world):
    """Nhãn [1] in đúng đường mà Enter sẽ dùng."""
    table = world(True, var)
    prompts = []

    def ask(p):
        prompts.append(p)
        return ""
    mode, st, _ = station.choose_mode(ask=ask)
    option1 = prompts[0].split("[2]")[0]
    assert os.path.normcase(st) in os.path.normcase(option1)
    want = table["oc"] if var != "unset" else table["embedded"]
    assert (mode, os.path.normcase(st)) == (want[0], os.path.normcase(want[1]))
