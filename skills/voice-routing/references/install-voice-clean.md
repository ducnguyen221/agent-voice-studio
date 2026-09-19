# Làm sạch bản ghi — và khi nào không nên

Chỉ dành cho bản ghi có **nhạc hoặc tạp âm nằm dưới giọng nói**. Chuỗi hai tầng: tách giọng
khỏi mọi thứ còn lại, rồi khử nhiễu và khử vang phần giọng còn lại.

- **Tầng 1** — `python-audio-separator` (MIT), model BS-Roformer, tách giọng ra khỏi bản mix.
- **Tầng 2** — `ClearerVoice-Studio` (Apache-2.0), model tăng cường tiếng nói 48 kHz, khử nốt
  tạp âm và tiếng vang phòng.

Công cụ: `voice-studio clean` (mã ở `voice_studio/clean/clean_voice.py` và
`voice_studio/clean/cv_enhance.py`). Lệnh cài chi tiết, vị trí thư mục công cụ và cách chuyển
model sang máy khác: `voice_studio/clean/README.md`.

---

## Quyết định trước khi cài

Đo nguồn trước:

- **Nền nhiễu (noise floor).** Khoảng −60 dB hoặc thấp hơn, có khoảng lặng thật giữa các câu
  → đã sạch.
- **Khoảng lặng.** Âm thanh liền mạch, *không* có khoảng lặng nào ở ngưỡng −45 dB nghĩa là có
  thứ gì đó đang phát bên dưới.

**Không làm sạch audio đã sạch.** Các model này làm mượt, và làm mượt xoá đi chính chất giọng
bạn đang muốn giữ. Một nguồn đo được −67 dB đã được cố ý để nguyên và cho ra một trong những
profile tốt hơn cả.

**Đo ở nhiều điểm.** Bản ghi dài thường lẫn lộn — nửa đầu có nhạc, nửa sau sạch. Đoạn sạch thì
không cần làm sạch gì cả, vừa nhanh hơn *vừa* tốt hơn.

## Bẫy khi cài: hai môi trường ảo, không phải một

Hai tầng có **phụ thuộc không thể dung hoà**. Một bên cần một major version numpy mà bên kia
ghim chặn (tầng 1 cần numpy ≥ 2, tầng 2 cần numpy < 2), kèm xung đột phiên bản của một thư viện
phụ trợ dùng chung. Cài chung một chỗ, pip lặng lẽ hạ phiên bản và tầng 1 hỏng — không có lỗi
nào rõ ràng.

Dựng **hai venv riêng**; tầng 1 gọi tầng 2 dưới dạng tiến trình con. Đây không phải chuyện gọn
gàng; đó là cách sắp xếp duy nhất chạy được. Không cài chung vào venv của engine giọng.

| Tầng | Venv | Python trong venv (Windows) | Python trong venv (macOS / Linux) |
|---|---|---|---|
| 1 — tách giọng | `.venv-sep` | `.venv-sep/Scripts/python.exe` | `.venv-sep/bin/python` |
| 2 — tăng cường | `.venv-cv` | `.venv-cv/Scripts/python.exe` | `.venv-cv/bin/python` |

```bash
python -m venv <dir>/.venv-sep    # tách giọng
python -m venv <dir>/.venv-cv     # tăng cường
```

`<dir>` là thư mục công cụ làm sạch, nằm **ngoài repo**: `--clean-dir` → biến
`VOICE_CLEAN_DIR` → `$VOICE_STATION/voice-clean` → `~/.voice/voice-clean`. Lệnh `pip install`
đầy đủ cho từng venv ở `voice_studio/clean/README.md`.

Mỗi venv có bản torch riêng. Dự trù vài GB cho mỗi môi trường. `voice-studio clean` tự chạy lại
bằng python của `.venv-sep` nếu venv hiện tại không có `audio-separator`, và gọi tầng 2 bằng
python của `.venv-cv` — người dùng không phải tự chuyển venv.

Trên macOS: **[chưa kiểm]** — bộ lệnh cài chưa được chạy thật trên máy Mac; nếu `clearvoice`
không có bản dựng sẵn cho arm64 thì xem trang dự án của nó trước khi cài.

## Model không nằm trong repo

Lần chạy đầu cần mạng: tầng 1 tải checkpoint vào `<dir>/models/`, tầng 2 tải vào
`<dir>/checkpoints/`. Các lần sau chạy offline. Chuyển máy thì chép nguyên hai thư mục này
sang, không cần tải lại. Không bao giờ commit file model vào repo.

## Hai cái bẫy nữa, nên biết trước khi dính

**Ghim phụ thuộc lỏng có thể làm hỏng bộ tách.** Một khoảng phiên bản quá rộng đã để lọt một
major version của thư viện audio, bản này bỏ mất một keyword argument mà bộ tách vẫn dùng — tách
xong xuôi rồi chết lúc ghi file, với thông báo nói về file output bị thiếu chứ không nói gì về
thư viện. Ghim phụ thuộc đó dưới major gây vỡ, và kiểm lại chỗ ghim sau mỗi lần nâng cấp.

**Model tăng cường có thể phân giải checkpoint theo thư mục làm việc hiện tại.** Chạy nó từ chỗ
khác là nó tải lại vài trăm MB vào bất kỳ thư mục nào bạn đang đứng. Ép thư mục làm việc trước
khi gọi: `cv_enhance.py` nhận `--workdir` và `chdir` vào đó, còn `voice-studio clean` luôn
truyền `--workdir` trỏ về thư mục công cụ.

## Tốc độ xử lý

Khoảng **0,25–0,4× realtime trên GPU tầm trung** — một giờ audio mất mười lăm đến hai mươi lăm
phút. Chạy tuần tự, không song song: cả hai tầng đều cần GPU, chạy chồng lên nhau còn chậm hơn.

## Kiểm tra việc làm sạch có hiệu quả

Đừng tin vào chuyện không có lỗi. Đo lại:

- **Khoảng lặng phải xuất hiện trở lại.** Trong một trường hợp, một bản đọc truyện kinh dị từ
  *không* khoảng lặng nào trong mẫu hai phút lên **mười chín** — nền đã thật sự biến mất.
- **RMS gần như không đổi.** Đo được −18,1 dB trước, −18,1 dB sau. Tụt mạnh nghĩa là giọng bị
  giảm theo cùng tạp âm, và clip giờ tệ hơn chứ không tốt hơn.

Sau đó nghe một cặp trước/sau ngắn. Kiểm bằng máy chỉ xác nhận tạp âm đã đi; chỉ con người mới
xác nhận được *chất giọng* còn giữ — và với chất liệu biểu cảm như tiếng hét hay giọng kể thì
thầm, đó chính là thứ đang bị đe doạ.

## Giấy phép model khác giấy phép code

Code bọc ngoài có giấy phép thoáng. **Trọng số model có giấy phép riêng**, và một số biến thể
model tách giọng là phi thương mại. Kiểm giấy phép của mọi checkpoint bạn tải về trước khi dùng
output cho mục đích thương mại. Giấy phép trọng số cũng đổi âm thầm hơn giấy phép code, nên kiểm
lại sau mỗi lần cập nhật.
