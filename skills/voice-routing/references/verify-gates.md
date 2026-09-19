# Sáu cổng mọi clip tham chiếu phải qua

Clip tham chiếu không phải một input trong nhiều input — **nó chính là giọng**. Mọi thứ sinh
ra từ nó đều thừa hưởng lỗi của nó. Các cổng này tồn tại vì thường không có người ngồi nghe,
và vì nghe bằng tai cũng không mở rộng được cho hàng chục ứng viên.

Chạy bằng `voice-studio verify` (mã ở `voice_studio/lab/verify.py`). Clip trượt **bất kỳ**
cổng nào đều bị loại và ứng viên kế tiếp được thử.

---

| # | Cổng | Loại khi | Bắt được |
|---|---|---|---|
| 1 | Clipping | peak ≥ −0.5 dB | bản ghi bị méo |
| 2 | Quá nhỏ | RMS < −34 dB | tỉ lệ tín hiệu/nhiễu không dùng được |
| 3 | Bám cao độ | > 35 % frame thất bại | còn sót nhạc nền, hoặc hai người nói chồng lên nhau |
| 4 | **Đuôi lặng** | 250 ms cuối không thấp hơn RMS của clip ít nhất 18 dB | clip kết thúc giữa chừng một từ |
| 5 | Round trip | tổng hợp 2 câu thăm dò, ASR ngược lại, CER > 0.25 | clip sinh ra lời nói bị méo |
| 6 | Leak probe | âm tiết đầu của output trùng âm tiết cuối của clip tham chiếu | đúng lỗi mà cổng 4 ngăn, bắt trực tiếp |

Cổng 1–4 rẻ; chạy chúng trước và bỏ qua phần việc GPU nếu đã trượt.

## Vì sao cổng 4 thay cho một phép kiểm tưởng hiển nhiên

Bản đầu tiên kiểm tra xem **transcript** có kết thúc bằng dấu câu không, với lập luận rằng
clip dừng giữa câu là clip cắt hỏng.

Nó loại sạch một cụm — ba trên ba ứng viên — và làm dừng cả quá trình build.

Nguyên nhân: ASR tiếng Việt thường xuyên bỏ dấu chấm cuối câu. Cổng đó đo **thói quen chấm
câu của bộ phiên âm**, không phải clip. Thứ thực sự đáng đo là audio có *kết thúc trong im
lặng* hay không, và audio thì đo trực tiếp được. Viết lại thành cổng 4, nó lập tức loại ba
clip hỏng thật ở ba cụm khác nhau — đúng việc một cổng phải làm.

**Bài học áp dụng rộng:** khi một cổng đo gián tiếp (proxy) cho thuộc tính bạn quan tâm, hãy
kiểm xem thực chất nó đang đo gì. Thiếu dấu chấm là sự thật về bộ phiên âm. Im lặng ở cuối
là sự thật về clip.

## Cổng 5 và 6 — lỗi đáng gọi tên

Nếu clip tham chiếu dừng **giữa từ hoặc giữa cụm từ**, model coi việc generate là phần nối
tiếp của âm thanh dở dang đó, và ghép âm tiết thừa vào đầu **mọi clip nó từng sinh ra từ
profile đó**. Một clip tham chiếu hỏng, và mọi bản render sau này đều mở đầu bằng một âm
tiết lạc.

Nghe qua loa thì dễ bỏ sót, nhưng đã biết hình dạng của nó thì không thể bỏ sót. Cổng 4 ngăn
nó về mặt cấu trúc; cổng 6 kiểm tra nó trực tiếp. Giữ cả hai — cổng 4 vẫn có thể được thoả
mãn bởi một khoảng lặng nằm ngay sau một từ bị cắt cụt.

## Cắt clip sao cho qua cổng

- Mở và đóng tại **ranh giới phát ngôn** — khoảng dừng ít nhất 250 ms ở cả hai phía.
- Thêm một đoạn dẫn ngắn (~0.15 s) và một đuôi lặng.
- **Đuôi không bao giờ được dài hơn khoảng lặng thật.** Đuôi cố định 0.40 s dài hơn ngưỡng
  dừng 0.25 s, nên khi khoảng lặng ngắn, đuôi sẽ nuốt mất âm đầu của câu kế tiếp — tái tạo
  đúng lỗi mà các cổng sinh ra để ngăn. Đo khoảng lặng thực tế phía sau rồi lấy
  `min(0.40, gap − 0.05)`.
- Nhắm **16–19 giây**. Clip ngắn hơn làm giảm chất lượng mọi thứ; dài hơn thì hết giúp ích.
- Khoảng dừng bên trong clip là bình thường và tự nhiên. Chỉ hai đầu là quan trọng.

## Chất lượng transcript ít quan trọng hơn bạn nghĩ

Văn bản tham chiếu nên khớp với audio, và sửa tay các lỗi ASR hiển nhiên đáng bỏ ra một phút.
Nhưng một clip cắt từ lời nói nhanh, nhiều năng lượng — nơi ASR kém đi rõ rệt — vẫn clone
sạch, qua round trip với CER 0.00. **Ranh giới trước, transcript sau.**

## Đừng cho clip qua cho có

Loại một ứng viên thì rẻ: lấy cái tiếp theo. Nhận một clip hỏng thì đắt: mọi bản render phía
sau đều mang lỗi, và bạn chỉ phát hiện ra vài tuần sau trên audio đã xuất bản.
