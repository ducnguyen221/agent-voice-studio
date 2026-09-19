"""vlab.py — ALIAS giữ đường import cũ; mã thật ở `voice_studio.lab.vlab`."""
import _env  # noqa: F401 — đưa gốc repo vào sys.path khi chạy trực tiếp từ thư mục studio/
from voice_studio.lab.vlab import *  # noqa: F401,F403
from voice_studio.lab.vlab import SEED, get_prompt, load_profile, manifest_path, split_by_marker, synth  # noqa: F401
