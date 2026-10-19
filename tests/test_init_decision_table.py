"""Bảng quyết định của `init`: {OPCOS_WORKSPACES: vắng / có nhưng chưa là trạm / có và đã là trạm}
× {bố cục trạm nhúng trong repo: chưa có / chỉ có tên số ít cũ / đã có workspaces / có cả hai}
× {cách gọi}. Một bảng, một nơi: đổi hành vi thì phải đổi bảng này.

Tên trạm luôn là `voice`, thư mục gốc luôn là `workspaces`:
  · cài cạnh OpcOS (biến đặt) → `<biến>/voice`;
  · cài riêng lẻ → trạm nhúng `<repo>/workspaces`. Tên số ít cũ `<repo>/workspace` chỉ còn được
    NHẬN (khi nó đã là trạm mà `workspaces` chưa có); `init` mới không bao giờ tạo nó.

Luật chung:
  · `--yes` KHÔNG BAO GIỜ hỏi (có hay không có terminal). Biến đặt ⇒ `<biến>/voice` (đã dấu: dùng thẳng,
    chưa dấu: dựng + một dòng); biến vắng ⇒ trạm nhúng. Ngoại lệ: trạm nhúng đã mang dấu (có dữ liệu) mà
    chưa ghi lựa chọn ⇒ GIỮ trạm cũ, không dựng trạm OpcOS rỗng cạnh nó.
  · Không có người (`--non-interactive`, không terminal, hết dữ liệu): biến đặt ⇒ như `--yes`; biến vắng ⇒
    mã 2 (không đoán chế độ).
  · Có người, biến đặt: một câu nhận đường — Enter ra `<biến>/voice` (kể cả khi đã dấu); `1`/`2`/`embedded`/
    `separate` ⇒ mã 2. Biến vắng: câu hỏi hai đường, Enter = trạm nhúng. Ctrl+C ở mọi câu ⇒ lan ra ngoài
    (`contract.run` đổi thành mã 2).
  · `--mode separate`: biến đặt ⇒ `<biến>/voice`; biến vắng ⇒ hỏi đường (có người) hoặc mã 2.
"""
import builtins
import json
import os
from collections import namedtuple

import pytest

from voice_studio import cli, station
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


def _choose(ask, kwargs):
    """`choose_mode`, nhưng Ctrl+C lan ra ở ca KHÔNG mong đợi thì thành lỗi test (không giết cả phiên pytest)."""
    try:
        return station.choose_mode(ask=ask, **kwargs)
    except KeyboardInterrupt:
        raise Boom("Ctrl+C lan ra ở ca không mong đợi")


def _answers(seen, *items):
    """Câu trả lời giả. `seen` ghi lại MỌI lần hỏi (kể cả lần nổ vì hết câu trả lời)."""
    it = iter(items)

    def ask(prompt):
        seen.append(prompt)
        try:
            val = next(it)
        except StopIteration:
            raise Boom("hỏi nhiều hơn dự kiến")
        if isinstance(val, BaseException) or (isinstance(val, type) and issubclass(val, BaseException)):
            raise val
        return val
    return ask


SKIP = "skip"
KEEP_LAYOUTS = ("marked", "old", "both")      # embedded station already carries the marker, no recorded choice

# kwargs cho choose_mode · cách dựng câu trả lời giả (typed_path -> list; phần tử là ngoại lệ thì ném) hoặc None
# · mong đợi(var, layout) · SỐ CÂU HỎI mong đợi(var, layout) — test đếm bằng ĐÚNG số này (hỏi ít hơn cũng đỏ)
# · tty (stdin có phải terminal) · recorded (nội dung studio.local.json đã ghi, "@typed" = đường gõ).
Sc = namedtuple("Sc", "kwargs answers expect asks tty recorded")


def sc(kwargs, answers, expect, asks=0, tty=True, recorded=None):
    return Sc(kwargs, answers, expect, asks if callable(asks) else (lambda var, layout, _n=asks: _n),
              tty, recorded)


def _enter(var, layout):
    return "oc" if var != "unset" and layout not in KEEP_LAYOUTS else "embedded"


def _auto(var, layout):
    """Không hỏi (--yes · không người): có biến ⇒ trạm OpcOS, trừ khi trạm nhúng mang dấu (giữ)."""
    return "embedded" if var == "unset" or layout in KEEP_LAYOUTS else "oc"


def _auto_or_exit2(var, layout):
    return "exit2" if var == "unset" else _auto(var, layout)


