"""Test `voice_studio.profiles` với một thư mục `voices/` giả (file rỗng, không audio thật)."""
import os
import sys
import time
import types

import pytest

from voice_studio import profiles


def _make_voices(root, names):
    root.mkdir(parents=True, exist_ok=True)
    for n in names:
        (root / f"{n}.wav").write_bytes(b"")
        (root / f"{n}.txt").write_text(f"transcript {n}", encoding="utf-8")
    return root


@pytest.fixture
def voices(tmp_path, monkeypatch):
    d = _make_voices(tmp_path / "voices", ["alpha", "beta"])
    monkeypatch.setenv("VOICES_DIR", str(d))
    profiles.clear_cache()
    return d


class FakePrompt:
    def __init__(self, src):
        self.src = src
        self.saved_to = []

    def save(self, path):
        self.saved_to.append(path)
        with open(path, "wb") as f:
            f.write(b"prompt")


class FakeModel:
    sampling_rate = 24000

    def __init__(self):
        self.calls = []

    def create_voice_clone_prompt(self, ref_audio, ref_text):
        self.calls.append((ref_audio, ref_text))
        return FakePrompt(ref_audio)


# ── thư mục giọng ──────────────────────────────────────────────────────────────────────

def test_voices_dir_from_voices_dir_env(voices):
    assert profiles.voices_dir() == str(voices)


def test_voices_dir_from_station(tmp_path, monkeypatch):
    st = tmp_path / "station"
    monkeypatch.setenv("VOICE_STATION", str(st))
    assert profiles.voices_dir() == str(st / "omnivoice" / "voices")


def test_voices_dir_from_legacy_engine_dir(tmp_path, monkeypatch):
    eng = tmp_path / "legacy" / "omnivoice"
    monkeypatch.setenv("OMNIVOICE_DIR", str(eng))
    assert profiles.voices_dir() == str(eng / "voices")


