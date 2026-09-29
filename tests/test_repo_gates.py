"""Cổng của repo: `.gitignore` khoá dữ liệu trạm (F17.4), cây mẫu `templates/workspace/` khớp mã,
`pyproject.toml` khai đúng entry point và không kéo engine nặng vào phụ thuộc lõi.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from voice_studio import API_VERSION, __version__, _env, bgm

ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = ROOT / ".gitignore"


def _lines():
    return {ln.strip() for ln in GITIGNORE.read_text(encoding="utf-8").splitlines()}


# Xoá BẤT KỲ dòng nào dưới đây là test đỏ — kể cả khi một mẫu rộng hơn tình cờ vẫn chặn.
REQUIRED = ["/workspace/", ".env", ".env.*", "!.env.example", "studio.local.json",
            "*.wav", "*.mp3", "*.pt", "*.onnx", "*.safetensors", "voices/", "out/"]


@pytest.mark.parametrize("line", REQUIRED)
def test_gitignore_keeps_required_line(line):
    assert line in _lines(), f".gitignore thiếu dòng bắt buộc: {line}"


def _in_git():
    return shutil.which("git") and (ROOT / ".git").exists()


@pytest.mark.skipif(not _in_git(), reason="cần bản clone git")
@pytest.mark.parametrize("path,ignored", [
    ("workspace/omnivoice/voices/a.txt", True),
    (".env", True),
    (".env.local", True),
    (".env.example", False),
    ("studio.local.json", True),
    ("templates/workspace/omnivoice/voices/_example/README.md", False),
    ("templates/workspace/out/README.md", False),
    ("templates/workspace/omnivoice/voices/a.wav", True),
    ("templates/workspace/omnivoice/voices/a.prompt.pt", True),
    ("templates/workspace/out/a.mp3", True),
    ("some/where/voices/a.txt", True),
])
def test_git_really_ignores(path, ignored):
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", path])
    assert (r.returncode == 0) is ignored, path


# ── .env.example: khuôn biến của chế độ embedded ───────────────────────────────────────
#
# `embedded` hứa "clone là chạy": cây mẫu sẵn trong repo, và `<repo>/.env` được `init` dọn
# sẵn từ file này. Một biến mà MÃ đọc nhưng khuôn không khai là một biến không ai biết mình
# phải điền — và người dùng chỉ phát hiện ra lúc lệnh nổ giữa chừng.

ENV_EXAMPLE = ROOT / ".env.example"
# Tên biến mà mã thật sự đọc qua `_env.env("…")`. Bắt theo chuỗi literal có chủ đích: đọc qua
# một biến trung gian là biến mất khỏi cổng này, nên đừng làm thế.
ENV_READ_RE = re.compile(r'\benv\(\s*"([A-Z][A-Z0-9_]*)"')


def _example_names():
    out = set()
    for ln in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and "=" in s:
            out.add(s.split("=", 1)[0].strip())
    return out


def _names_code_reads():
    out = set()
    for d in ("voice_studio", "studio"):
        for p in (ROOT / d).rglob("*.py"):
            out |= set(ENV_READ_RE.findall(p.read_text(encoding="utf-8")))
    return out - set(_env._LEGACY.values())      # tên cũ: đọc được, nhưng đừng dạy ai điền


def test_env_example_exists_and_holds_no_values():
    assert ENV_EXAMPLE.is_file(), "chế độ embedded cần .env.example để `init` chép thành .env"
    for ln in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            assert s.endswith("="), f"khuôn không được mang giá trị: {s!r}"


def test_env_example_declares_every_variable_the_code_reads():
    thieu = _names_code_reads() - _example_names()
    assert not thieu, f".env.example thiếu biến mã đang đọc: {sorted(thieu)}"


def test_env_example_declares_nothing_the_code_never_reads_without_saying_why():
    """Biến chỉ tiến trình KHÁC đọc (venv engine, thư viện HF) phải được đánh dấu rõ.

    Không có luật này thì khuôn phình dần bằng những dòng không ai đọc, và người dùng điền
    xong vẫn không có gì đổi — kiểu hỏng khó chịu nhất vì nó im lặng.
    """
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    thua = _example_names() - _names_code_reads()
    assert thua, "cổng này vô nghĩa nếu không còn biến nào ngoài tầm _env.env()"
    assert "[MÔI TRƯỜNG THẬT]" in text, "phải có chú thích cho biến tiến trình khác đọc"


# ── cây mẫu ────────────────────────────────────────────────────────────────────────────

T = ROOT / "templates" / "workspace"


def test_template_tree_complete():
    for rel in ("README.md", "station.json", "omnivoice/voices/_example/README.md",
                "omnivoice/voices/_example/sample.txt", "assets/bgm/README.md",
                "assets/bgm/bgm-library.json", "out/README.md", "cache/README.md"):
        assert (T / rel).is_file(), rel
    assert not [p for p in T.rglob("*") if p.suffix.lower() in (".wav", ".mp3", ".pt")]


def test_template_bgm_matches_code():
    assert json.loads((T / "assets/bgm/bgm-library.json").read_text(encoding="utf-8")) == \
        bgm.SAMPLE_LIBRARY
    assert (T / "assets/bgm/README.md").read_text(encoding="utf-8") == bgm.README_TEXT


def test_template_station_json_contract():
    info = json.loads((T / "station.json").read_text(encoding="utf-8"))
    assert info["contract"] == API_VERSION
    for key in ("device", "default_profile", "venv", "engine_dir", "bgm_dir"):
        assert key in info


# ── pyproject ──────────────────────────────────────────────────────────────────────────

tomllib = pytest.importorskip("tomllib") if sys.version_info >= (3, 11) else None


@pytest.mark.skipif(tomllib is None, reason="cần Python ≥ 3.11 để đọc TOML")
def test_pyproject_entry_point_and_version():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    proj = data["project"]
    assert proj["scripts"]["voice-studio"] == "voice_studio.cli:main"
    assert proj["version"] == __version__
    core = " ".join(proj.get("dependencies", [])).lower()
    for heavy in ("torch", "omnivoice", "gradio", "transformers"):
        assert heavy not in core, f"{heavy} phải là extras, không vào phụ thuộc lõi"
    extras = proj["optional-dependencies"]
    for name in ("engine", "mcp", "ui", "clone", "test"):
        assert name in extras
    assert any("omnivoice==0.2.1" in d for d in extras["engine"])


# ── transformers: ghim theo KHOẢNG đã đo, không một số cứng ────────────────────────────
# Các bản đã chạy thật với engine (docs/troubleshooting.md, mục Apple Silicon). Thêm bản mới vào
# đây chỉ khi đã đo trên máy thật.
TRANSFORMERS_MEASURED = ("5.10.2", "5.17.0")


@pytest.mark.skipif(tomllib is None, reason="cần Python ≥ 3.11 để đọc TOML")
def test_engine_pins_transformers_to_the_doctor_range():
    from voice_studio import doctor
    engine = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"]["optional-dependencies"]["engine"]
    pins = [d for d in engine if d.replace(" ", "").lower().startswith("transformers")]
    assert len(pins) == 1, "phần phụ engine phải ghim transformers đúng một lần"
    spec = pins[0].replace(" ", "")[len("transformers"):]
    # Một chỗ nói khoảng cho pip, một chỗ cho doctor — lệch là doctor khen/chê sai bản.
    assert spec == doctor.TRANSFORMERS_TESTED
    assert "==" not in spec and ">=" in spec and "<" in spec.replace(">=", ""), \
        "ghim theo khoảng có cận dưới và cận trên, không ghim cứng một số"


@pytest.mark.parametrize("version", TRANSFORMERS_MEASURED)
def test_every_measured_transformers_is_inside_the_range(version):
    from voice_studio import doctor
    assert doctor.in_range(version, doctor.TRANSFORMERS_TESTED)


@pytest.mark.parametrize("version,inside", [
    ("5.10.1", False), ("5.10.2", True), ("5.17.9", True), ("5.18.0", False),
    ("5.17.0.dev0", True), ("5.12.0+local", True), ("6.0", False), ("4.57.1", False)])
def test_in_range_bounds(version, inside):
    from voice_studio import doctor
    assert doctor.in_range(version, ">=5.10.2,<5.18") is inside


def test_doctor_warns_outside_measured_transformers():
    from voice_studio import doctor
    ok = doctor.transformers_check("5.17.0")
    assert ok["level"] == "ok" and "5.17.0" in ok["detail"]
    bad = doctor.transformers_check("5.20.1")
    # Ngoài khoảng là CẢNH BÁO, không chặn: chưa ai đo không có nghĩa là hỏng.
    assert bad["level"] == "warn" and "[engine]" in bad["hint"]