def _one_question(var, layout):
    """Câu hỏi có người khi biến đặt: bố cục `both` không có câu nào (the layout with an old marked `workspace` and an unmarked `workspaces`); otherwise exactly one."""
    return 0 if var != "unset" and layout == "both" else 1


def _set_only(fn):
    return lambda var, layout: SKIP if var == "unset" else fn(var, layout)


def _bare_choice(var, layout):
    return "exit2" if layout not in KEEP_LAYOUTS else "embedded"


SCENARIOS = {
    "tuong-tac Enter": sc(dict(), lambda t: [""], _enter, _one_question),
    "tuong-tac 1 (biến vắng)": sc(dict(), lambda t: ["1"],
                                  lambda var, layout: SKIP if var != "unset" else "embedded", 1),
    "tuong-tac 2 roi Enter": sc(dict(), lambda t: ["2", ""],
                                lambda var, layout: SKIP if var != "unset" else "exit2", 2),
    "tuong-tac 2 roi go duong": sc(dict(), lambda t: ["2", t],
                                   lambda var, layout: SKIP if var != "unset" else "typed", 2),
    "tuong-tac (biến đặt) go duong": sc(
        dict(), lambda t: [t],
        _set_only(lambda var, layout: "embedded" if layout in KEEP_LAYOUTS else "typed"), _one_question),
    "tuong-tac 3": sc(dict(), lambda t: ["3"],
                      lambda var, layout: SKIP if var != "unset" else "exit2", 1),
    "--yes": sc(dict(yes=True), None, _auto),
    "--non-interactive": sc(dict(non_interactive=True), None, _auto_or_exit2),
    "--non-interactive --yes": sc(dict(non_interactive=True, yes=True), None, _auto),
    "khong-tty khong co": sc(dict(), None, _auto_or_exit2, tty=False),
    "--mode embedded": sc(dict(mode="embedded"), None, lambda var, layout: "embedded"),
    "--mode separate (co nguoi)": sc(dict(mode="separate"), lambda t: [""],
                                     lambda var, layout: "oc" if var != "unset" else "exit2",
                                     lambda var, layout: 0 if var == "marked" else 1),
    "--mode separate --non-interactive": sc(dict(mode="separate", non_interactive=True), None,
                                            lambda var, layout: "oc" if var != "unset" else "exit2"),
    "--mode separate --yes": sc(dict(mode="separate", yes=True), None,
                                lambda var, layout: "oc" if var != "unset" else "exit2"),
    # câu EOF / Ctrl+C
    "EOF o bang (biến vắng)": sc(dict(), lambda t: [EOFError],
                                 lambda var, layout: "exit2" if var == "unset" else SKIP, 1),
    "EOF o cau duong (biến đặt)": sc(
        dict(), lambda t: [EOFError],
        _set_only(lambda var, layout: "embedded" if layout in KEEP_LAYOUTS else "oc"), _one_question),
    "Ctrl+C o cau hoi": sc(
        dict(), lambda t: [KeyboardInterrupt],
        lambda var, layout: "embedded" if var != "unset" and layout == "both" else "interrupt",
        _one_question),
    # lựa chọn đã ghi thắng biến
    "da ghi embedded + --yes": sc(dict(yes=True), None, lambda var, layout: "embedded",
                                  recorded={"mode": "embedded"}),
    "da ghi embedded + co nguoi": sc(dict(), lambda t: [], lambda var, layout: "embedded",
                                     recorded={"mode": "embedded"}),
    "da ghi separate co duong + --yes": sc(dict(yes=True), None, lambda var, layout: "typed",
                                           recorded={"mode": "separate", "station_path": "@typed"}),
    "da ghi separate thieu duong + --yes": sc(dict(yes=True), None, lambda var, layout: "exit2",
                                              recorded={"mode": "separate"}),
}
# a bare choice typed at the path question: exit code 2; riêng bố cục mang dấu thì đó là câu giữ/chuyển, `1`… không phải từ khoá ⇒ giữ
for _word in ("1", "2", "embedded", "separate"):
    SCENARIOS[f"tuong-tac (biến đặt) go {_word}"] = sc(
        dict(), (lambda t, _w=_word: [_w]), _set_only(_bare_choice), _one_question)


CASES = [(name, layout, var)
         for name in sorted(SCENARIOS)
         for layout in ("none", "old", "new", "both", "marked")
         for var in ("unset", "unmarked", "marked")
         if SCENARIOS[name].expect(var, layout) != SKIP]   # câu hỏi không xuất hiện ở tổ hợp này thì không có ca


