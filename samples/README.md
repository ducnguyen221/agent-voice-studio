# Bài mẫu — một câu, hai dạng, một hợp đồng

Thư mục này là **bài thử đầu tiên** sau khi cài, và là thứ `voice-studio doctor` xác minh mà
không cần mạng, torch hay model. Nó **không chứa audio** — repo không bao giờ chứa audio.

| File | Là gì |
|---|---|
| `cau-ngan.txt` | văn bản **thô**, cố ý chứa bốn bẫy phát âm đã đo |
| `cau-ngan.script.txt` | cùng câu **viết lại** theo [`vietnamese-tts-script.md`](../skills/voice-routing/references/vietnamese-tts-script.md) — không còn bẫy |
| `speak-expected.json` | **hình dạng** dòng JSON mà `voice-studio speak --json` in ra (khoá cố định; số là ví dụ) |

## Kết quả kỳ vọng (cố định)

**1. Soát bẫy — chạy ở mọi máy, không cần engine.** `voice_studio.samples.traps()` phải thấy
đúng **4 bẫy** trong bản thô và **0** trong bản viết lại:

| Bẫy | Trong bản thô | Viết lại thành | Vì sao (đã đo) |
|---|---|---|---|
| `gio` | `14:30` | `14 giờ 30` | dấu `:` bị nuốt, mất chữ "giờ" |
| `ngay` | `22/8/2026` | `22 tháng 8 năm 2026` | dấu `/` bị nuốt |
| `phien-ban` | `GPT 5.2` | `GPT phiên bản 5.2` | viết tắt dính số đọc thành "GPT-52" |
| `ten-mien` | `Z.ai` | `Z chấm AI` | đọc thành "Z đây" |

`2.436` (dấu chấm hàng nghìn) và `15%` đọc đúng — cố ý để nguyên, bài mẫu kiểm cả việc **không**
sửa thừa. Dòng `samples` của `voice-studio doctor` là `[PASS]` khi cả hai điều trên đúng.

**2. Đọc thành tiếng — chỉ khi đã cài engine và có một profile giọng.**

```
voice-studio speak --file samples/cau-ngan.script.txt --out <trạm>/out/cau-ngan.wav --seed 1234 --json
```

| Mã thoát | Nghĩa | Việc cần làm |
|---|---|---|
| `0` | có file audio | nghe thử; dòng JSON cuối stdout có đúng các khoá trong `speak-expected.json` |
| `1` | engine lỗi giữa chừng (hết bộ nhớ GPU…) | chạy lại; vẫn lỗi thì đọc stderr |
| `2` | gọi sai: chưa có profile mặc định, text rỗng | tạo profile hoặc truyền `--profile` |
| `3` | chưa có trạm / chưa cài torch hay engine | `voice-studio doctor`, làm tiếp phần còn thiếu |

Thời lượng câu này khoảng **5–8 giây** — ước lượng để nhận ra kết quả vô lý (0 giây, vài phút),
**không phải** cổng kiểm: tốc độ đọc tuỳ giọng. Audio ra nằm trong trạm (`<trạm>/out/`), không
bao giờ trong repo; `.gitignore` chặn mọi `*.wav` / `*.mp3`.
