---
title: Install
summary: Install voice-studio on a new machine - prerequisites, which venv, the two station modes, the .env template, and where the engine-specific steps live.
audience: anyone setting the voice studio up on a new machine
---

# Cài `voice-studio` (Windows · macOS · Linux)

Repo mang **phương pháp và mã**; giọng, nhạc nền và output sống ở **trạm giọng** — ngoài git.
Cài xong thì `voice-studio doctor` phải xanh.

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

> **Ngoại lệ có chủ đích:** luật đẻ repo của hệ này khuyên *không* dùng `pip install -e`. Ở đây
> dùng, vì repo phải chạy bằng chính venv của engine và `-e` giữ cho `git pull` là đủ để cập nhật.
> Đổi lại: `voice-studio update` chỉ là `git pull --ff-only`, không bao giờ `clean`.

## 3. Cài package

```
git clone https://github.com/ducnguyen221/agent-voice-studio
cd agent-voice-studio
pip install -e .          # trong venv engine — lệnh voice-studio
voice-studio --version
```

### Phần phụ

```
pip install -e ".[engine]"   # engine tổng hợp (omnivoice, bản ghim)
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
pip uninstall agent-voice-studio
```

Trạm **không bị đụng tới**: nó là dữ liệu của bạn. Muốn xoá thì xoá thư mục trạm — sau khi đã
`voice-studio backup`.

## 8. Nền tảng: cái gì đã chạy thật

| Nền tảng | Bộ khung (CLI, trạm, test) | Tổng hợp giọng thật |
|---|---|---|
| Windows | đã chạy thật | đã chạy thật |
| macOS (Apple Silicon) | CI chạy mỗi lần đẩy mã: cài gói, `--help`, `init` cả hai chế độ, toàn bộ test | **chưa kiểm** — test trên CI dùng module engine **giả**; engine thật trên MPS chưa ai chạy qua package này |
| Linux | CI chạy cổng kiểm repo | **chưa kiểm** |

Thứ đã được chứng minh trên mọi nền tảng là **bộ khung**: lệnh chạy, trạm dựng đúng, hợp đồng gọi
giữ nguyên. Phần tổng hợp giọng mới chỉ có số đo thật trên Windows — đừng đọc bảng này rộng hơn
thứ nó nói.
