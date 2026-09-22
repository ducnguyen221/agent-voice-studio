"""`extras/musicgen/` — công cụ tuỳ chọn sinh nhạc nền. Test KHÔNG nạp torch/transformers,
KHÔNG tải model: chỉ cú pháp, `--help`, bảng style, và phần ghi `bgm-library.json`.
"""
import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MG = ROOT / "extras" / "musicgen"


def load(name):
    spec = importlib.util.spec_from_file_location(f"mg_{name}", MG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", ["gen", "gen_pack"])
def test_parses_and_imports_without_torch(name, monkeypatch):
    ast.parse((MG / f"{name}.py").read_text(encoding="utf-8"))
    monkeypatch.setitem(sys.modules, "torch", None)          # import torch ⇒ ImportError
    monkeypatch.setitem(sys.modules, "transformers", None)
    load(name)                                                 # nạp module không đụng torch


@pytest.mark.parametrize("name", ["gen", "gen_pack"])
def test_help_runs_without_engine(name):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT))
    r = subprocess.run([sys.executable, str(MG / f"{name}.py"), "--help"], capture_output=True,
                       text=True, encoding="utf-8", env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "usage" in r.stdout.lower()


def test_styles_table_is_valid():
    data = json.loads((MG / "styles.json").read_text(encoding="utf-8"))
    names = [s["name"] for s in data["styles"]]
    assert len(names) == len(set(names)) and len(names) >= 3
    for s in data["styles"]:
        assert s["prompt"].strip() and "instrumental" in s["prompt"]
        assert s["name"] == s["name"].lower() and " " not in s["name"]


def test_default_model_is_large_and_ids_are_public():
    gen = load("gen")
    assert gen.MODELS["large"] == "facebook/musicgen-large"
    assert gen.DEFAULT_MODEL == "large"


def test_update_library_merges_without_clobbering(tmp_path):
    pack = load("gen_pack")
    lib = tmp_path / "bgm-library.json"
    lib.write_text(json.dumps({"volume": 0.2, "default": "mine",
                               "styles": [{"name": "mine", "mood": "của tôi"}]}), encoding="utf-8")
    pack.update_library(str(tmp_path), [{"name": "mine", "mood": "mới"},
                                        {"name": "tech-pulse", "mood": "nhịp"}])
    data = json.loads(lib.read_text(encoding="utf-8"))
    assert data["volume"] == 0.2 and data["default"] == "mine"
    by = {s["name"]: s for s in data["styles"]}
    assert by["mine"]["mood"] == "của tôi"                    # không đè mô tả người dùng
    assert "tech-pulse" in by


def test_update_library_creates_file(tmp_path):
    pack = load("gen_pack")
    pack.update_library(str(tmp_path), [{"name": "a", "mood": "x"}])
    data = json.loads((tmp_path / "bgm-library.json").read_text(encoding="utf-8"))
    assert data["default"] == "a" and data["volume"] == 0.10
