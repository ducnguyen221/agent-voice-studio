# Trạm giọng — từng thư mục là gì

Repo `agent-voice-studio` chỉ chứa **mã**. Mọi thứ của riêng bạn — venv engine, giọng, nhạc nền,
output — nằm ở **trạm giọng**. Tài liệu này mô tả cây trạm, hai chế độ đặt trạm, và việc gì an
toàn với từng thư mục.

Repo này là một **năng lực thêm**, đứng một mình: cài khi bạn cần một giọng đọc. Quy trình sản
xuất nội dung nào gọi nó thì gọi qua hợp đồng mã thoát + dòng JSON cuối stdout, và chạy bình
thường khi máy chưa cài nó. Không có "bộ" nào phải cài đủ.

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
**Agent cài phải trình bảng đó cho người dùng và chờ họ chọn** — không tự chọn im lặng. Tự
khai `--non-interactive` cũng vậy: nó nói "không có ai ngồi đây", KHÔNG nói "đoán hộ tôi", nên
thiếu `--yes`/`--mode`/`--station` thì vẫn là mã 2.

Agent cài nên **phân tích rồi khuyến nghị**, không hỏi trống: người không rành kỹ thuật, một
máy ⇒ `embedded`; người nhiều máy, rành hơn, hoặc repo này là bản public của chính họ ⇒
`separate`.

Xem trước, không ghi gì: `voice-studio init --dry-run`.

### Biến cấu hình ở chế độ `embedded` — `<repo>/.env`

`init` chép `.env.example` (khuôn tên biến, không có giá trị) thành `<repo>/.env` và khoá
quyền 600 trên POSIX. Chạy lại **không đè** file anh đã điền.

Thứ tự đọc một biến: **biến môi trường thật → `<repo>/.env` (chỉ khi `mode = embedded`) →
chưa đặt**. Biến thật luôn thắng file: máy đã đặt biến (máy chạy lịch) không được để một file
lạc vào repo cướp cấu hình. Chế độ `separate` **không bao giờ** nạp `.env` — ở đó repo có thể
là bản public của chính anh, và tự nạp một file nằm trong repo là mở cửa cho nó.

Một giới hạn phải biết: chỉ thứ đi qua `voice_studio._env.env()` mới đọc được từ `.env`. Biến
do **tiến trình khác** đọc — venv engine chạy riêng, thư viện Hugging Face đọc `HF_*` thẳng từ
môi trường — thì không; chúng được đánh dấu `[MÔI TRƯỜNG THẬT]` ngay trong `.env.example` và
phải đặt ở cấp user hoặc trong môi trường của scheduled task, kể cả khi đang `embedded`.

`.env` giữ **đường dẫn và cấu hình máy**, không bao giờ giữ token. Bí mật nằm trong file ngoài
git mà đường dẫn trong `.env` trỏ tới (ở `separate`: `~/.secret/voice-studio/`).

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
- `<repo>/.env` được dọn sẵn từ `.env.example`, quyền 600 trên POSIX. Cùng bộ test còn kiểm
  rằng **mọi biến mã đọc đều có trong khuôn** — thiếu một dòng là người dùng không biết mình
  phải điền gì, và chỉ phát hiện ra lúc lệnh nổ giữa chừng.
- Hook `pre-commit` (cài vào `.git/hooks/` nếu chưa có hook): chặn commit file dưới `workspace/`,
  `.env`, `studio.local.json`, và dòng thêm mới trông giống token. Hook đã có sẵn thì giữ nguyên.
- `doctor` kiểm lại các rào trên mỗi lần chạy.
