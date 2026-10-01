# Cài trạm giọng và engine

Repo mang **phương pháp + mã** (package `voice_studio`, lệnh `voice-studio`). **Bạn mang engine và
giọng của chính mình** — chúng sống ở *trạm giọng*, ngoài git.

Engine tham chiếu: **OmniVoice 0.2.1** (k2-fsa) — chạy offline, đa ngôn ngữ, clone giọng zero-shot.
Mọi số đo trong bộ tài liệu này đo trên nó. Thay engine khác được; luật ở
`vietnamese-tts-script.md` vẫn đúng về hình dạng, còn lỗi cụ thể sẽ khác.

## ⚠️ Giấy phép — đọc trước khi cài

| Thành phần | Giấy phép | Ghi chú |
|---|---|---|
| Code OmniVoice | Apache-2.0 | |
| **Weights OmniVoice** | **CC-BY-NC** (không thương mại) | tải từ Hugging Face lúc chạy lần đầu; repo không phát hành |
| Repo này | MIT | |

Audio sinh ra từ weights không thương mại dùng cho **kênh kiếm tiền, quảng cáo, sản phẩm bán** là
rủi ro giấy phép bạn phải tự cân nhắc. Giấy phép weights đi đường riêng với giấy phép code và hay
đổi âm thầm hơn — kiểm lại mỗi lần nâng engine.

## Cần gì

- **Python 3.10+** (đã đo trên 3.12).
- GPU **NVIDIA** cho tốc độ dùng được. Apple Silicon chạy qua **MPS** — đo 30/09/2026 trên một máy
  M1 16 GB, fp16: RTF 1,65 với `--instruct`, 2,7–4,8 với profile clone (chậm hơn thời gian thực;
  fp32 chậm hơn fp16 ~12 %). CPU chạy được nhưng chậm tới mức đổi cả cách làm việc.
- **~3,3 GB** đĩa cho weights (cache Hugging Face, lần chạy đầu; dùng chung mọi venv của máy).
- torch: bản CUDA ~2,5 GB; bản macOS arm64 ~130 MB (cả engine ≈ 300 MB).
- Internet **một lần** — tải weights và (nếu dùng phiên âm tự động) model ASR. Sau đó chạy offline.
- `ffmpeg` trên PATH (hoặc `FFMPEG_DIR`) — cho mp3 và ghép video.

## Cài — sáu bước

**`-e` hay bản sao:** lệnh dưới dùng `-e` (máy phát triển, và máy embedded nơi giọng nằm trong venv
của repo video). Chỉ xưởng Windows **chạy lịch** có trạm riêng cài bản sao — luật
và lệnh Windows/macOS chỉ nằm ở `docs/INSTALL.md` mục 3 của repo; đừng chép sang đây.

**1. Chọn chỗ đặt trạm** — `voice-studio init` sẽ hỏi; đọc `docs/WORKSPACE.md` của repo nếu
phân vân. Khuyến nghị cho người mới: **`embedded`** (trạm = `<repo>/workspace/`).

**2. Clone repo và tạo venv engine.** Đường venv chuẩn là `<trạm>/omnivoice/.venv`; `init` in đúng
lệnh cho máy bạn — có thể chạy `init` trước (bước 5) rồi quay lại đây.

```bash
git clone <địa chỉ repo agent-voice-studio>
python -m venv <trạm>/omnivoice/.venv
# Windows:          <trạm>\omnivoice\.venv\Scripts\activate
# macOS / Linux:    source <trạm>/omnivoice/.venv/bin/activate
```

