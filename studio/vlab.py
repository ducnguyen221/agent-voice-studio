"""
vlab.py — lõi voicelab: đọc manifest profile, cắt text theo marker, tổng hợp và nối.

Một hàm `synth()` phục vụ CẢ HAI nhánh:
  - profile KHÔNG có manifest (lối cũ, vd demo-voice) -> một giọng duy nhất,
    marker trong text bị gỡ bỏ (không bao giờ được đọc thành tiếng).
  - profile CÓ manifest (vd narrator) -> mỗi marker đổi sang clip mẫu tương ứng.

13 thẻ phi ngôn ngữ gốc của OmniVoice luôn được GIỮ NGUYÊN trong text để engine tự xử.
"""
import json
import os
import re

from _env import bootstrap
# Engine sống trên máy người dùng, không nằm trong repo -> không được đoán vị trí.
_ENGINE, VOICES_DIR = bootstrap()

# 13 thẻ gốc — engine tự hiểu, không phải marker của mình.
NATIVE_TAGS = {
    "laughter", "sigh", "confirmation-en", "question-en", "question-ah",
    "question-oh", "question-ei", "question-yi", "surprise-ah", "surprise-oh",
    "surprise-wa", "surprise-yo", "dissatisfaction-hnn",
}

_BRACKET = re.compile(r"\[([a-z0-9][a-z0-9\-]*)\]", re.IGNORECASE)

# Cắt câu: sau . ! ? … và khoảng trắng. Không cắt ở dấu chấm trong số (1.250.000).
_SENT = re.compile(r"(?<=[.!?…])\s+(?=[^\s])")


def split_sentences(chunk):
    """Cắt một nhịp thành câu. Tổng hợp từng câu — giống các pipeline đọc bản tin,
    và tránh nuốt nguyên đoạn dài vào một lần generate()."""
    out = [s.strip() for s in _SENT.split(chunk) if s.strip()]
    return out or ([chunk.strip()] if chunk.strip() else [])

CROSSFADE = 0.030   # giây, làm mềm mối nối giữa hai nhịp
GAP_MARKER = 0.120  # giây im lặng khi ĐỔI marker
GAP_SAME = 0.060    # giây im lặng giữa hai nhịp cùng marker

# OmniVoice KHÔNG có tham số seed, và class_temperature=0 vẫn không đủ: position_temperature
# (=5.0) cùng nhiễu khởi tạo diffusion khiến mỗi lần generate ra một bản khác — đã đo, hash
# audio khác nhau qua từng lần chạy cùng text. torch.manual_seed() trước mỗi generate làm
# output giống hệt tới từng byte. Ghim seed để render tái lập được và để A/B chỉ khác đúng
# thứ mình đang so.
SEED = 42

_prompt_cache = {}


def manifest_path(name):
    return os.path.join(VOICES_DIR, name + ".profile.json")


def load_profile(name):
    """Trả manifest dict, hoặc None nếu profile không có biến thể (lối cũ)."""
    p = manifest_path(name)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def split_by_marker(text, known_markers):
    """Cắt text thành [(marker|None, đoạn)]. Marker có hiệu lực tới marker kế tiếp.

    - Thẻ gốc OmniVoice: giữ nguyên trong đoạn.
    - Marker biết: thành ranh giới nhịp, gỡ khỏi text.
    - Bracket lạ: gỡ bỏ (không để lọt ra thành tiếng đọc) và báo về cho caller.
    """
    spans, unknown = [], []
    cur_marker, buf, pos = None, [], 0

    for m in _BRACKET.finditer(text):
        tag = m.group(1)
        low = tag.lower()
        if low in NATIVE_TAGS:
            continue  # để nguyên, engine xử
        buf.append(text[pos:m.start()])
        pos = m.end()
        if low in known_markers:
            chunk = "".join(buf).strip()
            if chunk:
                spans.append((cur_marker, chunk))
            buf, cur_marker = [], low
        else:
            unknown.append(tag)

    buf.append(text[pos:])
    chunk = "".join(buf).strip()
    if chunk:
        spans.append((cur_marker, chunk))
    return spans, unknown


def _variant_paths(profile, marker):
    """Đường dẫn wav/txt của một biến thể (hoặc của chính profile nếu marker None)."""
    name = profile["name"]
    v = profile["variants"][marker]
    wav = os.path.join(VOICES_DIR, v["wav"].replace("/", os.sep))
    txt = os.path.splitext(wav)[0] + ".txt"
    return name, wav, txt, float(v.get("speed", 1.0))


def get_prompt(model, profile_name, profile, marker):
    """Clone prompt cho một marker. Không manifest -> dùng profile gốc qua voice_profiles."""
    key = (profile_name, marker)
    if key in _prompt_cache:
        return _prompt_cache[key]

    if profile is None or marker is None:
        import voice_profiles as vp
        prompt = vp.get_clone_prompt(model, profile_name)
    else:
        _, wav, txt, _ = _variant_paths(profile, marker)
        ref_text = None
        if os.path.isfile(txt):
            with open(txt, "r", encoding="utf-8") as f:
                ref_text = f.read().strip() or None
        pt = os.path.splitext(wav)[0] + ".prompt.pt"
        prompt = None
        # So với CẢ .txt, không chỉ .wav: DESIGN mục 13 dặn "sửa tay .txt rồi xoá .prompt.pt",
        # nên chuyện người dùng sửa transcript là đường đi được biết trước. Chỉ so mtime(wav)
        # thì ai quên xoá .pt sẽ được phục vụ ref_text CŨ, im lặng. voice_profiles.py cũ đã
        # so cả hai — nhánh mới không được yếu hơn nhánh cũ.
        newest_src = os.path.getmtime(wav)
        if os.path.isfile(txt):
            newest_src = max(newest_src, os.path.getmtime(txt))
        if os.path.isfile(pt) and os.path.getmtime(pt) >= newest_src:
            try:
                from omnivoice.models.omnivoice import VoiceClonePrompt
                prompt = VoiceClonePrompt.load(pt)
            except Exception:
                prompt = None
        if prompt is None:
            prompt = model.create_voice_clone_prompt(ref_audio=wav, ref_text=ref_text)
            try:
                prompt.save(pt)
            except Exception:
                pass

    _prompt_cache[key] = prompt
    return prompt


