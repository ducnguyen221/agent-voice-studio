# Lịch sử phát hành

Mới nhất trước. Mỗi mục là thứ **người dùng** thấy khác đi; chi tiết từng thay đổi nằm trong lịch
sử git. Số phiên bản ở đây, trong `pyproject.toml`, `voice_studio/__init__.py` và ba manifest
plugin luôn cùng một số — `tests/test_version_sync.py` đỏ nếu lệch.

## 0.3.3 — 2026-10-01

**Extra `[clone]` ghim faster-whisper + PyAV theo cặp đã đo.** Engine, profile, trạm, CLI và mã thoát
không đổi.

- `clone = ["faster-whisper>=1.2,<1.3", "av>=15,<19", "yt-dlp"]`. Trước đây `av` không ghim nên pip
  kéo PyAV 19 — bản đã bỏ `metadata_errors` mà `faster_whisper.audio.decode_audio` truyền — và mọi
  thứ gọi faster-whisper (clone từ media, căn phụ đề của runner truyện marketing-studio dùng chung
  venv giọng) chết với `TypeError` (Mac mini, 01/10/2026). Cùng cặp với
  `requirements-runners.txt` của agent-marketing-studio 1.1.6.
- CI job mới `clone-runtime` (Windows + macOS): cài `.[test,clone]` thật rồi gọi `decode_audio`
  trên wav 1 giây; `VOICE_STUDIO_REQUIRE_CLONE=1` biến skip thành đỏ. Cổng cấu hình
  `tests/test_clone_runtime.py` giữ khoảng ghim.
- INSTALL (`INSTALL.md`, `docs/INSTALL.md`): macOS cài `ffmpeg-full` thay `ffmpeg`. `narrate` không
  cần bộ lọc chữ, nhưng ffmpeg của máy dùng chung với runner truyện — bản Homebrew core thiếu
  `drawtext`/`subtitles`.
- **Nâng cấp venv giọng đang chạy**: `pip install -e ".[clone]"` (hoặc
  `pip install -r <marketing>/requirements-runners.txt`) để đưa `av` về trong khoảng ghim.

## 0.3.2 — 2026-09-30

**Dọn theo review, hành vi chạy không đổi** — engine, profile, trạm, CLI và mã thoát giữ nguyên
trên cả Windows lẫn macOS; chỉ đổi `.gitignore`, CI và chữ tài liệu.

- `.gitignore` chặn thêm `*.zip` (gói giọng của `export --personal`) và video `*.mp4 *.mkv *.mov
  *.webm`: làm theo ví dụ README rồi `git add .` không còn đẩy giọng thật lên repo. Bước CI
  "No audio or model binaries committed" chặn cùng các đuôi đó.
- `.gitignore` bỏ qua thư mục công cụ agent `/.claude/ /.codex/ /.gemini/` (manifest
  `.claude-plugin/`, `.codex-plugin/` vẫn được theo dõi) và cache công cụ Python `.mypy_cache/
  .ruff_cache/ .coverage htmlcov/ .hypothesis/`, cùng `.python-version`, `.envrc`.
  `tests/test_repo_gates.py` có ca cho từng dòng.
- Tài liệu hết ghi macOS "chưa kiểm": số đo thật trên một máy M1 16 GB ngày 30/09/2026 (MPS, fp16,
  `doctor` 16 PASS, `speak` mã 0, RTF 1,65 với `--instruct`, 2,7–4,8 với profile clone).
  `.env.example` ghi weights ~3,3 GB (thay "~4 GB"), torch CUDA ~2,5 GB / macOS arm64 ~130 MB.
- CI: `actions/checkout` v5.1.0, `actions/setup-python` v6.3.0 (chạy Node 24 thay Node 20 đã bị
  GitHub báo lỗi thời), vẫn ghim SHA đầy đủ.

## 0.3.1 — 2026-09-30

**Chạy ổn trên Mac mini (máy embedded), Windows giữ nguyên.**

- `doctor` dòng `bgm-library` giờ kiểm cả **file nhạc**: style khai trong `bgm-library.json` mà
  thiếu `<style>.mp3` là `[WARN]` kèm tên style thiếu — trước đây chỉ kiểm file json, và pipeline
  chọn đúng style đó chết ở bước ghép sau khi đã tốn cả lượt tổng hợp. Repo không có lệnh sinh
  nhạc; cách tự sinh (và giấy phép CC-BY-NC của weights MusicGen) ở `docs/bgm-generation.md`.
- Tên profile so theo Unicode **NFC**: file tên có dấu ở dạng NFD (chép từ gói/máy khác) giờ khớp
  tên viết trong cấu hình; `list_profiles()` / `get_default()` trả tên NFC. Không đổi tên file nào.
