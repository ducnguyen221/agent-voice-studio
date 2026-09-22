"""Test `voice_studio.engine` bằng torch + omnivoice GIẢ — không tải weights, không cần GPU."""
import os
import sys
import types

import pytest

from voice_studio import engine


class _Flag:
    def __init__(self, value):
        self.value = value

    def is_available(self):
        return self.value


def fake_torch(cuda=False, mps=False):
    t = types.ModuleType("torch")
    t.float16, t.float32 = "fp16", "fp32"
    t.seeds = []
    t.manual_seed = lambda s: t.seeds.append(("cpu", s))
    t.cuda = types.SimpleNamespace(
        is_available=lambda: cuda,
        manual_seed_all=lambda s: t.seeds.append(("cuda", s)),
    )
    t.mps = types.SimpleNamespace(manual_seed=lambda s: t.seeds.append(("mps", s)))
    t.backends = types.SimpleNamespace(mps=_Flag(mps))
    return t


class FakeOmniVoice:
    loads = []

    def __init__(self, **kw):
        self.kw = kw
        self.sampling_rate = 24000
        self.generated = []

    @classmethod
    def from_pretrained(cls, model_id, **kw):
        cls.loads.append((model_id, kw))
        return cls(**kw)

    def generate(self, **kw):
        self.generated.append(kw)
        return [[0.0] * 10]


@pytest.fixture
def torch_env(monkeypatch):
    """Trả hàm cài torch giả theo cấu hình phần cứng mong muốn."""
    def install(cuda=False, mps=False):
        t = fake_torch(cuda=cuda, mps=mps)
        monkeypatch.setitem(sys.modules, "torch", t)
        ov = types.ModuleType("omnivoice")
        ov.OmniVoice = FakeOmniVoice
        monkeypatch.setitem(sys.modules, "omnivoice", ov)
        FakeOmniVoice.loads = []
        engine.unload()
        return t
    yield install
    engine.unload()


# ── chọn thiết bị: cuda → mps → cpu ────────────────────────────────────────────────────

def test_pick_cuda_first(torch_env):
    torch_env(cuda=True, mps=True)
    assert engine.pick_device() == "cuda:0"


def test_pick_mps_when_no_cuda(torch_env):
    torch_env(cuda=False, mps=True)
    assert engine.pick_device() == "mps"


def test_pick_cpu_last(torch_env):
    torch_env(cuda=False, mps=False)
    assert engine.pick_device() == "cpu"


def test_env_forces_device(torch_env, monkeypatch):
    torch_env(cuda=True, mps=False)
    monkeypatch.setenv("OMNIVOICE_DEVICE", "cpu")
    assert engine.pick_device() == "cpu"


def test_explicit_beats_env_and_cuda_normalized(torch_env, monkeypatch):
    torch_env(cuda=True)
    monkeypatch.setenv("OMNIVOICE_DEVICE", "cpu")
    assert engine.pick_device("cuda") == "cuda:0"
    assert engine.pick_device("cuda:1") == "cuda:1"


def test_forced_unavailable_device_fails_loudly(torch_env):
    torch_env(cuda=False, mps=False)
    with pytest.raises(RuntimeError, match="mps"):
        engine.pick_device("mps")
    with pytest.raises(ValueError):
        engine.pick_device("tpu")


# ── nạp model ──────────────────────────────────────────────────────────────────────────

def test_load_cuda_uses_fp16(torch_env):
    torch_env(cuda=True)
    m = engine.load()
    (model_id, kw), = FakeOmniVoice.loads
    assert model_id == engine.MODEL_ID
    assert kw == {"device_map": "cuda:0", "dtype": "fp16"}
    assert engine.load() is m and len(FakeOmniVoice.loads) == 1    # nạp một lần/tiến trình
    assert engine.loaded_device() == "cuda:0"


def test_load_mps_uses_fp16(torch_env):
    """F1 phương án A: MPS mặc định fp16 (RTF 1,77 vs 2,31) — [chưa kiểm trên Mac thật]."""
    torch_env(mps=True)
    engine.load()
    assert FakeOmniVoice.loads[0][1] == {"device_map": "mps", "dtype": "fp16"}


def test_load_mps_dtype_env_forces_fp32(torch_env, monkeypatch):
    torch_env(mps=True)
    monkeypatch.setenv("OMNIVOICE_DTYPE", "float32")
    engine.load()
    assert FakeOmniVoice.loads[0][1] == {"device_map": "mps", "dtype": "fp32"}


# ── OMNIVOICE_DTYPE ────────────────────────────────────────────────────────────────────

def test_dtype_defaults_per_device():
    assert engine.pick_dtype("cuda:0") == "float16"
    assert engine.pick_dtype("mps") == "float16"
    assert engine.pick_dtype("cpu") == "float32"


def test_dtype_env_overrides_and_auto_means_default(monkeypatch):
    monkeypatch.setenv("OMNIVOICE_DTYPE", "fp32")
    assert engine.pick_dtype("mps") == "float32"
    monkeypatch.setenv("OMNIVOICE_DTYPE", "half")
    assert engine.pick_dtype("cuda:0") == "float16"
    monkeypatch.setenv("OMNIVOICE_DTYPE", "auto")
    assert engine.pick_dtype("mps") == "float16"
    assert engine.pick_dtype("cpu") == "float32"


