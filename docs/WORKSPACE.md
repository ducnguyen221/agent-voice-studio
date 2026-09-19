# Trạm giọng — từng thư mục là gì

Repo `agent-voice-studio` chỉ chứa **mã**. Mọi thứ của riêng bạn — venv engine, giọng, nhạc nền,
output — nằm ở **trạm giọng**. Tài liệu này mô tả cây trạm, hai chế độ đặt trạm, và việc gì an
toàn với từng thư mục.

## Hai chế độ đặt trạm

| Chế độ | Trạm | Secret | Dành cho |
|---|---|---|---|
| **`embedded`** — gọn trong repo (**mặc định, khuyến nghị cho người mới**) | `<repo>/workspace/` | `<repo>/.env` | một máy, "mở một folder là thấy hết" |
| **`separate`** — trạm ngoài repo | `~/.voice` (hoặc nơi bạn chọn) | kho secret riêng của máy (`~/.secret/…`) | nhiều máy, repo public của chính bạn, nhiều repo dùng chung trạm |

`voice-studio init` hỏi bạn chọn (Enter = `embedded`) và ghi lựa chọn vào
`<repo>/studio.local.json`. Không hỏi trong ba trường hợp:

- `--station DIR` — bạn chỉ thẳng trạm ⇒ `separate`.
- Máy **đã có trạm ngoài**: biến `VOICE_STATION` (hoặc tên cũ `OMNIVOICE_DIR`) đã đặt, hoặc
  `~/.voice` đã có `station.json` / `omnivoice/voices/` ⇒ tự `separate`, **không bao giờ** tạo
  `workspace/` (hai trạm cho một repo = hai nguồn sự thật).
- `--mode embedded|separate` hoặc `--yes` (= nhận khuyến nghị `embedded`).

Chạy không có terminal (agent, script) mà chưa chọn ⇒ `init` in bảng lựa chọn rồi thoát mã 2.
**Agent cài phải trình bảng đó cho người dùng và chờ họ chọn** — không tự chọn im lặng.

Xem trước, không ghi gì: `voice-studio init --dry-run`.

### Thứ tự tìm trạm (mọi lệnh dùng chung một hàm)

```
--station  →  VOICE_STATION  →  OMNIVOICE_DIR (tên cũ, trỏ thư mục engine)  →
<repo>/studio.local.json  →  <repo>/workspace/ nếu có  →  ~/.voice
```

`<repo>` là bản clone đã `pip install -e` (hoặc đặt `VOICE_STUDIO_REPO`). Cài dạng wheel thì
không có repo — chỉ dùng được `separate`.

## Cây trạm

```
<trạm>/
├── station.json          QUẢN LÝ   cấu hình trạm
├── omnivoice/
│   ├── .venv/            QUẢN LÝ   venv engine (torch, omnivoice, voice_studio)
│   └── voices/           CONTENT   kho profile giọng
│       ├── <tên>.wav     CONTENT   clip tham chiếu
│       ├── <tên>.txt     CONTENT   lời của clip
│       ├── <tên>.profile.json  CONTENT  profile đa sắc thái (nếu có)
│       ├── _default.txt  QUẢN LÝ   tên profile mặc định
│       ├── <tên>.prompt.pt  QUẢN LÝ  cache clone prompt (dựng lại được)
│       └── _example/     MẪU       hướng dẫn tạo giọng ví dụ trung tính
├── assets/bgm/           CONTENT   thư viện nhạc nền: bgm-library.json + <style>.mp3
├── out/                  NHÁP      output tạm + chỗ làm việc của `voice-studio lab`
└── cache/                NHÁP      cache công cụ
```

Tuỳ chọn, bạn tự thêm khi cần: `voice-clean/` (công cụ làm sạch bản ghi + model, xem
`voice_studio/clean/README.md`), `musicgen/` (nếu chạy sinh nhạc riêng), `data/`, `.raw/` (bản ghi
gốc). Chúng không do `init` tạo.

## Từng thư mục