- Luật cài package có thêm dòng **máy embedded**: giọng cài vào venv của repo video thì luôn
  `pip install -e` (trùng `agent-video-studio/INSTALL.md` mục 5b); bản sao chỉ dành cho xưởng
  Windows chạy lịch có trạm giọng riêng. `docs/INSTALL.md` mục 3.
- `voice-studio init` nhận ra khi `voice_studio` đang chạy từ venv của dự án khác (vd `.venv` của
  repo video): không còn bảo tạo `<trạm>/omnivoice/.venv` hay tải lại weights đã có trong cache.
- Tài liệu cài: macOS dùng `python3.12` (không phải `python3` = 3.9), ghi chú uv/pyenv; dung lượng
  tách theo máy — torch CUDA ~2,5 GB, macOS arm64 ~130 MB, weights ~3,3 GB.
- JSON của `speak`, `narrate`, `doctor` (và `get_status` của MCP) thêm khoá `version` = phiên bản
  package; `voice_studio` **vẫn** là phiên bản hợp đồng (`API_VERSION`, nay `1.1.0` vì thêm khoá —
  không phá khoá cũ). Bên gọi ghim theo `voice_studio`, truy lỗi theo `version`.

## 0.3.0 — 2026-09-29

**Cài đặt cho agent, hai hệ điều hành.**

- `INSTALL.md` ở gốc repo: hướng dẫn dành cho AI agent (Windows và macOS) kèm prompt copy-dán
  tiếng Việt và tiếng Anh. Agent phải hỏi trước khi cài phần mềm, tải engine, hay chọn chỗ đặt trạm.
- `START-HERE.md`, `AGENTS.md` (+ `CLAUDE.md`, `GEMINI.md` trỏ về), `hosts/` cho Claude Code, Codex,
  Antigravity, Claude Desktop; `docs/troubleshooting.md`; trang web `/install/`.
- **Trạm mặc định là `<repo>/workspace/`** khi không đặt biến nào — không còn tự chọn `~/.voice`.
  `~/.voice` chỉ được dùng khi bạn đã chọn nó hoặc nó đã là một trạm. Cài dạng wheel mà chưa đặt
  `VOICE_STATION`: lệnh cần trạm dừng với mã 3 kèm cách đặt.
- Lệnh mới `voice-studio uninstall`: gỡ package và hook `pre-commit`, **giữ** trạm và giọng;
  `--dry-run` để xem trước.
- `doctor` có bốn trạng thái `PASS` / `WARN` / `FAIL` / `NOT_CHECKED`; JSON thêm mức
  `not_checked` và danh sách `not_checked` (các mức cũ giữ nguyên tên). Dòng mới `samples` và
  `synthesis`.
- `samples/`: một câu tiếng Việt ngắn ở dạng thô (4 bẫy phát âm đã đo) và dạng viết lại, cùng hình
  dạng JSON của `speak --json`. Doctor xác minh offline.
- Sửa: tài liệu từng bảo `OMNIVOICE_ONLINE=1 voice-studio doctor` để tải weights — doctor không
  bao giờ tải gì; lần tổng hợp đầu mới tải. Lệnh `init` in ra giờ đúng cú pháp PowerShell trên
  Windows.
- Phần phụ `engine` giữ `transformers` trong khoảng đã chạy thật (`>=5.10.2,<5.18`), không ghim
  cứng một số; cài engine bằng `pip install "<repo>[engine]"`. Doctor in phiên bản transformers và
  `[WARN]` khi nó nằm ngoài khoảng.
- Cài package có **một** luật, ở `docs/INSTALL.md` mục 3: máy phát triển `pip install -e`, máy
  chạy lịch cài **bản sao** (không `-e`) để sửa hay `git pull` repo không đổi lượt đang chạy; có
  lệnh Windows và macOS. `voice-studio update` trên bản sao in lại lệnh cài để mã mới vào venv.

## 0.2.0 — 2026-09-22

**Engine thành package, clone là chạy.**

- Engine giọng thành package cài được `voice_studio` với lệnh `voice-studio`; mã thoát là hợp đồng
  (`2` cấu hình sai, `3` thiếu engine) và một dòng JSON cuối stdout.
- `embedded` là chế độ mặc định: clone repo rồi chạy là đường bình thường. Trạm và bí mật nằm đâu,
  chuyển thế nào: `voice-studio migrate`.
- Cứng hơn: nhập gói từ chối thành phần mang ký tự ổ đĩa ở bất kỳ đoạn nào và kiểm lại sau khi
  phân giải đường thật; xuất gói từ chối thứ trông như bí mật; ba biến môi trường không còn lặng
  lẽ trỏ trạm đi chỗ khác.
- CI chạy trên Windows và macOS.

## 0.1.0 — 2026-08-26

Bản đầu: bộ công cụ tạo và quản lý giọng cho AI agent — đào sắc thái từ bản ghi dài, sáu cổng
kiểm clip tham chiếu, profile nhiều sắc thái điều khiển bằng marker, bảng phát âm tiếng Việt đã đo.