def _rms(a):
    import numpy as np
    a = np.asarray(a, dtype="float32")
    return float(np.sqrt(np.mean(a * a))) if a.size else 0.0


def _edge_fade(seg, sr):
    """Vuốt CROSSFADE giây ở hai đầu một nhịp.

    Bản đầu định crossfade hai nhịp chồng lên nhau, nhưng nhánh đó là CODE CHẾT: synth luôn
    chèn khe im lặng > 0 giữa các nhịp nên điều kiện `gap == 0` không bao giờ đúng. Hậu quả
    thật: mỗi câu TTS thường kết ở biên độ khác 0, nối thẳng vào mảng zeros là một bước nhảy
    -> click nghe được ở MỌI mối nối của MỌI bản render. Vuốt hai đầu rồi mới chèn im lặng
    thì vừa hết click, vừa giữ đúng khe nghỉ mà thiết kế muốn.
    """
    import numpy as np
    seg = np.asarray(seg, dtype="float32").copy()
    k = min(max(1, int(sr * CROSSFADE)), len(seg) // 2)
    if k > 1:
        ramp = np.linspace(0.0, 1.0, k, dtype="float32")
        seg[:k] *= ramp
        seg[-k:] *= ramp[::-1]
    return seg


def _join(parts, sr, gaps):
    """Nối các nhịp: vuốt hai đầu mỗi nhịp rồi chèn im lặng theo `gaps`."""
    import numpy as np
    if not parts:
        return np.zeros(0, dtype="float32")
    faded = [_edge_fade(p, sr) for p in parts]
    out = [faded[0]]
    for i, seg in enumerate(faded[1:]):
        g = int(sr * gaps[i])
        if g > 0:
            out.append(np.zeros(g, dtype="float32"))
        out.append(seg)
    return np.concatenate(out)


def synth(model, text, profile_name, language="Vietnamese", speed=None, verbose=True,
          seed=SEED):
    """Tổng hợp một đoạn text có marker. Trả (audio float32, sample_rate, log dict).

    `seed=None` để chạy tự do (mỗi lần một bản khác); mặc định ghim để tái lập được.
    """
    import numpy as np
    import torch

    profile = load_profile(profile_name)
    known = set(profile["variants"].keys()) if profile else set()
    spans, unknown = split_by_marker(text, known)
    if unknown and verbose:
        print(f"[vlab] bỏ qua bracket lạ: {sorted(set(unknown))}")
    if not spans:
        return np.zeros(0, dtype="float32"), model.sampling_rate, {"spans": 0}

    neutral = profile.get("neutral") if profile else None
    target_rms = None
    if profile and neutral:
        _, nwav, _, _ = _variant_paths(profile, neutral)
        if os.path.isfile(nwav):
            import soundfile as sf
            ref, _ = sf.read(nwav, dtype="float32")
            target_rms = _rms(ref)

    parts, gaps, used = [], [], []
    prev_marker = object()
    for marker, chunk in spans:
        eff = marker if (profile and marker in known) else (neutral if profile else None)
        prompt = get_prompt(model, profile_name, profile, eff)
        sp = speed
        if sp is None and profile and eff in known:
            sp = float(profile["variants"][eff].get("speed", 1.0))
        kw = {"speed": sp} if sp and sp != 1.0 else {}

        for sent in split_sentences(chunk):
            if seed is not None:
                # seed lệch theo thứ tự câu: tái lập được, nhưng các câu không dùng chung
                # đúng một mẫu nhiễu.
                torch.manual_seed(seed + len(parts))
                torch.cuda.manual_seed_all(seed + len(parts))
            audio = model.generate(text=sent, language=language,
                                   voice_clone_prompt=prompt, normalize_text=False, **kw)[0]
            audio = np.asarray(audio, dtype="float32")

            # Chuẩn hoá về mức của clip trung tính -> chống vênh âm lượng ở mối nối.
            if target_rms and eff is not None:
                r = _rms(audio)
                if r > 1e-6:
                    audio = np.clip(audio * (target_rms / r), -1.0, 1.0)

            if parts:
                gaps.append(GAP_MARKER if eff != prev_marker else GAP_SAME)
            parts.append(audio)
            used.append(eff or profile_name)
            prev_marker = eff
            if verbose:
                print(f"[vlab] {eff or '(gốc)':<12} {len(audio)/model.sampling_rate:5.2f}s  {sent[:52]!r}")

    out = _join(parts, model.sampling_rate, gaps)
    return out, model.sampling_rate, {"spans": len(spans), "sentences": len(parts),
                                      "markers": used}