| Thư mục / file | Loại | Mục đích | Ai / cái gì ghi | `export --personal` | `backup` | Nhạy cảm | Xoá được? |
|---|---|---|---|---|---|---|---|
| `station.json` | quản lý | hợp đồng (`contract`), chế độ, `venv`, `engine_dir`, `bgm_dir`, `device`, `default_profile` | `init`; bạn sửa tay được | có | có | không | xoá ⇒ `init --existing` dựng lại |
| `omnivoice/.venv/` | quản lý | Python + torch + engine + package `voice_studio` | bạn, theo lệnh `init` in ra | **không** (cài lại ở máy mới) | **không** | không | được — tạo lại venv là xong |
| `omnivoice/voices/*.wav, *.txt, *.profile.json` | **content** | giọng của bạn | `make-profile`, `clone`, `lab build`, `lab split` | có | có | **CÓ** — dữ liệu sinh trắc gần đúng | **không** — mất là phải dựng lại từ bản ghi |
| `omnivoice/voices/_default.txt` | quản lý | profile mặc định | `make-profile --set-default`, bạn | có | có | không | được (mất mặc định: lệnh phải truyền `--profile`) |
| `omnivoice/voices/*.prompt.pt` | quản lý | cache clone prompt, nhanh gấp ~50 lần lần gọi đầu | engine tự ghi | **không** | **không** | thấp | được — tự dựng lại |
| `omnivoice/voices/_example/` | mẫu | hướng dẫn giọng ví dụ | `init` chép từ repo | có (vô hại) | có | không | được |
| `assets/bgm/bgm-library.json` | content | style, style mặc định, âm lượng | `init` (khung), `gen_pack.py`, bạn | có | có | không | không nên |
| `assets/bgm/<style>.mp3` | content | nhạc nền | bạn / MusicGen (`docs/bgm-generation.md`) | có | có | giấy phép nhạc | được nếu còn nguồn |
| `out/` (= `VOICE_STUDIO_WORK`) | nháp | output mặc định, `out/lab/<tên>/` của bộ dựng giọng | mọi lệnh | **không** | **không** | **CÓ** — audio giọng thật | được, trừ khi đang giữa mẻ `lab mine → build` |
| `cache/` | nháp | cache công cụ | công cụ | không | không | thấp | được |

Weights của engine (~4 GB) **không** nằm trong trạm mà trong cache Hugging Face (`HF_HOME`,
mặc định `~/.cache/huggingface`). Chuyển máy thì tải lại (`OMNIVOICE_ONLINE=1 voice-studio doctor`).

## Vận hành

| Việc | Lệnh | Ghi chú |
|---|---|---|
| Kiểm trạm | `voice-studio doctor` | ĐỎ khi vừa có `workspace/` vừa có trạm ngoài; embedded: kiểm `workspace/`, `.env` không bị git theo dõi, repo không nằm trong OneDrive/Drive/iCloud/Dropbox, `.env` quyền 600 |
| Cập nhật repo | `voice-studio update` | = `git pull --ff-only`. **Không bao giờ** xoá hay `git clean`. **Đừng xoá folder repo để cài lại** — ở chế độ embedded đó là xoá luôn giọng của bạn |
| Sao lưu | `voice-studio backup --out trạm.zip` | cả trạm trừ venv, `cache/`, `out/`, `*.prompt.pt`; `.env` chỉ kèm khi thêm `--with-env` |
| Chuyển máy | `voice-studio export --personal --out giong.zip` → máy mới: `voice-studio import giong.zip` | gói `voices/`, `assets/bgm/`, `station.json`; từ chối file trông như secret (`*token*`, `*secret*`, `.env`…); `import` không đè file trùng trừ khi `--force` |
| Tách trạm ra ngoài | `voice-studio migrate --to separate [--station DIR]` | dời `workspace/` → `~/.voice` (hoặc DIR), `.env` → `~/.secret/voice-studio/.env`, ghi lại `studio.local.json`; đích phải rỗng |

## Rào của chế độ embedded (init tự dựng)

- `.gitignore` của repo khoá `/workspace/`, `.env`, `.env.*` (trừ `.env.example`), `studio.local.json`
  — test `tests/test_repo_gates.py` đỏ nếu ai xoá một dòng.
- Hook `pre-commit` (cài vào `.git/hooks/` nếu chưa có hook): chặn commit file dưới `workspace/`,
  `.env`, `studio.local.json`, và dòng thêm mới trông giống token. Hook đã có sẵn thì giữ nguyên.
- `doctor` kiểm lại các rào trên mỗi lần chạy.
