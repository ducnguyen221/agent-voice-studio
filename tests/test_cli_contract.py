"""Hợp đồng CLI giữa các trạm (§2.4): `speak` / `narrate` với engine GIẢ.

Thứ được khoá: mã thoát 0/1/2/3 đúng nghĩa, file thật nằm ở `--out`, stdout kết thúc bằng
ĐÚNG MỘT dòng JSON hợp lệ (log người đọc đi stderr), lỗi cũng ra JSON khi có `--json`.
Hai test cuối chạy `python -m voice_studio` thành tiến trình thật — đúng cách pipeline gọi.
"""
import json
import os
import subprocess
import sys

import pytest

from conftest import last_json
from voice_studio import av, cli, engine

pytest.importorskip("numpy")
pytest.importorskip("soundfile")


def run(capsys, *argv):
    rc = cli.main(list(argv))
    out, err = capsys.readouterr()
    return rc, out, err


# ── speak ──────────────────────────────────────────────────────────────────────────────

def test_speak_ok_writes_file_and_one_json_line(station, fake_engine, tmp_path, capsys):
    out = tmp_path / "ra" / "a.wav"
    rc, stdout, stderr = run(capsys, "speak", "--text", "Xin chào. Câu thứ hai.",
                             "--profile", "demo", "--out", str(out), "--json")
    assert rc == 0
    assert out.is_file() and out.stat().st_size > 0
    assert len([ln for ln in stdout.splitlines() if ln.strip()]) == 1, "log lọt vào stdout"
    res = last_json(stdout)
    assert res["ok"] is True
    assert res["profile"] == "demo"
    assert res["outputs"][0]["kind"] == "audio"
    assert os.path.samefile(res["outputs"][0]["path"], out)
    assert res["outputs"][0]["duration"] > 0
    assert set(res["timings"]) == {"load", "synth", "total"}
    assert res["engine"]["voice_studio"]
    assert "[speak]" in stderr
    # hai câu ⇒ hai lần generate, cùng một clone prompt (giọng nhất quán)
    prompts = {id(c.get("voice_clone_prompt")) for c in fake_engine.calls}
    assert len(fake_engine.calls) == 2 and len(prompts) == 1


