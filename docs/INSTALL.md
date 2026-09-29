---
title: Install
summary: Install voice-studio on a new machine - prerequisites, which venv, the two station modes, the .env template, and where the engine-specific steps live.
audience: anyone setting the voice studio up on a new machine
---

# Cài `voice-studio` (Windows · macOS · Linux)

Repo mang **phương pháp và mã**; giọng, nhạc nền và output sống ở **trạm giọng** — ngoài git.
Cài xong thì `voice-studio doctor` phải xanh.

> **Nhờ AI agent cài?** Agent làm theo [`INSTALL.md`](../INSTALL.md) ở gốc repo (luật an toàn,
> Windows và macOS, prompt copy-dán). File này là bản chi tiết cho người tự cài; bản rút gọn ở
> [`START-HERE.md`](../START-HERE.md), gỡ vướng ở [`troubleshooting.md`](troubleshooting.md).

> **Một tài liệu, một việc.** File này là đường vào: thứ tự các bước, chọn venv, chọn chế độ
> trạm. Phần **engine** (torch theo hệ điều hành, `omnivoice`, weights, biến môi trường, số đo
> Apple Silicon) nằm ở
> [`skills/voice-routing/references/install-omnivoice.md`](../skills/voice-routing/references/install-omnivoice.md)
> và **chỉ** nằm ở đó — đừng chép sang đây, hai bản sẽ trôi khỏi nhau.

## 1. Thứ phải có trước

| Thứ | Vì sao | Windows | macOS |
|---|---|---|---|
| **Python ≥ 3.10** | chính package này (đã đo trên 3.12) | `winget install Python.Python.3.12` | `brew install python@3.12` |
| **ffmpeg + ffprobe** | xuất mp3, ghép tiếng vào video, chuẩn âm lượng | `winget install Gyan.FFmpeg` | `brew install ffmpeg` |
| **torch** | engine chạy trên nó — bản phải khớp phần cứng | xem tài liệu engine | xem tài liệu engine |
| **~4 GB đĩa** | weights tải về cache lần chạy đầu | | |

Không nằm trên PATH thì đặt `FFMPEG_DIR` trỏ thư mục chứa ffmpeg/ffprobe.

GPU **NVIDIA** cho tốc độ dùng được; Apple Silicon chạy qua **MPS**; CPU chạy được nhưng chậm tới
mức đổi cả cách làm việc.

## 2. Cài vào venv nào — câu hỏi quan trọng nhất của phần này

| Bạn định làm gì | Cài vào đâu |
|---|---|
| Tổng hợp giọng thật (mọi việc có tiếng) | **venv của engine**, đường chuẩn `<trạm>/omnivoice/.venv` — nơi đã cài torch |
| Chỉ `init` / `doctor` / đọc tài liệu | venv nào cũng được |
| Trạm **video** cũng phải lồng tiếng | cài `agent-video-studio` vào **cùng venv engine** này |

Lồng tiếng đi qua một lần `import voice_studio` **trong cùng tiến trình**: model nặng hàng GB, nạp
một lần cho cả bài. Hai venv khác nhau thì không có đường nào để import, và lỗi hiện ra ở giữa lượt
chạy chứ không phải lúc cài.

## 3. Cài package — `-e` hay bản sao

**Đây là chỗ DUY NHẤT quy định cách cài package.** README, `INSTALL.md` ở gốc và tài liệu engine
chỉ trỏ về đây.

| Máy của bạn | Cài | Vì sao |
|---|---|---|
| **Máy phát triển** — bạn sửa repo, hoặc tự gọi lệnh bằng tay | `pip install -e` | sửa mã hay `git pull` là có hiệu lực ngay, không phải cài lại |
| **Máy chạy lịch** — scheduled task, cron, launchd gọi `voice-studio` khi không có ai ngồi đó | **bản sao**: `pip install` không `-e` | lượt đang chạy dùng bản đã cài, không đọc mã bạn đang sửa dở hay vừa `git pull`; mã mới chỉ vào khi bạn **chủ động cài lại** |

