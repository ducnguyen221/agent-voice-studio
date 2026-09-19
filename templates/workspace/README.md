# Trạm giọng

Thư mục này là **trạm giọng** của bạn: nơi chứa engine (venv), giọng của riêng bạn, nhạc nền và
output. Repo `agent-voice-studio` chỉ chứa mã; mọi thứ ở đây là của bạn và **không bao giờ vào git**.

Cây do `voice-studio init` dựng từ `templates/workspace/` của repo. Giải thích từng thư mục —
cái nào là nội dung, cái nào là quản lý, cái nào được sao lưu, cái nào xoá được — ở
`docs/WORKSPACE.md` của repo.

```
station.json          cấu hình trạm (hợp đồng, venv, thư mục engine, thư viện nhạc nền)
omnivoice/.venv/      venv engine — bạn tự tạo theo lệnh `init` in ra
omnivoice/voices/     kho profile giọng: <tên>.wav + <tên>.txt, _default.txt
assets/bgm/           thư viện nhạc nền: bgm-library.json + <style>.mp3
out/                  output và nháp (VOICE_STUDIO_WORK)
cache/                cache dựng lại được
```

Kiểm trạm: `voice-studio doctor`. Sao lưu: `voice-studio backup --out <file.zip>`.
Chuyển máy: `voice-studio export --personal --out <file.zip>` rồi `voice-studio import` ở máy mới.
