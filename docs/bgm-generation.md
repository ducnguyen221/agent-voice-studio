# Sinh nhạc nền bằng MusicGen

Repo **không phát hành file nhạc nào**. Thư viện nhạc nền của trạm (`<trạm>/assets/bgm/`) do bạn
tự lấp: tự sinh bằng MusicGen theo hướng dẫn này, hoặc bỏ vào nhạc bạn có quyền dùng.

## ⚠️ Giấy phép — đọc trước khi sinh

| Thành phần | Giấy phép | Dùng thương mại? |
|---|---|---|
| Weights `facebook/musicgen-small/medium/large` | **CC-BY-NC 4.0** | **Không** |
| Code MusicGen (audiocraft) | MIT | có |
| Script trong `extras/musicgen/` | MIT (repo này) | có |

Đã kiểm trên thẻ model Hugging Face ngày 2026-09-20 (ghi ở `extras/musicgen/upstream.json`).
Weights không thương mại nghĩa là: dùng nhạc sinh ra cho **kênh có kiếm tiền, quảng cáo, sản phẩm
bán** là rủi ro giấy phép mà bạn phải tự cân nhắc — repo không kết luận thay bạn. Giấy phép có thể
đổi; kiểm lại thẻ model mỗi khi đổi model id. Cần chắc chắn cho mục đích thương mại thì dùng nhạc
có giấy phép rõ ràng.

## Cần gì

- Một venv có `torch`, `transformers`, `soundfile` — có thể dùng luôn venv engine của trạm:
  `pip install transformers` vào đó.
- `ffmpeg` (để đổi sang mp3 — thư viện đọc `<style>.mp3`).
- GPU NVIDIA cho tốc độ dùng được; CPU chạy được nhưng chậm nhiều lần. Trên Apple Silicon
  script dùng CPU `[chưa kiểm MPS]`.
- Lần đầu tải weights vào cache Hugging Face — đây là bước tải duy nhất. `large` nặng nhất
  (cỡ chục GB), `small` nhẹ nhất `[dung lượng chưa đo trên máy thật]`; thử nhanh bằng `small`.

## Sinh cả bộ vào thư viện

```bash
python extras/musicgen/gen_pack.py                                  # 10 style, 30 giây/bản
python extras/musicgen/gen_pack.py --only lofi-chill tech-pulse     # chỉ vài style
python extras/musicgen/gen_pack.py --model small --seconds 20       # thử nhanh
```

- Bảng style ở `extras/musicgen/styles.json`: `name` (= tên file `<name>.mp3`), `mood`/`use`
  (mô tả cho người chọn), `prompt` (tiếng Anh — MusicGen hiểu mô tả tiếng Anh tốt nhất).
- Nhạc ghi thẳng vào thư viện của trạm (`VOICE_BGM_DIR`, mặc định `<trạm>/assets/bgm/`), và
  style được **thêm** vào `bgm-library.json`. Mô tả, style mặc định, âm lượng bạn đã chỉnh
  **không bị đè**. File đã có thì bỏ qua; `--force` để sinh lại.
- Kiểm: `voice-studio bgm list` — không style nào báo `[THIẾU FILE]`.

## Sinh một bản lẻ

```bash
python extras/musicgen/gen.py --prompt "calm ambient pad, 80 BPM, instrumental" --name calm --mp3
```

Mặc định ghi vào `<VOICE_STUDIO_WORK>/musicgen/` (trong trạm, không bao giờ trong repo). Nghe
thử, ưng thì chép vào thư viện và khai trong `bgm-library.json`.

## Viết prompt cho nhạc nền

- Luôn có `instrumental` — lời hát tranh chỗ với giọng đọc.
- Ghi BPM và tính chất (`unobtrusive background bed`, `loopable`): nhạc nền phải lùi sau giọng.
- Tránh nhạc cụ đè dải giọng nói (lead sáng, synth chói) — pad, piano nhẹ, bass mềm an toàn hơn.
- MusicGen không tái lập: cùng prompt ra bản khác mỗi lần. Ưng bản nào thì **giữ file**, đừng
  mong sinh lại được y hệt.

## Âm lượng

Renderer trộn nhạc ở mức `volume` trong `bgm-library.json` (mặc định 0.10). Đổi cho một lần chạy
bằng `VOICE_BGM_VOL`. Chọn file cụ thể cho một lần ghép: `VOICE_BGM=<đường mp3>`.