@pytest.mark.parametrize("name,layout,var", CASES, ids=[f"{n}|{l}|{v}" for n, l, v in CASES])
def test_decision_table(name, layout, var, world, monkeypatch, capsys):
    s = SCENARIOS[name]
    table = world(layout, var, recorded=s.recorded)
    key = s.expect(var, layout)
    # `tty` của từng ca: mọi đường không-hỏi mà gọi input() là lỗi.
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: s.tty)
    monkeypatch.setattr(builtins, "input", _boom)
    seen = []
    ask = _answers(seen, *s.answers(table["typed_path"])) if s.answers else None
    want = None if key == "interrupt" else table[key]
    if key == "interrupt":
        with pytest.raises(KeyboardInterrupt):        # choose_mode must not catch Ctrl+C
            station.choose_mode(ask=ask, **s.kwargs)
    elif want is None:
        with pytest.raises(ContractError):
            _choose(ask, s.kwargs)
    else:
        mode, st, _why = _choose(ask, s.kwargs)
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


# ── an embedded station that already holds data wins over the variable (no recorded choice) ─────────────────────────

def _tree_state(*roots):
    """Ảnh chụp cây (đường → nội dung) để chứng minh KHÔNG byte nào bị dời/ghi."""
    out = {}
    for root in roots:
        for dp, dn, fn in os.walk(root):
            for n in dn:
                out[os.path.join(dp, n)] = None
            for n in fn:
                p = os.path.join(dp, n)
                with open(p, "rb") as f:
                    out[p] = f.read()
    return out


KEEP_CALLS = {
    # tên ca → (kwargs, answers(t) | None, tty, số câu hỏi)
    "yes": (dict(yes=True), None, True, 0),
    "non-interactive": (dict(non_interactive=True), None, True, 0),
    "khong-tty": (dict(), None, False, 0),
    "Enter": (dict(), lambda t: [""], True, 1),
    "go duong": (dict(), lambda t: [t], True, 1),
    "EOF": (dict(), lambda t: [EOFError], True, 1),
}


@pytest.mark.parametrize("layout", ["marked", "old"])
@pytest.mark.parametrize("var", ["unmarked", "marked"])
@pytest.mark.parametrize("call", sorted(KEEP_CALLS))
def test_old_station_with_data_is_kept_and_says_how_to_move(call, var, layout, world, monkeypatch, capsys):
    """Keep the old embedded station, 1 dòng chỉ cách dời; không bao giờ dựng trạm OpcOS rỗng."""
    kwargs, build, tty, n_asks = KEEP_CALLS[call]
    table = world(layout, var)
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: tty)
    monkeypatch.setattr(builtins, "input", _boom)
    seen = []
    ask = _answers(seen, *build(table["typed_path"])) if build else None
    choice = station.choose_mode(ask=ask, **kwargs)
    mode, st, _why = choice
    assert (mode, os.path.normcase(st)) == (table["embedded"][0], os.path.normcase(table["embedded"][1]))
    assert choice.then_migrate is None
    assert len(seen) == n_asks
    oc = table["oc"][1]
    err = capsys.readouterr().err
    if var == "unmarked":
        assert f"migrate --to separate --station {oc}" in err
    else:                                          # <biến>/voice is a station too
        assert "hai trạm" in err and "migrate --to separate" not in err
        assert f"--station {oc}" in err


@pytest.mark.parametrize("word", ["chuyen", "chuyển", "c", "C", "Chuyen", "  chuyen  "])
@pytest.mark.parametrize("layout", ["marked", "old"])
@pytest.mark.parametrize("var", ["unmarked", "marked"])
def test_old_station_choosing_to_move_returns_a_flag_and_moves_nothing(word, var, layout, world, monkeypatch, capsys):
    """choose_mode never moves anything — nó trả `then_migrate`; `do_init` mới dời sau cổng dry-run."""
    table = world(layout, var)
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: True)
    monkeypatch.setattr(builtins, "input", _boom)
    before = _tree_state(tmp_root(table), )
    seen = []
    choice = station.choose_mode(ask=_answers(seen, word))
    mode, st, _why = choice
    assert (mode, os.path.normcase(st)) == (table["embedded"][0], os.path.normcase(table["embedded"][1]))
    assert os.path.normcase(choice.then_migrate) == os.path.normcase(table["oc"][1])
    assert len(seen) == 1 and "chuyen" in seen[0] and table["oc"][1] in seen[0]
    assert _tree_state(tmp_root(table)) == before          # 0 byte đổi


def tmp_root(table):
    return os.path.dirname(table["typed_path"])


