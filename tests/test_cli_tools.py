"""Bộ điều phối `voice-studio`, `doctor`, công cụ làm sạch theo hệ điều hành, và cổng
"không còn dây rốn vào trạm cũ" cho `studio/` + `voice_studio/`.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import last_json
from voice_studio import _env, cli
from voice_studio.clean import clean_voice

ROOT = Path(__file__).resolve().parent.parent


def run(capsys, *argv):
    rc = cli.main(list(argv))
    out, err = capsys.readouterr()
    return rc, out, err


# ── điều phối ──────────────────────────────────────────────────────────────────────────

def test_usage_lists_every_command(capsys):
    rc, out, _ = run(capsys)
    assert rc == 0
    for name in cli.COMMANDS:
        assert f"  {name} " in out


def test_unknown_command_is_2(capsys):
    assert run(capsys, "noi-bua")[0] == 2


@pytest.mark.parametrize("cmd", ["init", "export", "import", "backup", "migrate", "update"])
def test_station_commands_help_is_0(cmd, capsys):
    assert run(capsys, cmd, "--help")[0] == 0


@pytest.mark.parametrize("cmd", ["speak", "narrate", "make-profile", "clone", "reftext", "tts",
                                 "doctor", "bgm"])
def test_contract_commands_help_is_0(cmd, capsys):
    assert run(capsys, cmd, "--help")[0] == 0


@pytest.mark.parametrize("cmd", ["ui", "tts", "clean", "verify"])
def test_help_runs_as_real_process_without_engine(cmd):
    """`ui --help`, `tts --help`… phải chạy được trên máy chưa cài gradio/torch/engine."""
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "voice_studio", cmd, "--help"], capture_output=True,
                       text=True, encoding="utf-8", env=env, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "usage" in r.stdout.lower()


def test_lab_dispatch(capsys):
    assert run(capsys, "lab")[0] == 0
    assert run(capsys, "lab", "khong-co")[0] == 2
    for tool, mod in cli.LAB.items():
        __import__(mod)
        assert callable(sys.modules[mod].main), tool


def test_bgm_is_wired_to_cli(tmp_path, capsys):
    from voice_studio import bgm
    d = bgm.init_library(str(tmp_path / "bgm"))
    rc, out, _ = run(capsys, "bgm", "list", "--dir", d, "--json")
    assert rc == 0 and last_json(out)["default"] == "neutral"


def test_lab_work_lives_in_station_not_in_package(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    assert _env.work_dir() == str(tmp_path / "st" / "out")
    assert _env.lab_dir("x", "a.json") == str(tmp_path / "st" / "out" / "lab" / "x" / "a.json")
    monkeypatch.setenv("VOICE_STUDIO_WORK", str(tmp_path / "w"))
    assert _env.lab_dir("x") == str(tmp_path / "w" / "lab" / "x")
    assert str(ROOT) not in _env.lab_dir("x")


# ── doctor ─────────────────────────────────────────────────────────────────────────────

def test_doctor_red_on_bare_machine(capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "omnivoice", None)
    rc, out, err = run(capsys, "doctor", "--json")
    assert rc == 3
    res = last_json(out)
    assert res["ok"] is False and res["code"] == 3
    assert {"station", "voices", "torch", "omnivoice"} <= set(res["errors"])
    assert "pip install" in err                     # có hướng dẫn cài phần còn thiếu


def test_doctor_green_with_station_and_engine(station, fake_engine, capsys, monkeypatch, tmp_path):
    (station / "omnivoice" / "voices" / "_default.txt").write_text("demo", encoding="utf-8")
    monkeypatch.setenv("OMNIVOICE_DIR", str(station / "omnivoice"))
    monkeypatch.delenv("VOICE_STATION")
    rc, out, _ = run(capsys, "doctor", "--json")
    assert rc == 0
    res = last_json(out)
    assert res["errors"] == []
    assert "env-name" in res["warnings"]            # tên biến cũ bị nhắc đổi
    assert os.path.samefile(res["station"], station)


# ── làm sạch: đường venv theo hệ điều hành ─────────────────────────────────────────────

def test_venv_python_per_os(tmp_path):
    assert clean_voice.venv_python(tmp_path, ".venv-sep", windows=True) == \
        tmp_path / ".venv-sep" / "Scripts" / "python.exe"
    assert clean_voice.venv_python(tmp_path, ".venv-cv", windows=False) == \
        tmp_path / ".venv-cv" / "bin" / "python"


def test_clean_dir_resolution_order(tmp_path, monkeypatch):
    assert clean_voice.resolve_clean_dir() == Path.home() / ".voice" / "voice-clean"
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "old" / "omnivoice"))
    assert clean_voice.resolve_clean_dir() == (tmp_path / "old" / "voice-clean").resolve()
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    assert clean_voice.resolve_clean_dir() == (tmp_path / "st" / "voice-clean").resolve()
    monkeypatch.setenv("VOICE_CLEAN_DIR", str(tmp_path / "vc"))
    assert clean_voice.resolve_clean_dir() == (tmp_path / "vc").resolve()
    assert clean_voice.resolve_clean_dir(str(tmp_path / "x")) == (tmp_path / "x").resolve()


def test_enhance_cmd_pins_checkpoint_workdir(tmp_path):
    cmd = clean_voice.enhance_cmd("py", "in.wav", "out.wav", "M", tmp_path)
    assert cmd[1].endswith("cv_enhance.py")
    assert cmd[cmd.index("--workdir") + 1] == str(tmp_path)


def test_clean_missing_separator_venv_is_3(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "audio_separator", None)
    rc = clean_voice.main([str(tmp_path / "a.mp3"), "--clean-dir", str(tmp_path / "vc")])
    assert rc == 3


def test_clean_conflicting_flags_is_2(tmp_path):
    assert clean_voice.main(["a.mp3", "--no-enhance", "--enhance-only"]) == 2


# ── cổng: không còn dây rốn vào lớp bọc cũ của trạm ─────────────────────────────────────

# Chuỗi cấm dựng bằng chr() để chính file test này không tự khớp.
_OLD_MCP = "".join(map(chr, (109, 99, 112, 95, 115, 101, 114, 118, 101, 114)))          # tên module MCP cũ
_OLD_PROFILES = "".join(map(chr, (118, 111, 105, 99, 101, 95, 112, 114, 111, 102, 105, 108, 101, 115)))
_OLD_STATION = "".join(map(chr, (46, 116, 116, 115)))                                     # thư mục trạm cũ


def _py_files():
    for top in ("studio", "voice_studio"):
        yield from sorted((ROOT / top).rglob("*.py"))


_BANNED = [
    re.compile(rf"^\s*(import|from)\s+{_OLD_MCP}\b"),   # import module MCP cũ của trạm
    re.compile(rf"\b{_OLD_PROFILES}\b"),                # module profile cũ (tool list_… không khớp)
    re.compile(re.escape(_OLD_STATION) + r"[\\/]"),      # đường vào thư mục trạm cũ
]


@pytest.mark.parametrize("bad", _BANNED, ids=["import-mcp-cu", "module-profile-cu", "duong-tram-cu"])
def test_no_import_of_legacy_station_modules(bad):
    hits = [f"{p.relative_to(ROOT)}:{i}" for p in _py_files()
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if bad.search(line)]
    assert hits == [], hits


def test_no_sys_path_hacks_into_engine_dir():
    hits = [str(p.relative_to(ROOT)) for p in _py_files()
            if "sys.path.insert" in p.read_text(encoding="utf-8") and p.name != "_env.py"]
    assert hits == [], hits
