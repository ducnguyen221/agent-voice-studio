# Khai thác phong cách nói từ bản ghi dài

Bạn có hàng giờ ghi âm một người nói và cần vài clip tham chiếu ngắn thể hiện được **những cách
nói khác nhau** của họ. Lệnh: `voice-studio lab mine` (mã ở `voice_studio/lab/mine.py`).

---

## Chọn chất liệu nguồn

Ghi **theo tình huống, không theo lượt thu**. Hỏi người nói về những bối cảnh họ thực sự làm
việc — giải thích, thuyết phục, trình bày theo ghi chú, trình bày theo kịch bản, demo một công
cụ. Nhãn tình huống đó là thông tin máy không thể khôi phục từ dạng sóng, và hoá ra là đầu vào
giá trị nhất của cả quy trình.

Khoảng một giờ là dư. Ràng buộc thật là *chọn lọc*, không phải khối lượng: một profile cần một
clip 16–19 giây cho mỗi phong cách, nên một giờ là nhiều hơn mức cần tới vài bậc độ lớn.

**Giữ nguyên cách bố trí thu âm giữa các tình huống.** Trộn micro hay khoảng cách sẽ tách giọng
thành nhiều họ âm sắc mà thuật toán phân cụm khéo đến đâu cũng không gộp lại được — và trông như
người nói có biên độ rộng hơn thực tế.

## Quy trình

1. **Phân đoạn** — tìm các phát ngôn cách nhau bởi khoảng dừng ≥ 250 ms; gộp các phát ngôn liền
   nhau thành cửa sổ 12–22 giây, mở và đóng đúng ranh giới phát ngôn.
2. **Đặc trưng** — mỗi cửa sổ: cao độ trung vị, biên độ cao độ, tốc độ nói, năng lượng, tỉ lệ
   dừng, độ sáng phổ. **Chỉ ngữ điệu.** Không gì về chủ đề hay câu chữ.
3. **Phân cụm** — chuẩn hoá z-score *trong phạm vi người nói này*, rồi k-means với `k` chọn theo
   silhouette.
4. **Đặt tên** — theo các trục đã đo, không theo tưởng tượng.
5. **Chọn** — ba ứng viên mỗi cụm gần tâm cụm nhất, cắt có lead-in và đuôi lặng đúng độ dài.
6. **Kiểm** — `verify-gates.md`. Ứng viên đầu tiên qua cổng thì thắng.

## Ba chỗ sửa đã làm đổi kết quả

### Không vắt qua khoảng lặng dài

Độ dài cửa sổ đo từ đầu đến cuối, nên một cửa sổ có thể "hợp lệ" trong khi một nửa là khoảng
trống — người nói dừng mười giây để uống nước. Điều đó phá hỏng đặc trưng tỉ lệ dừng và cho ra
clip tham chiếu gần như rỗng. **Từ chối nối các phát ngôn qua khoảng trống dài hơn ~1,2 s.**

### Chuẩn hoá mức âm theo từng file nguồn, không thì bạn phân cụm theo file

Năng lượng tuyệt đối không đo cách nói; nó đo **gain lúc thu**. Một buổi thu nhỏ hơn các buổi
khác khoảng 10 dB đã sinh ra một "cụm biểu cảm" mà hoá ra chính là file đó — thuật toán đã gom
theo *file*, không theo phong cách. Dấu hiệu lộ ra: kích thước cụm khớp kích thước file gần như
một-một.

Trừ năng lượng trung vị của chính mỗi file trước. Sau khi sửa, chênh lệch năng lượng giữa các
tình huống sụp về gần bằng không, xác nhận toàn bộ hiệu ứng trước đó chỉ là do gain lúc thu.
Giữ cao độ ở giá trị tuyệt đối — với một người nói qua nhiều buổi, nó vẫn có ý nghĩa.

### Đặt tên cụm theo thứ bạn đã đo

Bản đầu so khớp cụm với một bảng nguyên mẫu cảm xúc viết tay (*excited*, *whispering*, v.v.).
Trên dữ liệu thật, **ba trên năm cụm không khớp gì** và rơi xuống kiểu đánh số tự động vô
nghĩa. Nới dung sai còn tệ hơn: nó sẽ gắn nhãn "whispering" cho một cụm rõ ràng là *nhanh*.

Dựng tên từ các trục thực sự lệch — cao/thấp, nhanh/chậm, mạnh/nhẹ — theo thứ tự cố định.
`high-slow` nói một điều đúng và kiểm được. `excited` là phỏng đoán về trạng thái bên trong mà
không ai đo.

## Hai loại marker, và vì sao cần cả hai

Phân cụm âm học vứt bỏ nhãn của chính người nói. Silhouette cũng ưu ái cách chia thô, nên năm
tình huống thu cẩn thận có thể sụp còn ba cụm.

Giữ cả hai: **marker âm học** do dữ liệu tìm ra, và **marker tình huống**, mỗi file nguồn một
marker, đặt tên theo file. Loại thứ hai là bối cảnh con người mà dạng sóng không chứa, và trên
thực tế là loại dễ chọn đúng hơn khi viết kịch bản.

**Khử trùng lặp lúc build** (`voice-studio lab build`). Cả hai loại được khai thác từ cùng một
kho cửa sổ, nên hai marker có thể rơi vào cùng một đoạn — đã gặp một lần, giống hệt từng byte.
Hai tên cho ra cùng một audio là phí một slot và đánh lừa người viết kịch bản.

## Để dữ liệu quyết định số lượng

Đừng cố định trước số phong cách. Silhouette chọn. Nếu người nói chỉ có ba giọng điệu khác
biệt thì ba là câu trả lời trung thực, và bịa thêm cái thứ tư sẽ cho ra một marker nghe giống
một trong những cái kia.

## Khi nào làm sạch đáng công — và khi nào gây hại

Chỉ làm sạch audio có nhạc hoặc tạp âm **nằm dưới giọng nói**. Kiểm nền nhiễu và xem giữa các
câu có khoảng lặng thật không: audio liền mạch không có khoảng lặng nghĩa là có thứ gì đó đang
phát bên dưới.

**Không làm sạch audio đã sạch.** Model tách và khử nhiễu làm mượt, và làm mượt chính là thứ xoá
đi chất giọng bạn đang muốn giữ. Một bản ghi đo được nền nhiễu −67 dB đã được để nguyên vì lý do
đó và cho ra một trong những profile tốt hơn cả.

Bản ghi dài thường lẫn lộn: một nguồn có thể có nhạc suốt nửa đầu và sạch ở nửa sau. Đo ở nhiều
điểm trước khi quyết — đoạn sạch thì không cần làm sạch gì cả, vừa nhanh hơn vừa tốt hơn. Làm
sạch bằng `voice-studio clean`; chi tiết cài đặt ở `install-voice-clean.md`.
