"""Cổng của repo: `.gitignore` khoá dữ liệu trạm (F17.4), cây mẫu `templates/workspace/` khớp mã,
`pyproject.toml` khai đúng entry point và không kéo engine nặng vào phụ thuộc lõi.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from voice_studio import API_VERSION, __version__, bgm

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