Không chắc thì dùng `-e`. Máy vừa phát triển vừa chạy lịch: cho lịch một venv engine riêng cài bản
sao, đừng dùng chung venv `-e`.

### Máy phát triển (`-e`)

```
git clone https://github.com/ducnguyen221/agent-voice-studio
cd agent-voice-studio
pip install -e .          # trong venv engine — lệnh voice-studio
voice-studio --version
```

`voice-studio update` chỉ là `git pull --ff-only`, không bao giờ `clean`; với `-e` thì thế là đủ.

### Máy chạy lịch (bản sao)

Cài vào **python của venv engine** (`<trạm>/omnivoice/.venv`), kèm phần phụ `engine`.

Windows (PowerShell):

```powershell
$py = "<trạm>\omnivoice\.venv\Scripts\python.exe"
& $py -m pip install "<repo>[engine]"
& $py -m voice_studio --version
```

macOS (sh/zsh):

```sh
py="<trạm>/omnivoice/.venv/bin/python"
"$py" -m pip install "<repo>[engine]"
"$py" -m voice_studio --version
```

Bản sao **không biết bản clone nằm đâu**. Đặt biến người dùng `VOICE_STUDIO_REPO=<repo>` — cần cho
trạm `embedded`, cho `voice-studio update`, cây mẫu của `init` và bài mẫu của `doctor`. Trạm
`separate` đã có `VOICE_STATION` thì vẫn chạy được không cần nó; thiếu cả hai thì lệnh cần trạm
dừng mã 3. Trên macOS, lịch `launchd` không đọc `~/.zprofile`: khai biến trong mục
`EnvironmentVariables` của plist.

**Cập nhật máy chạy lịch** — làm ngoài giờ lịch chạy:

```
voice-studio update                       # git pull --ff-only trên bản clone
<python venv engine> -m pip install "<repo>[engine]"   # nạp mã mới vào venv — bước này mới có hiệu lực
```

pip luôn cài lại từ thư mục cục bộ kể cả khi số phiên bản không đổi. `update` trên bản sao tự in
lại lệnh cài để bạn không quên bước hai.

### Phần phụ

```
pip install -e ".[engine]"   # engine tổng hợp (omnivoice ghim, transformers trong khoảng đã đo)
pip install -e ".[lab]"      # bộ đào giọng đa sắc thái (librosa, scikit-learn)
pip install -e ".[mcp]"      # chạy như MCP server cho agent
pip install -e ".[ui]"       # giao diện web cục bộ
pip install -e ".[clone]"    # dựng profile từ media dài / URL
pip install -e ".[test]"     # chạy test
```

Danh sách phần phụ là nguồn duy nhất ở `pyproject.toml`; một cổng trong bộ test đối chiếu nó với
mã, nên bảng này không trôi được mà không ai thấy.

## 4. Dựng trạm

```
voice-studio init                       # trình bảng hai lựa chọn rồi chờ bạn chọn
voice-studio init --dry-run             # chỉ in ra sẽ làm gì
voice-studio init --station ~/.voice    # chọn thẳng separate, không hỏi
voice-studio init --station <trạm cũ> --existing   # nhận trạm đang chạy: chỉ ghi station.json
```

**`embedded` là mặc định và là khuyến nghị**: trạm ở `<repo>/workspace/`, biến cấu hình ở
`<repo>/.env`, bấm Enter là xong, không phải đặt biến môi trường nào. Chọn **`separate`** khi bạn
dùng nhiều máy, rành kỹ thuật, hoặc repo này là bản public của chính bạn — tức là trạm phải sống
lâu hơn bản clone.

Không có ai trả lời (CI, scheduled task) mà chưa chọn ⇒ `init` in bảng lựa chọn rồi thoát
**mã 2, chưa ghi byte nào**. Agent cài phải đưa bảng đó cho người dùng xem, **không tự chọn im
lặng**.