def test_speak_uses_default_profile_when_not_named(station, fake_engine, tmp_path, capsys):
    (station / "omnivoice" / "voices" / "_default.txt").write_text("other", encoding="utf-8")
    rc, stdout, _ = run(capsys, "speak", "--text", "Xin chào", "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 0 and last_json(stdout)["profile"] == "other"


def test_speak_from_file_and_normalize(station, fake_engine, tmp_path, capsys):
    src = tmp_path / "bai.txt"
    src.write_text("Một câu trong file.", encoding="utf-8")
    rc, stdout, _ = run(capsys, "speak", "--file", str(src), "--profile", "demo",
                        "--out", str(tmp_path / "a.wav"), "--normalize", "--json")
    assert rc == 0 and last_json(stdout)["ok"] is True


def test_speak_no_profile_no_default_is_contract_error(station, fake_engine, tmp_path, capsys):
    """Kho có 2 profile, không mặc định, không --profile ⇒ mã 2, không bao giờ lùi giọng ngẫu nhiên."""
    rc, stdout, stderr = run(capsys, "speak", "--text", "x", "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 2
    res = last_json(stdout)
    assert res == {"ok": False, "code": 2, "error": res["error"]}
    assert "mặc định" in res["error"]
    assert not (tmp_path / "a.wav").exists()
    assert fake_engine.calls == []


def test_speak_unknown_profile_is_contract_error(station, fake_engine, tmp_path, capsys):
    rc, stdout, _ = run(capsys, "speak", "--text", "x", "--profile", "khong-co",
                        "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 2 and last_json(stdout)["code"] == 2


def test_speak_empty_text_is_contract_error(station, fake_engine, tmp_path, capsys):
    rc, stdout, _ = run(capsys, "speak", "--text", "   ", "--profile", "demo",
                        "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 2 and last_json(stdout)["code"] == 2


def test_speak_bad_args_still_emit_json(capsys):
    rc, stdout, _ = run(capsys, "speak", "--text", "x", "--json")      # thiếu --out
    assert rc == 2
    assert last_json(stdout) == {"ok": False, "code": 2, "error": last_json(stdout)["error"]}


def test_speak_missing_station_is_3(tmp_path, monkeypatch, fake_engine, capsys):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "khong-ton-tai"))
    rc, stdout, _ = run(capsys, "speak", "--text", "x", "--profile", "demo",
                        "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 3
    res = last_json(stdout)
    assert res["ok"] is False and res["code"] == 3 and "init" in res["error"]


def test_speak_engine_not_installed_is_3(station, tmp_path, monkeypatch, capsys):
    """Venv không có torch/omnivoice = trạm chưa đủ ⇒ mã 3 (cài tiếp), không phải 1."""
    monkeypatch.setitem(sys.modules, "torch", None)       # import torch ⇒ ImportError
    engine.unload()
    rc, stdout, _ = run(capsys, "speak", "--text", "x", "--profile", "demo",
                        "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 3 and last_json(stdout)["code"] == 3


def test_speak_engine_failure_is_1(station, fake_engine, tmp_path, capsys):
    fake_engine.fail = True
    rc, stdout, stderr = run(capsys, "speak", "--text", "x", "--profile", "demo",
                             "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 1
    res = last_json(stdout)
    assert res["code"] == 1 and "out of memory" in res["error"]
    assert "Traceback" in stderr            # lỗi engine: giữ dấu vết cho người sửa


def test_speak_without_json_prints_nothing_on_stdout(station, fake_engine, tmp_path, capsys):
    rc, stdout, _ = run(capsys, "speak", "--text", "x", "--profile", "demo", "--out", str(tmp_path / "a.wav"))
    assert rc == 0 and stdout == ""


def test_speak_instruct_mode_needs_no_voice_store(tmp_path, monkeypatch, fake_engine, capsys):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "trong"))
    rc, stdout, _ = run(capsys, "speak", "--text", "x", "--instruct", "male, low pitch",
                        "--out", str(tmp_path / "a.wav"), "--json")
    assert rc == 0 and last_json(stdout)["profile"] is None
    assert fake_engine.calls[0]["instruct"] == "male, low pitch"


def test_speak_markers_are_never_spoken(station, fake_engine, tmp_path, capsys):
    rc, _, _ = run(capsys, "speak", "--text", "[hao-hung] Con số này gấp ba.", "--profile", "demo",
                   "--out", str(tmp_path / "a.wav"))
    assert rc == 0
    assert all("[hao-hung]" not in c["text"] for c in fake_engine.calls)


# ── narrate ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_mux(monkeypatch):
    calls = []

    def mux(video, voice, out, mode="fit", bgm=None, volume=None):
        assert os.path.isfile(voice), "giọng tạm phải tồn tại lúc ghép"
        calls.append({"video": video, "voice": voice, "out": out, "mode": mode, "bgm": bgm,
                      "volume": volume})
        with open(out, "wb") as f:
            f.write(b"mp4")
        return out
    monkeypatch.setattr(av, "mux", mux)
    monkeypatch.setattr(av, "video_duration", lambda p: 3.0)
    return calls


def test_narrate_ok(station, fake_engine, fake_mux, tmp_path, capsys):
    video = tmp_path / "cam.mp4"
    video.write_bytes(b"v")
    out = tmp_path / "ra" / "final.mp4"
    rc, stdout, _ = run(capsys, "narrate", "--video", str(video), "--text", "Xin chào.",
                        "--profile", "demo", "--out", str(out), "--bgm", "none", "--json")
    assert rc == 0 and out.is_file()
    res = last_json(stdout)
    assert res["outputs"][0]["kind"] == "video"
    assert res["video_duration"] == 3.0 and res["voice_duration"] > 0
    assert fake_mux[0]["bgm"] is False and fake_mux[0]["mode"] == "fit"
    assert not os.path.exists(str(out) + ".__voice.wav"), "wav tạm bị bỏ lại"


def test_narrate_bgm_style_passed_through(station, fake_engine, fake_mux, tmp_path, capsys):
    video = tmp_path / "cam.mp4"
    video.write_bytes(b"v")
    rc, _, _ = run(capsys, "narrate", "--video", str(video), "--text", "x", "--profile", "demo",
                   "--out", str(tmp_path / "f.mp4"), "--bgm", "neutral", "--bgm-volume", "0.2",
                   "--mode", "shortest")
    assert rc == 0
    assert fake_mux[0]["bgm"] == "neutral" and fake_mux[0]["volume"] == 0.2
    assert fake_mux[0]["mode"] == "shortest"


def test_narrate_missing_video_is_2(station, fake_engine, tmp_path, capsys):
    rc, stdout, _ = run(capsys, "narrate", "--video", str(tmp_path / "khong.mp4"), "--text", "x",
                        "--profile", "demo", "--out", str(tmp_path / "f.mp4"), "--json")
    assert rc == 2 and last_json(stdout)["code"] == 2


# ── tiến trình thật: đúng cách pipeline gọi ─────────────────────────────────────────────

FAKE_TORCH = '''
import types
float16, float32 = "fp16", "fp32"
def manual_seed(s): pass
cuda = types.SimpleNamespace(is_available=lambda: False, manual_seed_all=lambda s: None)
mps = types.SimpleNamespace(manual_seed=lambda s: None)
backends = types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False))
'''
FAKE_OMNIVOICE = '''
import numpy as np
class _P:
    def save(self, p): open(p, "wb").write(b"p")
class OmniVoice:
    sampling_rate = 24000
    @classmethod
    def from_pretrained(cls, *a, **k): return cls()
    def create_voice_clone_prompt(self, **k): return _P()
    def generate(self, **k):
        print("log rác của engine lọt ra stdout")
        return [np.full(2400, 0.1, dtype="float32")]
'''


def _subprocess_env(tmp_path, station_dir, fakes=True):
    env = {k: v for k, v in os.environ.items() if k not in ("VOICE_STATION", "OMNIVOICE_DIR")}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = [root]
    if fakes:
        fk = tmp_path / "fakes"
        (fk / "omnivoice").mkdir(parents=True, exist_ok=True)
        (fk / "torch.py").write_text(FAKE_TORCH, encoding="utf-8")
        (fk / "omnivoice" / "__init__.py").write_text(FAKE_OMNIVOICE, encoding="utf-8")
        paths.insert(0, str(fk))
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["VOICE_STATION"] = str(station_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_process_speak_exit_0_and_json_is_last_stdout_line(station, tmp_path):
    out = tmp_path / "p.wav"
    r = subprocess.run([sys.executable, "-m", "voice_studio", "speak", "--text", "Xin chào.",
                        "--profile", "demo", "--out", str(out), "--json"],
                       capture_output=True, text=True, encoding="utf-8",
                       env=_subprocess_env(tmp_path, station), timeout=120)
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    res = last_json(r.stdout)            # log rác phía trước không làm hỏng việc parse
    assert res["ok"] is True and os.path.samefile(res["outputs"][0]["path"], out)


def test_process_speak_exit_3_without_station(tmp_path):
    r = subprocess.run([sys.executable, "-m", "voice_studio", "speak", "--text", "x",
                        "--profile", "demo", "--out", str(tmp_path / "p.wav"), "--json"],
                       capture_output=True, text=True, encoding="utf-8",
                       env=_subprocess_env(tmp_path, tmp_path / "khong-co-tram"), timeout=120)
    assert r.returncode == 3
    assert json.loads(r.stdout.strip().splitlines()[-1])["code"] == 3