@pytest.mark.parametrize("call", ["yes", "non-interactive", "khong-tty", "Enter"])
@pytest.mark.parametrize("var", ["unmarked", "marked"])
def test_both_layout_keeps_without_any_question_or_migrate_line(call, var, world, monkeypatch, capsys):
    """Layout `both`: the old `workspace` mang dấu + `workspaces` mới chưa dấu ⇒ giữ, 0 câu ở mọi cách
    gọi (kể cả có người), nhắc gộp có sẵn, KHÔNG gợi `migrate` (dời thư mục rỗng là vô nghĩa)."""
    kwargs, build, tty, _n = KEEP_CALLS[call]
    table = world("both", var)
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: tty)
    monkeypatch.setattr(builtins, "input", _boom)
    seen = []
    ask = _answers(seen, *(build(table["typed_path"]) if build else [])) if call == "Enter" else None
    choice = station.choose_mode(ask=ask, **kwargs)
    mode, st, _why = choice
    assert (mode, os.path.normcase(st)) == (table["embedded"][0], os.path.normcase(table["embedded"][1]))
    assert choice.then_migrate is None and seen == []
    err = capsys.readouterr().err
    assert "tên cũ" in err and "migrate --to separate" not in err


# ── odd OPCOS_WORKSPACES values ───────────────────────────────────────────────────

@pytest.mark.parametrize("flags", [["--yes"], ["--non-interactive"], ["--mode", "separate", "--yes"]])
def test_opcos_workspaces_pointing_at_a_file_is_code_2_naming_the_variable(flags, world, tmp_path, monkeypatch, capsys):
    """A caller error: ⇒ mã 2 nêu TÊN BIẾN, không traceback (trước: mã 1)."""
    world("none", "unset")
    f = tmp_path / "la-file"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(f))
    rc = cli.main(["init", "--json", *flags])
    out, err = capsys.readouterr()
    assert rc == 2, err
    last = json.loads(out.strip().splitlines()[-1])
    assert last["code"] == 2 and "OPCOS_WORKSPACES" in last["error"] and "FILE" in last["error"]
    assert "Traceback" not in err
    assert not (tmp_path / "repo" / "studio.local.json").exists()


def test_opcos_workspaces_voice_entry_being_a_file_is_code_2_naming_the_variable(world, tmp_path, monkeypatch, capsys):
    world("none", "unset")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "voice").write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    rc = cli.main(["init", "--yes", "--json"])
    out, err = capsys.readouterr()
    last = json.loads(out.strip().splitlines()[-1])
    # the ERROR itself must name the variable (not just an earlier "[init] separate: dùng … OPCOS_WORKSPACES/voice" line)
    assert rc == 2 and last["code"] == 2 and "OPCOS_WORKSPACES" in last["error"] and "FILE" in last["error"]
    assert "Traceback" not in err and "[init] separate: dùng" not in err


def test_blank_opcos_workspaces_counts_as_unset(world, monkeypatch):
    """Blank/khoảng trắng = vắng ⇒ `--yes` vẫn ra trạm nhúng."""
    table = world("none", "unset")
    monkeypatch.setenv("OPCOS_WORKSPACES", "   ")
    mode, st, _ = station.choose_mode(yes=True)
    assert (mode, os.path.normcase(st)) == (table["embedded"][0], os.path.normcase(table["embedded"][1]))


def test_relative_opcos_workspaces_gives_an_absolute_station_with_yes(world, tmp_path, monkeypatch, capsys):
    """A relative variable ⇒ đường ra là tuyệt đối theo cwd lúc gọi."""
    world("none", "unset")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPCOS_WORKSPACES", "relws")
    mode, st, _ = station.choose_mode(yes=True)
    assert mode == "separate" and os.path.isabs(st)
    assert os.path.normcase(st) == os.path.normcase(str(tmp_path / "relws" / "voice"))


def test_opcos_workspaces_inside_the_repo_is_built_as_asked(world, tmp_path, monkeypatch):
    """Pinned as current behaviour, not a contract: whether this should be refused is still open."""
    world("none", "unset")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(tmp_path / "repo" / "ws"))
    mode, st, _ = station.choose_mode(yes=True)
    assert mode == "separate" and os.path.normcase(st) == os.path.normcase(str(tmp_path / "repo" / "ws" / "voice"))


def test_opcos_workspaces_that_is_itself_a_station_is_nested_as_asked(world, tmp_path, monkeypatch):
    """Pinned as current behaviour, not a contract."""
    world("none", "unset")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "station.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    mode, st, _ = station.choose_mode(yes=True)
    assert mode == "separate" and os.path.normcase(st) == os.path.normcase(str(ws / "voice"))