**3. Cài torch theo hệ điều hành** — pip không tự chọn đúng bản:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu126   # Windows/Linux + NVIDIA (khớp CUDA)
pip install torch --index-url https://download.pytorch.org/whl/cpu     # không GPU
pip install torch                                                      # macOS Apple Silicon (MPS)
```

**Torch phải đủ mới.** Engine kéo một bản transformers cần một kiểu dtype có từ torch 2.7; torch
cũ hơn sập lúc import với lỗi không chỉ rõ là do phiên bản.

**4. Cài engine và package:**

```bash
pip install -e "<thư mục repo>[engine]"           # omnivoice==0.2.1 + transformers + lệnh voice-studio
pip install -e "<thư mục repo>[engine,mcp,lab]"   # tuỳ chọn thêm: MCP server, bộ đào giọng (librosa, scikit-learn)
```

Phần phụ `[engine]` ghim `omnivoice` và giữ `transformers` trong **khoảng đã đo** (khai ở
`pyproject.toml`). Cài `omnivoice` trần thì pip kéo transformers mới nhất — chưa ai đo; doctor
báo `[WARN] transformers` khi bản đang có nằm ngoài khoảng.

Nhóm tuỳ chọn khác: `[ui]` (gradio), `[clone]` (faster-whisper + av ghim theo cặp, yt-dlp). **Đừng cài phần phụ
chuẩn hoá văn bản của engine trên Windows** — một phụ thuộc không có wheel, đòi cả bộ build MSVC;
và bạn cũng không muốn nó (xem cảnh báo bộ chuẩn hoá trong `vietnamese-tts-script.md`).

**5. Dựng trạm:**

```bash
voice-studio init                 # hỏi embedded / separate (Enter = embedded)
voice-studio init --dry-run       # chỉ xem sẽ làm gì
voice-studio init --station ~/.voice          # separate, không hỏi
voice-studio init --station <trạm cũ> --existing   # nhận trạm đang chạy: chỉ ghi station.json
```

`init` dựng `station.json`, `omnivoice/voices/`, `assets/bgm/` (khung thư viện nhạc nền, không
mp3), `out/`, `cache/`. Nó **không** tạo venv, không tải model — chỉ in lệnh.

**6. Kiểm, rồi tải weights ở lần tổng hợp đầu:**

```bash
voice-studio doctor                       # kiểm engine; KHÔNG tải gì, không nạp model
OMNIVOICE_ONLINE=1 voice-studio speak --text "Xin chào" --instruct "female, young adult" --out <trạm>/out/thu.wav --json
# PowerShell: $env:OMNIVOICE_ONLINE = "1"; voice-studio speak …; Remove-Item Env:OMNIVOICE_ONLINE
```

Mặc định engine chạy **offline** (`HF_HUB_OFFLINE=1`) để lịch chạy không bao giờ treo vì mạng;
`OMNIVOICE_ONLINE=1` mở mạng cho **đúng lần tổng hợp đó** — chỉ lệnh nạp model (`speak`,
`make-profile`, `narrate`…) mới tải weights; `doctor` thì không bao giờ. Sau đó doctor báo
`[PASS] weights`. `doctor` thoát mã 3 kèm hướng dẫn nếu còn thiếu gì.

Thử cả chuỗi không cần ghi âm ai: làm theo `omnivoice/voices/_example/README.md` trong trạm
(tạo giọng `sample` bằng thiết kế giọng, rồi `voice-studio speak`).

## Biến môi trường

Chế độ `embedded` không cần đặt biến nào. Chế độ `separate` nên đặt `VOICE_STATION` ở mức người
dùng (mọi harness, shell, lịch chạy đều thừa hưởng):

```powershell
setx VOICE_STATION "<đường trạm>"
```
```bash
echo 'export VOICE_STATION=<đường trạm>' >> ~/.zshrc
```

| Biến | Nghĩa | Mặc định |
|---|---|---|
| `VOICE_STATION` | gốc trạm giọng | theo thứ tự trong `docs/WORKSPACE.md` |
| `OMNIVOICE_DIR` | **tên cũ** — trỏ thư mục engine (`<trạm>/omnivoice`); vẫn đọc được, `doctor` nhắc đổi | — |
| `VOICES_DIR` | kho profile | `<trạm>/omnivoice/voices` |
| `VOICE_DEFAULT_PROFILE` | profile mặc định khi không có `_default.txt` | — |
| `OMNIVOICE_DEVICE` | ép thiết bị `cuda` / `mps` / `cpu` | tự chọn `cuda → mps → cpu` |
| `OMNIVOICE_DTYPE` | ép độ chính xác `float16` / `float32` / `auto` | `cuda`,`mps` → float16 · `cpu` → float32 |
| `HF_DEACTIVATE_ASYNC_LOAD` | tắt nạp weights bất đồng bộ của transformers | `1` sẵn trên macOS (xem dưới) |
| `OMNIVOICE_ONLINE` | `1` = cho phép tải từ Hugging Face | tắt (offline) |
| `VOICE_BGM_DIR`, `VOICE_BGM`, `VOICE_BGM_VOL` | thư viện nhạc nền · file nhạc cho một lần ghép · âm lượng | `<trạm>/assets/bgm` · — · 0.10 |
| `VOICE_STUDIO_WORK` | output tạm + chỗ làm việc của `lab` | `<trạm>/out` |
| `FFMPEG_DIR` | thư mục chứa ffmpeg/ffprobe | PATH |

Tên biến nhạc nền của bản cũ vẫn đọc được một phiên bản, kèm cảnh báo; `doctor` chỉ ra tên cần đổi.
**Đặt `VOICE_STUDIO_WORK` ngoài repo** (mặc định đã vậy): output là dữ liệu giọng thật.

### Apple Silicon (MPS): fp16 là mặc định

Đo trên M1 16 GB với khúc văn đúng cỡ pipeline thật cắt ra: **fp16 RTF ≈ 1,77 · fp32 ≈ 2,31**
— nhanh hơn ~23 %, đủ để một lượt đọc dài xong sớm hơn hơn một tiếng. Nên engine mặc định fp16
trên MPS. Chất lượng nghe thì **phải nghe rồi mới kết luận**: đặt `OMNIVOICE_DTYPE=float32` nếu
bạn thấy fp16 rè hoặc méo.

Trên macOS engine tự đặt (nếu bạn chưa đặt) hai biến:

- `PYTORCH_ENABLE_MPS_FALLBACK=1` — phép toán nào MPS chưa có thì chạy trên CPU thay vì sập.
- `HF_DEACTIVATE_ASYNC_LOAD=1` — transformers 5.17 nạp weights song song **segfault** khi dtype
  là fp16 trên MPS. Đổi vài giây khởi động lấy một lượt không sập.

fp16 trên CPU bị từ chối cố ý: torch chạy CPU half bằng đường mô phỏng, chậm hơn fp32.

*[Số đo lấy từ spike Mac; chưa chạy lại trên máy Windows — Windows không có MPS.]*

## Gọi từ pipeline khác

Hai đường, cùng một venv engine:

**CLI — cho việc một lần** (đọc một bài, lồng tiếng một video). Hợp đồng ổn định: file ở `--out`,
**một dòng JSON cuối stdout** với `--json`, log ra stderr, mã thoát `0` ok · `1` lỗi engine (thử lại
được) · `2` gọi sai (thiếu profile, text rỗng — sửa cấu hình) · `3` trạm/engine chưa cài.

```bash
<venv>/python -m voice_studio speak --file bai.txt --profile narrator --out bai.mp3 --json
<venv>/python -m voice_studio narrate --video cam.mp4 --file loi.txt --out ra.mp4 --bgm neutral --json
```

Bên gọi đọc **mã thoát và dòng JSON cuối**, không đọc log. Bẫy PowerShell 5.1: đừng `2>&1` khi gọi
lệnh native (mỗi dòng stderr thành lỗi, `$?` sai dù mã 0) — đọc `$LASTEXITCODE`.

**In-process — cho việc đọc hàng trăm câu** (sách nói, video nhiều đoạn), vì CLI mỗi câu là nạp
model lại mỗi lần:

```python
from voice_studio import engine, profiles, av
model = engine.load()                         # cuda → mps → cpu
prompt = profiles.get_clone_prompt(model)     # profile mặc định
wav, sr = engine.synth("Xin chào.", prompt, seed=42)
engine.save(wav, "a.mp3", sr)
```

Ghim phiên bản hợp đồng bằng `voice_studio.API_VERSION` (semver — đổi số đầu là đổi chữ ký).
Trong JSON của `speak` / `narrate` / `doctor`, khoá `voice_studio` **luôn** là `API_VERSION`; bản
phát hành của package (`voice_studio.__version__`) nằm ở khoá riêng `version`. Bên gọi muốn báo
lại phiên bản giọng trong JSON của mình thì giữ đúng hai nghĩa đó, đừng đặt bản phát hành vào khoá
`voice_studio`.

## Trạm video gọi giọng

Repo dựng video cùng họ (`agent-video-studio`) lồng tiếng bằng `voice_studio` **in-process**:
cài nó vào **cùng venv engine** của trạm giọng — `pip install -e <thư mục agent-video-studio>` —
để hai package dùng chung torch và model chỉ nạp một lần. Lệch phiên bản hợp đồng thì `doctor` của
mỗi bên báo.

## Giữ giọng ngoài version control

Clip tham chiếu là dữ liệu gần với sinh trắc học. Repo chặn cả họ audio mặc định (`.gitignore`),
chế độ `embedded` thêm hook `pre-commit` chặn `workspace/` và `.env`, và ví dụ công khai **không có
audio nào** — cố ý.

**Chỉ clone giọng của chính bạn, hoặc giọng mà chủ nhân đã đồng ý bằng văn bản.**
