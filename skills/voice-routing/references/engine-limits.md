# Engine làm được gì, không làm được gì

Sáu sự thật rút ra từ đo đạc. Mỗi điều đều đã làm đổi một quyết định thiết kế, và vài điều
đi ngược hẳn với những gì bề mặt API gợi ý.

---

## 1. Một lần generate = một clip = một lối đọc

Clip tham chiếu không chỉ cho âm sắc; nó quyết định *toàn bộ* lối đọc — quãng giọng, nhịp,
năng lượng, cách người nói ngắt câu. Không có cách nào bảo một clip đọc đoạn này tươi sáng
rồi đọc đoạn sau trầm xuống.

**Hệ quả:** không thể dựng "một profile có dải cảm xúc" từ một clip duy nhất. Phải là nhiều
clip trong cùng một danh tính, chuyển qua lại bằng marker trong văn bản. Đó chính là toàn
bộ lý do `profile-and-markers.md` tồn tại.

## 2. Không có tham số cảm xúc

Trường `instruct` chỉ nhận một **bộ từ vựng đóng** — giới tính, nhóm tuổi, cao độ, thì thầm,
giọng vùng. Từ chỉ cảm xúc bị từ chối thẳng bằng `ValueError`.

## 3. `instruct` yếu hẳn khi đã clone clip

F0 trung vị đo trên cùng một văn bản:

| | F0 |
|---|---|
| mặc định | 159.9 Hz |
| `instruct = high pitch` | 172.3 Hz (+12) |
| `instruct = low pitch` | **164.0 Hz — dịch sai chiều** |

Prompt clone lấn át tất cả. Đừng xây gì trên `instruct` khi đang dùng clip tham chiếu; nó
không phải trục cảm xúc, và khi đi cùng clone thì gần như cũng không phải trục cao độ.

## 4. Generate KHÔNG tái lập được nếu không pin seed tường minh

Cùng văn bản, cùng profile, chạy ba lần → **ba hash audio khác nhau**. Thời lượng thì khớp,
vì thời lượng được ước lượng từ văn bản — và chính điều đó khiến lỗi này dễ bị bỏ sót:
trong log, output *trông* rất ổn định.

Cấu hình generate **không có tham số seed**, và nhiệt độ lấy mẫu token vốn đã bằng 0. Tính
ngẫu nhiên đến từ việc chọn vị trí trong quá trình unmasking lặp và từ khởi tạo diffusion.
Seed thư viện tensor trước mỗi lần gọi thì output giống hệt **đến từng byte**.

**Hệ quả — điều quan trọng nhất:** mọi phép so sánh chạy mà không pin seed đều đang đo
nhiễu lấy mẫu. Điều này được phát hiện theo cách đắt giá khi thử đo xem một inline tag có
tác dụng gì không; khác biệt đo được hoá ra chứa cả tác dụng của tag lẫn nhiễu của hai lần
lấy mẫu riêng biệt, không tách ra được.

**Seed không làm giọng hay hơn.** Nó làm một lần render lặp lại được. Các lần lấy mẫu khác
nhau *đúng là* có lần tốt lần kém — nên dò seed là việc chính đáng — nhưng máy chỉ loại được
lần lấy mẫu hỏng qua lỗi ASR. Không có gì đo được "nghe người hơn". Chỉ dò seed cho những câu
trượt cổng.

Đổi seed theo từng câu (`seed + sentence_index`) để các câu không dùng chung một mẫu nhiễu,
trong khi cả bản render vẫn tái lập được.

## 5. Inline tag phi ngôn ngữ có thật nhưng yếu với tiếng Việt

Các âm trong ngoặc của engine — tiếng cười, tiếng thở dài, thán từ ngạc nhiên, âm nghi vấn —
chạy không lỗi trên văn bản tiếng Việt và có nới rộng dải cao độ một chút. Chúng là tiếng
động rời rạc, không phải công cụ điều khiển lối đọc: trong bộ từ vựng đó không có gì diễn
đạt được "đọc đoạn này trầm hơn". Dùng tiết chế.

## 6. Bộ chuẩn hoá văn bản không an toàn với tiếng Việt

Nó đưa tiếng Trung và tiếng Anh qua một bộ chuẩn hoá thật, còn mọi ngôn ngữ khác đi qua một
regex chỉ nhận số nguyên trơn. Dấu phân cách hàng nghìn kiểu Việt bị vỡ thành mảnh — tệ hơn
để nguyên văn bản. **Luôn tắt.**

---

## Chẩn đoán giọng nghe sai

| Triệu chứng | Gần như luôn do | Cách sửa |
|---|---|---|
| Một âm tiết từ đâu xuất hiện ở đầu mọi clip | clip tham chiếu kết thúc giữa chừng một từ | cắt lại clip tại ranh giới câu, có đuôi lặng — xem `verify-gates.md` |
| Số, từ viết tắt hoặc ngày tháng bị đọc méo | cách viết văn bản | `vietnamese-tts-script.md` |
| Câu ngắn render chập chờn, nuốt mất từ đầu | mảnh câu bị render đứng một mình | gộp vào một câu dài hơn |
| Cùng input, mỗi lần chạy ra output khác | chưa pin seed | sự thật 4 |
| Lối đọc phẳng, giống hệt nhau mọi chỗ | một clip gánh toàn bộ | nhiều clip + marker |
| Chất lượng giọng kém nói chung | clip tham chiếu quá ngắn | cắt lại 16–19 giây từ audio sạch |

Dòng cuối đáng khắc cốt: **một phần lớn bất ngờ của "engine dở" hoá ra là "clip ngắn".**
Kiểm tra độ dài clip trước khi đổ lỗi cho bất cứ thứ gì khác.
