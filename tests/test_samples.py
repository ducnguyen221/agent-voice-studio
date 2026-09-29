"""Bài mẫu cố định (`samples/`): tồn tại, đúng kỳ vọng ghi ở README, khớp hợp đồng `speak`.

Bài mẫu là thứ người dùng chạy đầu tiên sau khi cài và là thứ `doctor` xác minh offline. Nó
chỉ có giá trị khi kết quả kỳ vọng là CỐ ĐỊNH và máy kiểm được — test này giữ điều đó.
"""
import json
import subprocess
import shutil
from pathlib import Path

import pytest

from conftest import last_json
from voice_studio import cli, doctor, samples, speak

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "samples"


def test_sample_files_exist_and_are_text_only():
    for name in ("README.md", samples.RAW, samples.SCRIPT, samples.EXPECTED):
        assert (S / name).is_file(), name
    assert not [p for p in S.rglob("*") if p.suffix.lower() in (".wav", ".mp3", ".pt", ".flac")]


def test_raw_sample_is_short_and_has_exactly_the_documented_traps():
    raw = (S / samples.RAW).read_text(encoding="utf-8").strip()
    assert 0 < len(raw) <= samples.MAX_CHARS
    assert sorted(k for k, _, _ in samples.traps(raw)) == ["gio", "ngay", "phien-ban", "ten-mien"]


def test_script_sample_has_no_trap_and_keeps_safe_numbers():
    script = (S / samples.SCRIPT).read_text(encoding="utf-8").strip()
    assert samples.traps(script) == []
    assert "2.436" in script and "15%" in script          # số an toàn: không sửa thừa


def test_readme_names_every_trap_key():
    text = (S / "README.md").read_text(encoding="utf-8")
    for key in samples.TRAPS:
        assert f"`{key}`" in text, key


@pytest.mark.parametrize("text,key", [
    ("họp lúc 9:05", "gio"),
    ("ngày 1/12/26", "ngay"),
    ("GLM-5.3 ra mắt", "phien-ban"),
    ("xem openai.com", "ten-mien"),
])
def test_trap_patterns_catch_their_target(text, key):
    assert key in {k for k, _, _ in samples.traps(text)}


@pytest.mark.parametrize("text", ["2.436 từ", "phiên bản 5.2", "15%", "14 giờ 30", "Z chấm AI"])
def test_trap_patterns_leave_safe_text_alone(text):
    assert samples.traps(text) == []


def test_expected_json_matches_speak_contract(station, fake_engine, tmp_path, capsys):
    expected = json.loads((S / samples.EXPECTED).read_text(encoding="utf-8"))
    assert set(expected) == set(speak.RESULT_KEYS)
    rc = cli.main(["speak", "--file", str(S / samples.SCRIPT), "--profile", "demo",
                   "--out", str(tmp_path / "cau-ngan.wav"), "--seed", "1234", "--json"])
    res = last_json(capsys.readouterr().out)
    assert rc == 0 and set(res) == set(expected)
    assert set(res["outputs"][0]) == set(expected["outputs"][0])
    assert set(res["timings"]) == set(expected["timings"])
    assert set(res["engine"]) == set(expected["engine"])


def test_doctor_verifies_samples_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(ROOT))
    # Bản clone của người chạy test có thể có workspace/ thật — trỏ trạm đi chỗ tạm.
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "st"))
    c = {x["name"]: x for x in doctor.run_checks()}["samples"]
    assert c["level"] == "ok", c


def test_doctor_samples_not_checked_without_repo():
    # conftest trỏ repo vào thư mục không tồn tại = bản cài wheel, không kèm samples/
    c = {x["name"]: x for x in doctor.run_checks()}["samples"]
    assert c["level"] == "not_checked"


def test_doctor_flags_a_drifted_sample(tmp_path, monkeypatch):
    shutil.copytree(S, tmp_path / "samples")
    (tmp_path / "samples" / samples.SCRIPT).write_text("Họp lúc 9:05.", encoding="utf-8")
    monkeypatch.setenv("VOICE_STUDIO_REPO", str(tmp_path))
    c = {x["name"]: x for x in doctor.run_checks()}["samples"]
    assert c["level"] == "warn" and "gio" in c["detail"]


@pytest.mark.skipif(not shutil.which("git") or not (ROOT / ".git").exists(), reason="cần bản clone git")
def test_audio_dropped_into_samples_stays_ignored():
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index",
                        "samples/cau-ngan.wav"])
    assert r.returncode == 0
