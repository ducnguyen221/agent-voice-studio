# Thư viện nhạc nền

Thư mục này chứa nhạc nền dùng chung cho mọi pipeline gọi trạm giọng.

- `bgm-library.json` — danh sách style, style mặc định, âm lượng trộn (mặc định 0.10).
- `<style>.mp3` — một file cho mỗi style, **tên file trùng `name`** trong json.

Repo không phát hành file nhạc nào. Hai cách có nhạc:

1. **Tự sinh bằng MusicGen** (công cụ ở `extras/musicgen/` của repo): sinh mỗi style một bản
   ~60 giây, lưu thành `<style>.mp3` ở đây. Kiểm lại giấy phép weights của MusicGen trước
   khi dùng cho mục đích thương mại.
2. **Dùng nhạc bạn có quyền dùng** — đổi tên thành `<style>.mp3` và khai trong json.

Kiểm: `python -m voice_studio.bgm list` phải liệt kê đủ style, không báo thiếu file.
