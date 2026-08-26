# Agent Voice Studio

Quy trình sản xuất giọng để một AI agent chạy trọn vẹn: từ hàng giờ ghi âm thô đến một giọng
đọc đã được kiểm chứng, mà sắc thái do chính kịch bản điều khiển.

**[English](README.md)** · [Hướng dẫn](GUIDE.vi.md) · MIT

---

## Đây là cái gì

Clone một giọng thì dễ. Có được một giọng đọc **đúng** văn bản của mình, đổi sắc thái khi ý
nghĩa đổi, và lặp lại y hệt khi chạy lại — đó mới là phần khó, và đó là thứ ở đây.

**Cách tìm ra các sắc thái vốn đã có sẵn trong giọng một người.** Không ai chỉ có một cách
nói. Người ta giảng giải, thuyết phục, kể chuyện, hướng dẫn thao tác. Việc đào tách những
kiểu nói đó ra khỏi bản ghi dài, bằng ngôn điệu **đo được** chứ không bằng phỏng đoán.

**Sáu cổng kiểm tự động thay cho tai người.** Clip mẫu không phải một đầu vào bình thường —
**nó chính là giọng**, và mọi thứ sinh ra sau đều thừa hưởng lỗi của nó. Mỗi ứng viên đều bị
máy chấm, gồm cả một vòng đi-về qua nhận dạng tiếng nói.

**Điều khiển sắc thái từ trong kịch bản.** Marker trong text quyết định clip mẫu nào đọc đoạn
nào. Người gọi chỉ chọn một tên profile; phần diễn do câu chữ quyết định.

**Bảng luật phát âm tiếng Việt được ĐO, không phải đoán.** Mọi luật đều dựng bằng cách tổng
hợp rồi cho nhận dạng nghe lại. Số đo nằm nguyên trong bảng — kể cả số đo đã lật đổ một niềm
tin cũ.

## Không phải cái gì

Không phải engine — anh tự cài. Không phải dịch vụ. Không phải nguồn cung giọng: repo này
**không chứa một file audio nào**, có chủ đích.

## Cài

```bash
git clone https://github.com/ducnguyen221/agent-voice-studio
cd agent-voice-studio
```

Cài engine rồi trỏ đúng một biến vào đó. Các bước đầy đủ, kèm hai cạm bẫy từng tốn thời gian
thật, nằm ở [`skills/voice-routing/references/install-omnivoice.md`](skills/voice-routing/references/install-omnivoice.md).

```powershell
setx OMNIVOICE_DIR "C:\duong\dan\toi\engine"
```

Cài như plugin cho agent:

```bash
claude plugin marketplace add ducnguyen221/agent-voice-studio
claude plugin install agent-voice-studio@agent-voice-studio
```

## Dùng

```bash
python studio/mine.py  --dir recordings/ --name narrator   # tìm các sắc thái
python studio/build.py --name narrator --mode new          # chấm clip, dựng profile
python studio/speak.py --file script.txt --profile narrator --out out.mp3
```

Đào và dựng làm **một lần** cho mỗi giọng. Viết và đọc thì làm mỗi lần.

Agent đã cài plugin sẽ đọc `skills/voice-routing/SKILL.md` và chỉ nạp đúng reference của bước
đang làm.

## Bốn luật

1. **Đừng tin tai — hãy đo.** Tổng hợp, cho nhận dạng nghe lại, so. "Nghe hay hơn" không phải
   kết quả.
2. **Ghim seed.** Engine không tái lập nếu không ghim. Phép so không seed là đang đo nhiễu.
3. **Clip mẫu hỏng thì hỏng mọi thứ sinh ra từ nó.** Đừng bao giờ cho qua lấy lệ.
4. **Chỉ clone giọng của chính mình, hoặc người đã đồng ý bằng văn bản.**

## Ghi công

Repo này điều phối các engine mà anh tự cài; nó không đóng gói dòng code nào của họ.

- [OmniVoice](https://github.com/k2-fsa/OmniVoice) (k2-fsa) — Apache-2.0 — tổng hợp và clone
- [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio) — Apache-2.0 — khử noise
- [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) — MIT — tách giọng

**License của model weights đi đường riêng với license của code**, và một số biến thể model
tách giọng là **non-commercial**. Kiểm license từng checkpoint mình tải trước khi dùng sản
phẩm vào mục đích thương mại.

## Giấy phép

MIT — xem [LICENSE](LICENSE).