def test_voices_dir_prefers_new_name(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICE_STATION", str(tmp_path / "new"))
    monkeypatch.setenv("OMNIVOICE_DIR", str(tmp_path / "old" / "omnivoice"))
    assert profiles.voices_dir() == str(tmp_path / "new" / "omnivoice" / "voices")


def test_module_attribute_voices_dir_is_live(voices):
    # shim cũ đọc `vp.VOICES_DIR` — phải phản ánh cấu hình hiện hành, không đóng băng lúc import
    assert profiles.VOICES_DIR == str(voices)


# ── liệt kê + mặc định ─────────────────────────────────────────────────────────────────

def test_list_profiles_skips_underscore_and_non_wav(voices):
    (voices / "_example.wav").write_bytes(b"")
    (voices / "notes.txt").write_text("x", encoding="utf-8")
    assert profiles.list_profiles() == ["alpha", "beta"]


def test_list_profiles_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICES_DIR", str(tmp_path / "nope"))
    assert profiles.list_profiles() == []


def test_default_branch1_default_file(voices, monkeypatch):
    (voices / "_default.txt").write_text("beta\n", encoding="utf-8")
    monkeypatch.setenv("VOICE_DEFAULT_PROFILE", "alpha")  # file thắng biến
    assert profiles.get_default() == "beta"


def test_default_branch2_env(voices, monkeypatch):
    monkeypatch.setenv("VOICE_DEFAULT_PROFILE", "alpha")
    assert profiles.get_default() == "alpha"


def test_default_branch3_single_profile(tmp_path, monkeypatch):
    d = _make_voices(tmp_path / "solo", ["only"])
    monkeypatch.setenv("VOICES_DIR", str(d))
    assert profiles.get_default() == "only"


def test_default_ambiguous_returns_none(voices):
    assert profiles.get_default() is None


def test_default_file_pointing_to_missing_profile_falls_through(voices, monkeypatch):
    (voices / "_default.txt").write_text("ghost", encoding="utf-8")
    monkeypatch.setenv("VOICE_DEFAULT_PROFILE", "alpha")
    assert profiles.get_default() == "alpha"


def test_ensure_default_raises_when_ambiguous(voices):
    with pytest.raises(profiles.ProfileError) as e:
        profiles.ensure_default()
    # thông báo phải chỉ cách sửa, và là FileNotFoundError để code cũ bắt được
    assert isinstance(e.value, FileNotFoundError)
    assert "VOICE_DEFAULT_PROFILE" in str(e.value)


def test_ensure_default_raises_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("VOICES_DIR", str(tmp_path / "empty"))
    with pytest.raises(profiles.ProfileError):
        profiles.ensure_default()


def test_ensure_default_returns_named_or_default(voices, monkeypatch):
    assert profiles.ensure_default(name="beta") == "beta"
    monkeypatch.setenv("VOICE_DEFAULT_PROFILE", "alpha")
    assert profiles.ensure_default() == "alpha"


def test_set_default_writes_file_and_rejects_unknown(voices):
    profiles.set_default("alpha")
    assert (voices / "_default.txt").read_text(encoding="utf-8") == "alpha"
    with pytest.raises(FileNotFoundError):
        profiles.set_default("ghost")


# ── clone prompt + cache ───────────────────────────────────────────────────────────────

def test_get_clone_prompt_builds_and_caches_beside_profile(voices):
    m = FakeModel()
    p1 = profiles.get_clone_prompt(m, "alpha")
    p2 = profiles.get_clone_prompt(m, "alpha")
    assert p1 is p2 and len(m.calls) == 1                     # cache RAM
    assert m.calls[0] == (str(voices / "alpha.wav"), "transcript alpha")
    assert p1.saved_to == [str(voices / "alpha.prompt.pt")]   # cache đĩa cạnh profile


def test_get_clone_prompt_uses_default_and_none_when_ambiguous(voices, monkeypatch):
    assert profiles.get_clone_prompt(FakeModel()) is None
    monkeypatch.setenv("VOICE_DEFAULT_PROFILE", "beta")
    assert profiles.get_clone_prompt(FakeModel()).src == str(voices / "beta.wav")


def test_get_clone_prompt_missing_profile(voices):
    with pytest.raises(FileNotFoundError):
        profiles.get_clone_prompt(FakeModel(), "ghost")


def _install_fake_voiceclone(monkeypatch, loaded):
    class VoiceClonePrompt:
        @staticmethod
        def load(path):
            loaded.append(path)
            return "FROM-DISK"

    mod = types.ModuleType("omnivoice.models.omnivoice")
    mod.VoiceClonePrompt = VoiceClonePrompt
    monkeypatch.setitem(sys.modules, "omnivoice", types.ModuleType("omnivoice"))
    monkeypatch.setitem(sys.modules, "omnivoice.models", types.ModuleType("omnivoice.models"))
    monkeypatch.setitem(sys.modules, "omnivoice.models.omnivoice", mod)


def test_disk_cache_is_used_when_fresh(voices, monkeypatch):
    loaded = []
    _install_fake_voiceclone(monkeypatch, loaded)
    pt = voices / "alpha.prompt.pt"
    pt.write_bytes(b"x")
    future = time.time() + 60
    os.utime(pt, (future, future))
    m = FakeModel()
    assert profiles.get_clone_prompt(m, "alpha") == "FROM-DISK"
    assert m.calls == [] and loaded == [str(pt)]


def test_disk_cache_ignored_when_stale(voices, monkeypatch):
    loaded = []
    _install_fake_voiceclone(monkeypatch, loaded)
    pt = voices / "alpha.prompt.pt"
    pt.write_bytes(b"x")
    past = time.time() - 3600
    os.utime(pt, (past, past))
    m = FakeModel()
    profiles.get_clone_prompt(m, "alpha")
    assert loaded == [] and len(m.calls) == 1                 # dựng lại, không dùng cache cũ


def test_save_profile_from_instruct_drops_cache(voices, monkeypatch):
    sf = pytest.importorskip("soundfile")
    np = pytest.importorskip("numpy")

    class GenModel(FakeModel):
        def generate(self, text, language, instruct):
            return [np.zeros(2400, dtype="float32")]

    (voices / "gamma.prompt.pt").write_bytes(b"old")
    profiles.save_profile_from_instruct(GenModel(), "female", "gamma", set_as_default=False)
    assert (voices / "gamma.wav").exists()
    assert not (voices / "gamma.prompt.pt").exists()
    assert sf.info(str(voices / "gamma.wav")).samplerate == 24000


# ── cổng danh tính: không tên profile cá nhân nào nằm cứng trong mã ───────────────────

def test_no_hardcoded_personal_default():
    src = open(profiles.__file__, encoding="utf-8").read()
    banned = ["".join(map(chr, c)) for c in (
        (109, 121, 45, 118, 111, 105, 99, 101),     # tên profile cá nhân cũ
        (97, 45, 116, 117, 110),                    # tên profile truyện cũ
    )]
    for word in banned:
        assert word not in src
    assert "PREFERRED_DEFAULT" not in src