def test_opcos_voice_dir_not_empty_without_marker_is_used_as_asked(world, tmp_path, monkeypatch):
    """Pinned as current behaviour, not a contract: the directory is used as is, nothing is deleted."""
    world("none", "unset")
    ws = tmp_path / "ws"
    (ws / "voice").mkdir(parents=True)
    (ws / "voice" / "la.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPCOS_WORKSPACES", str(ws))
    mode, st, _ = station.choose_mode(yes=True)
    assert mode == "separate" and os.path.normcase(st) == os.path.normcase(str(ws / "voice"))
    assert (ws / "voice" / "la.txt").read_text(encoding="utf-8") == "x"


# ── dòng in khi dựng trạm OpcOS mới ────────────────────────────────────────────────────────

@pytest.mark.parametrize("call", ["--yes", "--non-interactive", "khong-tty khong co"])
def test_building_the_opcos_station_prints_one_line_with_the_path_and_how_to_change_it(call, world, monkeypatch, capsys):
    table = world("none", "unmarked")
    s = SCENARIOS[call]
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: s.tty)
    monkeypatch.setattr(builtins, "input", _boom)
    station.choose_mode(**s.kwargs)
    err = capsys.readouterr().err
    assert table["oc"][1] in err and "--station" in err
    assert len([ln for ln in err.splitlines() if "OPCOS_WORKSPACES" in ln]) == 1


def test_using_an_already_marked_opcos_station_prints_nothing(world, monkeypatch, capsys):
    world("none", "marked")
    station.choose_mode(yes=True)
    assert capsys.readouterr().err == ""


# ── thứ tự ưu tiên: --station và biến trạm RIÊNG thắng OPCOS_WORKSPACES ──────

OWN_VARS = ("VOICE_STATION", "OMNIVOICE_DIR")
OWN_CALLS = {
    "yes": (dict(yes=True), None, True, 0),
    "non-interactive": (dict(non_interactive=True), None, True, 0),
    "khong-tty": (dict(), None, False, 0),
    "co nguoi": (dict(), lambda t: ["khong-duoc-hoi"], True, 0),
}


@pytest.mark.parametrize("call", sorted(OWN_CALLS))
@pytest.mark.parametrize("var", ["unset", "unmarked", "marked"])
@pytest.mark.parametrize("own", OWN_VARS)
def test_own_station_variable_beats_opcos_workspaces_and_is_never_asked_about(own, var, call, world, tmp_path,
                                                                              monkeypatch):
    """A station-specific variable (VOICE_STATION · OMNIVOICE_DIR) ⇒ separate tại trạm đó, 0 câu, không tạo workspaces/."""
    world("marked", var)
    st = tmp_path / "tram-rieng"
    monkeypatch.setenv(own, str(st / "omnivoice") if own == "OMNIVOICE_DIR" else str(st))
    kwargs, build, tty, _n = OWN_CALLS[call]
    monkeypatch.setattr(station, "_stdin_is_tty", lambda: tty)
    monkeypatch.setattr(builtins, "input", _boom)
    seen = []
    ask = _answers(seen, "khong-duoc-hoi") if build else None
    mode, got, _why = station.choose_mode(ask=ask, **kwargs)
    assert mode == "separate" and os.path.normcase(got) == os.path.normcase(str(st))
    assert len(seen) == 0


@pytest.mark.parametrize("own", OWN_VARS)
@pytest.mark.parametrize("var", ["unset", "unmarked"])
def test_explicit_embedded_with_an_own_station_variable_is_code_2(own, var, world, tmp_path, monkeypatch):
    """`--mode embedded` + biến trạm riêng ⇒ mã 2 ('hai nguồn sự thật')."""
    world("none", var)
    monkeypatch.setenv(own, str(tmp_path / "tram-rieng"))
    with pytest.raises(ContractError, match="hai nguồn sự thật"):
        station.choose_mode(mode="embedded")


@pytest.mark.parametrize("var", ["unset", "unmarked", "marked"])
@pytest.mark.parametrize("layout", ["none", "marked", "old", "both"])
def test_station_flag_beats_everything_and_is_made_absolute(layout, var, world, tmp_path, monkeypatch):
    """`--station` ⇒ separate tại đường đó (tuyệt đối theo cwd), 0 câu, bất kể biến/bố cục."""
    world(layout, var)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "input", _boom)
    mode, got, why = station.choose_mode(station="tram-tuong-doi", yes=True)
    assert (mode, why) == ("separate", "--station")
    assert os.path.normcase(got) == os.path.normcase(str(tmp_path / "tram-tuong-doi"))
