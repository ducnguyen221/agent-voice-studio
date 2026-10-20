# Lịch sử phát hành

Mới nhất trước. Mỗi mục là thứ **người dùng** thấy khác đi; chi tiết từng thay đổi nằm trong lịch
sử git. Số phiên bản ở đây, trong `pyproject.toml`, `voice_studio/__init__.py` và ba manifest
plugin luôn cùng một số — `tests/test_version_sync.py` đỏ nếu lệch.

## 0.5.0 — 2026-10-20

**Sửa lỗi dời trạm:** lỗi sau bước dời dữ liệu được hoàn tác theo trạng thái đã xác minh; nếu trạng thái không rõ hoặc phục hồi thất bại thì giữ dữ liệu và báo cách phục hồi, không dọn rộng.

**Đổi bố cục và đổi cách hỏi.**

- **Tên thư mục trạm thống nhất.** Gốc luôn tên `workspaces`; trạm giọng khi cài cạnh OpcOS là
  `<OPCOS_WORKSPACES>/voice`, còn cài riêng lẻ thì trạm là chính `<repo>/workspaces/` (đã nằm trong
  repo nên không thêm `voice`). Trạm nhúng cũ tên số ít `<repo>/workspace/` vẫn dùng được: nếu nó đã là
  một trạm mà `workspaces/` chưa có thì được nhận kèm một dòng nhắc đổi tên (không tự dời); có cả hai
  thì `workspaces/` thắng và có dòng nhắc. `init` mới không bao giờ tạo tên số ít; `doctor` có dòng
  `legacy-workspace` nhắc.
- `studio.local.json` do `init` embedded ghi (`station_path: workspace` hoặc `workspaces`) không còn được
  tin theo chữ: trạm nhúng luôn được phân giải bằng một luật chung (đổi tên thư mục theo gợi ý không làm mất
  trạm; có cả hai thì `workspaces` thắng và có nhắc). `init` embedded ghi lại `station_path: workspaces`.
  Cây mẫu của repo cũng đổi từ `templates/workspace/` sang `templates/workspaces/`.
- Thư mục trạm cũ ẩn trong thư mục cá nhân không còn được tự nhận; trỏ vào bằng `--station <đường>`.
- **Đổi hành vi — máy có `OPCOS_WORKSPACES`: `init --yes` và chạy không có người ra `<biến>/voice`** (trước
  đây `--yes` ra `<repo>/workspaces/` và chạy không người thoát mã 2). Đã mang dấu thì dùng thẳng, không
  in gì; chưa thì dựng ở đó và in một dòng nêu đường cùng cách đổi (`--station <đường>`). **Muốn giữ trạm
  trong repo như trước: `init --mode embedded --yes`.** Windows `< NUL` hay pipe hết dữ liệu ở câu hỏi đường
  khi máy có biến nay ra `<biến>/voice` (không còn mã 2); máy không có biến vẫn thoát mã 2, không đoán.
- **Trạm nhúng cũ có dữ liệu được giữ, không bị biến đè.** Nếu `<repo>/workspaces/` (hay `workspace/` tên cũ)
  đã là một trạm mà chưa ghi lựa chọn, `init` không dựng trạm rỗng cạnh nó: `--yes`, chạy không người, Enter
  hay hết dữ liệu ⇒ giữ trạm cũ, ghi `embedded` và in một dòng cách dời sau (`migrate --to separate`); có
  người ngồi đó thì được hỏi một câu giữ/chuyển — gõ `chuyen` (hay `chuyển`, `c`) để dời vào `<biến>/voice`
  (vẫn hỏi y/N trước khi dời; đích không rỗng ⇒ mã 2 trước khi hỏi; `--dry-run` chỉ in kế hoạch). Bố cục có
  cả `workspace/` đã có dữ liệu lẫn `workspaces/` mới chưa dấu: giữ `workspaces/` kèm dòng nhắc gộp, không hỏi.
- `init`: có `OPCOS_WORKSPACES` và có người trả lời thì hỏi đúng một câu nhận đường (Enter = `<biến>/voice`,
  kể cả khi trạm đó đã có sẵn); gõ `1`, `2`, `embedded` hay `separate` ở câu này là mã 2 (trước đây
  tạo thư mục `<thư mục hiện tại>/1`). Không có biến thì câu hỏi hai đường (Enter = `<repo>/workspaces/`,
  nhãn in đúng đường) và `--non-interactive` thiếu cả `--yes` lẫn `--mode` vẫn thoát mã 2.
- `OPCOS_WORKSPACES` (hay `<biến>/voice`) trỏ vào một file giờ thoát mã 2 nêu tên biến, trước mọi thao tác
  ghi (trước đây mã 1 kèm traceback).
- `OPCOS_WORKSPACES` có dấu nháy dính vào giá trị (kiểu `setx` kèm nháy), có ký tự không hợp lệ trong đường
  dẫn (Windows), hoặc trỏ vào chính một trạm (thay vì thư mục CHA chứa các trạm) giờ thoát mã 2 nêu tên biến,
  chưa ghi gì — không còn mã 1 kèm traceback hay trạm lồng trong trạm. Gốc workspaces thông thường (không có
  `station.json`/`omnivoice/voices/`) không bị chặn.
- Ctrl+C ở bất kỳ lệnh `voice-studio` nào giờ thoát **mã 2** với đúng một dòng `đã huỷ (Ctrl+C)` (kèm dòng
  JSON lỗi khi có `--json`), không còn traceback.
- `separate` không còn đường mặc định ở thư mục cá nhân. `--mode separate` khi `OPCOS_WORKSPACES` đặt: đích là
  `<biến>/voice` (tuyệt đối, kể cả khi chưa là trạm) — nếu thư mục đó đã mang dấu trạm thì dùng thẳng,
  không hỏi; nếu chưa, có người thì hỏi xác nhận/đổi, không có người thì (kể cả `--yes`) dùng luôn và in
  một dòng. Không đặt biến: có người thì hỏi đường, không thì dừng mã 2. `--station` trỏ vào một file
  giờ thoát mã 2 thay vì lỗi hệ điều hành.
- `migrate --to separate` (nguồn là `<repo>/workspaces/`, hoặc tên số ít cũ nếu chỉ có nó) thiếu
  `--station` thì **hỏi nơi dời** (gợi ý `<OPCOS_WORKSPACES>/voice` nếu có), hiện đường tuyệt đối cùng
  số file và dung lượng (KB/MB) rồi xin xác nhận y/N; không có người trả lời (hoặc `--non-interactive`)
  thì dừng mã 2. Từ chối đích là file hoặc nằm trong chính thư mục đang dời; đường dán kèm ngoặc kép
  ('Copy as path') được bóc ở mọi chỗ nhập đường.

## 0.4.0 — 2026-10-18

**Đổi hành vi (bỏ tầng `home`):** các lệnh không còn tự nhận `~/.voice` chỉ vì nó đã có
`station.json` / `omnivoice/voices/`. Thứ tự tìm trạm: `--station` → `VOICE_STATION` →
`OMNIVOICE_DIR` → `studio.local.json` → `<repo>/workspace/`. Máy còn `~/.voice` thật mà chưa cấu
hình phải đặt `VOICE_STATION` hoặc chạy `voice-studio init` (`init` phát hiện `~/.voice` đã là trạm thì tự nhận làm trạm separate, không hỏi — kể cả `--yes`).
`doctor` bỏ dòng `station-source`. Thêm: `init` đề xuất và `doctor` nhắc trạm `voice/` trong
`OPCOS_WORKSPACES` (tuỳ chọn; `init --yes` không tự nhận, resolver không đọc biến này).

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