def test_dtype_argument_beats_env(monkeypatch):
    monkeypatch.setenv("OMNIVOICE_DTYPE", "float32")
    assert engine.pick_dtype("mps", "float16") == "float16"


def test_dtype_rejects_garbage_and_cpu_fp16(monkeypatch):
    with pytest.raises(ValueError, match="OMNIVOICE_DTYPE"):
        engine.pick_dtype("mps", "bfloat16")
    monkeypatch.setenv("OMNIVOICE_DTYPE", "float16")
    with pytest.raises(RuntimeError, match="CPU"):
        engine.pick_dtype("cpu")


def test_macos_sets_async_load_guard(monkeypatch):
    """Trên macOS, nạp song song + fp16 trên MPS segfault ⇒ phải tắt sẵn."""
    monkeypatch.setattr(engine.sys, "platform", "darwin")
    monkeypatch.delenv("HF_DEACTIVATE_ASYNC_LOAD", raising=False)
    monkeypatch.delenv("PYTORCH_ENABLE_MPS_FALLBACK", raising=False)
    engine.apply_offline_env()
    assert os.environ["HF_DEACTIVATE_ASYNC_LOAD"] == "1"
    assert os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] == "1"


def test_load_cpu_uses_fp32(torch_env):
    torch_env()
    engine.load()
    assert FakeOmniVoice.loads[0][1] == {"device_map": "cpu", "dtype": "fp32"}


def test_load_other_device_reloads(torch_env):
    torch_env(cuda=True)
    engine.load()
    engine.load("cpu")
    assert [kw["device_map"] for _, kw in FakeOmniVoice.loads] == ["cuda:0", "cpu"]


def test_offline_by_default(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    engine.apply_offline_env()
    assert os.environ["HF_HUB_OFFLINE"] == "1" and os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_online_opt_in(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.setenv("OMNIVOICE_ONLINE", "1")
    engine.apply_offline_env()
    assert "HF_HUB_OFFLINE" not in os.environ


# ── seed ───────────────────────────────────────────────────────────────────────────────

def test_seed_all_hits_every_available_backend(torch_env):
    t = torch_env(cuda=True, mps=True)
    engine.seed_all(7)
    assert t.seeds == [("cpu", 7), ("cuda", 7), ("mps", 7)]


def test_seed_all_cpu_only(torch_env):
    t = torch_env()
    engine.seed_all(3)
    assert t.seeds == [("cpu", 3)]


# ── synth ──────────────────────────────────────────────────────────────────────────────

def test_synth_with_prompt_object(torch_env):
    t = torch_env()
    prompt = types.SimpleNamespace(tag="built-prompt")     # prompt đã dựng, không phải tên
    wav, sr = engine.synth("xin chào", prompt, speed=1.1, seed=5)
    assert sr == 24000 and len(wav) == 10
    kw = engine.load().generated[-1]
    assert kw == {"text": "xin chào", "language": "Vietnamese",
                  "voice_clone_prompt": prompt, "speed": 1.1}
    assert ("cpu", 5) in t.seeds


def test_synth_profile_name_resolves_prompt(torch_env, monkeypatch):
    torch_env()
    from voice_studio import profiles
    monkeypatch.setattr(profiles, "get_clone_prompt", lambda model, name=None: f"P:{name}")
    engine.synth("a", "narrator")
    assert engine.load().generated[-1]["voice_clone_prompt"] == "P:narrator"


def test_synth_instruct_mode(torch_env):
    torch_env()
    engine.synth("a", None, instruct="female, young adult")
    kw = engine.load().generated[-1]
    assert kw["instruct"] == "female, young adult" and "voice_clone_prompt" not in kw


def test_synth_without_any_voice_refuses_random_speaker(torch_env, monkeypatch):
    torch_env()
    from voice_studio import profiles
    monkeypatch.setattr(profiles, "get_clone_prompt", lambda model, name=None: None)
    with pytest.raises(profiles.ProfileError):
        engine.synth("a")


# ── chuẩn hoá âm lượng ─────────────────────────────────────────────────────────────────

def test_normalize_rms_hits_target_and_never_clips():
    np = pytest.importorskip("numpy")
    a = (0.01 * np.sin(np.linspace(0, 200, 24000))).astype("float32")
    out = engine.normalize(a, target_db=-20.0)
    rms_db = 20 * np.log10(np.sqrt((out ** 2).mean()))
    assert abs(rms_db - (-20.0)) < 0.5
    loud = engine.normalize(a, target_db=0.0)
    assert float(np.max(np.abs(loud))) <= 0.97 + 1e-6
    assert out.dtype == np.float32


def test_normalize_leaves_silence_alone():
    np = pytest.importorskip("numpy")
    a = np.zeros(1000, dtype="float32")
    assert engine.normalize(a) is a


def test_api_version_is_semver():
    import voice_studio
    parts = voice_studio.API_VERSION.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)
    assert engine.API_VERSION == voice_studio.API_VERSION