`init` dựng `station.json` và cây trạm (`omnivoice/voices/`, `assets/bgm/`, `out/`, `cache/`). Nó
**không** tạo venv và **không** tải model — chỉ in lệnh. Từng thư mục giải thích ở
[`WORKSPACE.md`](WORKSPACE.md).

### `.env` ở chế độ embedded

`init` chép `.env.example` (khuôn tên biến, không có giá trị) thành `<repo>/.env` cho bạn điền;
chạy lại **không đè** file bạn đã điền. Thứ tự đọc một biến: **biến môi trường thật → `<repo>/.env`
(chỉ khi `mode = embedded`) → chưa đặt**.

`.env` giữ **đường dẫn và cấu hình**, **không bao giờ** giữ token. Cả `workspace/` lẫn `.env` bị
`.gitignore` chặn, và hook `pre-commit` chặn lần nữa. Một biến mà mã đọc nhưng khuôn không khai là
**test đỏ**: người dùng không thể biết mình phải điền gì nếu không ai kể.

Biến nào **phải** là biến môi trường thật (không đọc được từ `.env`) được đánh dấu
`[MÔI TRƯỜNG THẬT]` ngay trong khuôn, kèm lý do. Bảng đầy đủ các biến: tài liệu engine ở mục 1.

## 5. Kiểm

```
voice-studio doctor
```

Mã 3 ⇒ đọc phần thiếu rồi cài tiếp. Lần đầu cần mở mạng đúng một lần để tải weights — cách làm ở
tài liệu engine; các lần sau engine chạy **offline** theo mặc định để lịch chạy không treo vì mạng.

## 6. Chuyển máy

```
voice-studio export --personal --out <ngoài trạm>/voice.zip   # giọng + nhạc nền + station.json
voice-studio import <voice.zip>                                # ở máy mới, sau khi đã init
voice-studio backup --out <ngoài trạm>/station.zip             # sao lưu cả trạm
```

Gói `--personal` **không** mang venv, cache hay output. Đặt file zip **ngoài trạm** để lần sao lưu
sau không gói chính nó.

## 7. Gỡ

```
voice-studio uninstall --dry-run     # xem trước: gỡ gì, giữ gì
python -m voice_studio uninstall --yes
```

`uninstall` gỡ hook `pre-commit` do `init` cài (chỉ khi đúng là hook của nó) và
`pip uninstall agent-voice-studio` khỏi venv đang chạy; in lệnh gỡ plugin của từng host (repo
không tự ghi cấu hình host nên cũng không tự xoá). Gọi qua `python -m` để trên Windows tiến trình
không giữ khoá file `voice-studio.exe` đang bị gỡ. `--keep-package` chỉ gỡ hook.

Trạm, `.env`, `studio.local.json` **không bị đụng tới**: chúng là dữ liệu của bạn. Muốn xoá thì
xoá thư mục trạm — sau khi đã `voice-studio backup`.

## 8. Nền tảng: cái gì đã chạy thật

| Nền tảng | Bộ khung (CLI, trạm, test) | Tổng hợp giọng thật |
|---|---|---|
| Windows | đã chạy thật | đã chạy thật |
| macOS (Apple Silicon) | CI chạy mỗi lần đẩy mã: cài gói, `--help`, `init` cả hai chế độ, toàn bộ test | **chưa kiểm** — test trên CI dùng module engine **giả**; engine thật trên MPS chưa ai chạy qua package này |
| Linux | CI chạy cổng kiểm repo | **chưa kiểm** |

Thứ đã được chứng minh trên mọi nền tảng là **bộ khung**: lệnh chạy, trạm dựng đúng, hợp đồng gọi
giữ nguyên. Phần tổng hợp giọng mới chỉ có số đo thật trên Windows — đừng đọc bảng này rộng hơn
thứ nó nói.
