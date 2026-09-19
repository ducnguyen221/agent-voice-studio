---
name: voice-routing
description: Use when producing speech with a cloned voice — building a voice profile from recordings, writing a script a TTS engine reads correctly (especially Vietnamese numbers, acronyms, dates, foreign names), diagnosing a voice that stutters or mangles words, or setting up the engine and voice station. Routes to the one reference the current step needs instead of loading everything.
---

# Voice Studio — một cửa vào

Bạn đang tạo lời nói bằng giọng thật của một người. Có bốn tình huống. Xác định tình huống của
mình, nạp **đúng một** reference tương ứng, làm việc, dừng.

| Đang xảy ra | Nạp | Rồi |
|---|---|---|
| Có text cần **đọc** — đã có profile | `references/vietnamese-tts-script.md` | viết lại text, gắn marker, tổng hợp |
| Chưa có profile — có **bản ghi âm** | `references/mining-protocol.md` | đào → kiểm → dựng |
| Giọng **nghe sai** — vấp, đọc sai số, lặp âm tiết | `references/engine-limits.md` | chẩn đoán theo hành vi đã biết của engine |
| **Chưa cài gì** / cần dựng trạm | `references/install-omnivoice.md` | cài engine + `voice-studio init`, rồi quay lại |

Nạp `references/verify-gates.md` mỗi khi nhận hoặc loại một clip tham chiếu.
Nạp `references/profile-and-markers.md` khi một profile cần nhiều hơn một sắc thái đọc.
Nạp `references/install-voice-clean.md` chỉ khi bản ghi có nhạc hoặc tạp âm dưới giọng.

## Bốn luật đè mọi thứ

**1. Đừng tin tai. Đo.**
Cả bộ công cụ tồn tại vì nghe là thứ không tin được và không lặp lại được. Mọi nhận định về
giọng — clip này tốt không, thẻ kia có tác dụng không, bản đọc này đúng chưa — đều phân xử bằng
cách tổng hợp rồi cho ASR nghe lại output. Thấy mình viết "nghe hay hơn" là đã bỏ qua đúng bước
quan trọng nhất.

**2. Ghim seed, không thì phép so sánh vô nghĩa.**
Engine mặc định không tái lập: hai lần đọc cùng một text ra khác nhau. So A/B mà không ghim seed
là đo nhiễu, không đo thứ bạn vừa đổi. Xem `engine-limits.md`.

**3. Một clip tham chiếu tồi đầu độc mọi thứ phía sau.**
Clip không phải một đầu vào trong nhiều đầu vào — nó *là* giọng. Có sáu cổng kiểm tự động vì
thường không có người ngồi nghe. Đừng bao giờ cho qua một clip chưa kiểm.

**4. Chỉ clone giọng của chính bạn, hoặc giọng mà chủ nhân đã đồng ý bằng văn bản.**
Không phải chú thích pháp lý cho có — đó là lý do repo này không phát hành một file audio nào.

## Hình dạng công việc

```
bản ghi ──► đào ──► kiểm ──► dựng ──► profile
 (hàng giờ)  clip    cổng    manifest     │
                                          ▼
                 text thô ──► kịch bản ──► đọc ──► audio
                             (marker,       │
                              phát âm)      ▼
                                        ASR kiểm lại
```

Đào và kiểm làm **một lần** cho mỗi giọng. Viết kịch bản và đọc làm mỗi lần. Phần lớn phiên
làm việc chỉ có hàng dưới.

## Lệnh

Một lệnh `voice-studio` (hoặc `python -m voice_studio` bằng python của venv engine) cho mọi
công cụ. Trạm giọng tìm theo thứ tự trong `docs/WORKSPACE.md` — lệnh không bao giờ giả định engine
nằm cạnh nó.

```
voice-studio lab mine     --dir <bản ghi> --name <profile>     # đào các sắc thái đọc
voice-studio lab build    --name <profile> --mode new          # chấm clip qua cổng, dựng profile
voice-studio speak        --file script.txt --profile <profile> --out out.mp3 --json
voice-studio make-profile --audio rec.wav --start 120 --dur 18 --name <profile>
voice-studio verify       --wav clip.wav                       # soi một clip
voice-studio lab split    --from <profile> --prefix <p>        # biến thể → profile độc lập
voice-studio lab organize --keep <profile> ... --apply         # dọn kho giọng
voice-studio doctor                                            # trạm đủ chưa, thiếu gì
```

`lab build` và `speak` phủ phần lớn công việc; phần còn lại dành cho lúc cần soi kỹ. Các lệnh cũ
`python studio/<tên>.py` vẫn chạy (là alias).

Pipeline khác gọi `speak`/`narrate` với `--json`: đọc **mã thoát** (`0` ok · `1` lỗi engine ·
`2` gọi sai · `3` trạm chưa cài) và **dòng JSON cuối stdout** — chi tiết ở `install-omnivoice.md`.

## Đồ đạc nằm ở đâu

Engine, kho giọng và bản ghi là **của bạn**, sống ở *trạm giọng* ngoài git: `<repo>/workspace/`
(chế độ `embedded`, mặc định) hoặc `~/.voice` (chế độ `separate`). Repo chỉ giữ phương pháp và
mã. Giữ nguyên như vậy: audio không bao giờ được vào repo — `.gitignore` chặn cả họ audio mặc
định, và hook `pre-commit` của chế độ embedded chặn `workspace/` lẫn `.env`.

Khi cài cho người khác: `voice-studio init` sẽ hỏi chế độ. **Agent phải trình bảng lựa chọn cho
người dùng và chờ họ chọn** (khuyến nghị `embedded`), không tự chọn im lặng. Máy đã có trạm
ngoài thì `init` tự nhận `separate`, không hỏi.
