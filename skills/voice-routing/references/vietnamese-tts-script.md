# Viết kịch bản để engine TTS tiếng Việt đọc đúng

Mọi quy tắc ở đây đều đã được **đo**, không phải đoán: văn bản được tổng hợp thành tiếng, rồi
Whisper phiên âm ngược audio đó, và cột "engine đọc thành" là thứ nó nghe ra. Quy tắc nào chưa
đo thì ghi rõ là chưa đo.

Đo trên OmniVoice 0.2.1 với clip tham chiếu dài 18 giây. Trên engine khác, chi tiết sẽ khác,
nhưng *dạng lỗi* thì lặp lại: ký tự phân cách bị nuốt, từ viết tắt dính vào chữ số liền kề,
và mảnh câu ngắn đứng riêng thì render chập chờn.

---

## 1. Việc cần làm

Văn bản thô → kịch bản để nói. **Không phải chép lại văn bản viết.** Văn viết để đọc bằng mắt
và văn viết để đọc thành tiếng là hai thứ khác nhau; ghép nối các câu của một bài báo sẽ cho
ra nhịp đọc phẳng như đọc danh sách — thứ ai cũng nhận ra là giọng máy.

Viết lại trước, rồi áp các quy tắc dưới đây, rồi gắn marker, rồi kiểm tra.

## 2. Bảng phát âm

| Trường hợp | Viết SAI | Engine đọc thành | Viết ĐÚNG |
|---|---|---|---|
| **Số phiên bản** | `GLM-5.3` | "GLM-53" — mất `.3` | `GLM phiên bản 5.3` |
| | `GLM 5.3` | "GOM53" — cả cụm bị méo | |
| | `GPT 5.2` | "GPT-52" | `GPT phiên bản 5.2` |
| **Giờ** | `14:30` | "14.30" — mất chữ "giờ" | `14 giờ 30` |
| **Ngày** | `22/8/2026` | "22.8.2026" — mất dấu gạch chéo | `22 tháng 8 năm 2026` |
| **Tên miền** | `Z.ai` | **"Z đây"** — sai hẳn | `Z chấm AI` |
| **Hàng nghìn** | — | đúng | `2.436` *hoặc* `2436` — cả hai đều được |
| **Số viết bằng chữ** | — | đúng | `hai nghìn bốn trăm ba mươi sáu` — cũng được |
| **Tiền** | — | đúng | `1.250.000 đồng` |
| **Phần trăm** | — | đọc thành "phần trăm" | `15%` |
| **Thuật ngữ công nghệ tiếng Anh phổ biến** | — | đúng | `API`, `OpenAI`, `Microsoft`, `Google` — để nguyên |

### Quy tắc nằm bên dưới bảng

**Từ viết tắt dính sát vào số sẽ dính liền và méo.** `GLM 5.3` → "GOM53",
`GPT 5.2` → "GPT-52". Chèn một từ thường vào giữa là hết:
`GLM phiên bản 5.3` đọc đúng. Đây là dòng hữu ích nhất trong tài liệu này — nó áp cho tên
model, phiên bản sản phẩm, tiêu chuẩn, bất cứ thứ gì có dạng `CHỮ CÁI + chữ số`.

**Ký tự phân cách bị nuốt.** `:` `/` `.` trong giờ, ngày và số phiên bản biến mất. Viết chúng
thành chữ: `giờ`, `tháng`, `năm`, `chấm`.

**Số trơn thì an toàn.** Cả chữ số lẫn số viết bằng chữ đều đọc đúng, kể cả dấu chấm hàng
nghìn kiểu Việt. Để nguyên.

> **Một quy tắc đã bị thay thế, giữ lại vì lý do của nó quan trọng.** Bản trước của ghi chú
> này bắt buộc giữ số ở dạng chữ số vì số viết bằng chữ bị nén lại
> ("một nghìn một trăm bốn mươi mốt" co thành "141"). Đo lại với một clip tham chiếu tốt:
> **cả hai dạng đều đúng.** Lỗi gốc chưa bao giờ nằm ở cách viết — mà ở một clip tham chiếu
> chỉ dài vài giây. Clip ngắn làm giảm chất lượng mọi thứ, và triệu chứng tình cờ lộ ra ở con
> số trước. Khi một quy tắc có vẻ là về văn bản, hãy kiểm xem thực ra nó có phải về clip không.

**Không bao giờ bật bộ chuẩn hoá văn bản của engine cho tiếng Việt.** Trong OmniVoice,
`normalize_text` đưa zh/en qua một bộ chuẩn hoá đúng nghĩa, còn mọi ngôn ngữ khác đi qua một
regex chỉ biết `\d+`. Dấu chấm hàng nghìn kiểu Việt bị vỡ thành mảnh — tệ hơn không chuẩn hoá.
Luôn tắt.

### Chưa đo — kiểm khi gặp

Tên riêng nước ngoài ít gặp (một lần thử nghe `Claude` thành "Cloud", và không rõ engine phát
âm sai hay ASR nghe nhầm); từ viết tắt cần đánh vần từng chữ cái; đơn vị như `km/h` và `GB`;
số La Mã.

## 3. Marker

```
[marker-name] First sentence. Second sentence.
[other-marker] Now the delivery changes.
```

Một marker giữ hiệu lực **đến marker kế tiếp**. Đoạn không gắn marker dùng clip trung tính
của profile.

Tên marker lấy từ profile, không phải tự nghĩ ra — đọc `voices/<profile>.profile.json` trước.
Marker không có trong manifest sẽ bị gỡ bỏ và đoạn đó quay về marker đang có hiệu lực, chỉ
được báo bằng một dòng console rất dễ bỏ qua.

Chọn theo **ý nghĩa**, không rải cho có biến hoá: câu mở móc (hook), nhấn mạnh hoặc kết luận,
kể chuyện nhỏ nhẹ, liệt kê nhanh, giải thích thông thường.

**Tag phi ngôn ngữ** — các âm nội tuyến của chính engine như tiếng cười, thở dài và thán từ
ngạc nhiên — được chuyển thẳng qua, và yếu. Chúng là tiếng động rời rạc; không diễn đạt được
"đọc cả đoạn này trầm hơn". Dùng tiết chế; trong văn bản tin tức chúng nghe giả rất nhanh.

## 4. Seed

Pin một seed. Engine không tái lập được nếu thiếu nó, và một phép A/B không pin seed đo nhiễu
lấy mẫu chứ không đo thay đổi của bạn. Chi tiết ở `engine-limits.md`.

Seed không làm giọng hay hơn — nó làm một lần render lặp lại được. Các lần lấy mẫu khác nhau
*đúng là* có lần tốt lần kém, nên dò seed là một kỹ thuật thật, nhưng máy chỉ **loại được lần
lấy mẫu hỏng** (lỗi ASR cao). Không có chỉ số nào cho biết lần nào nghe người hơn. Chỉ dò seed
cho những câu trượt cổng ASR; đừng dò cho tất cả.

## 5. Kiểm trước khi bàn giao

1. Không còn ngoặc lạc — mọi marker đều có trong manifest, mọi tag đều là tag thật của engine.
2. **Không có mảnh câu ngắn đứng một mình.** Tiêu đề, nhãn hay một con số trơn render riêng
   sẽ chập chờn: token đầu bị méo hoặc một từ bị nuốt. Gộp nó vào đầu một câu dài hơn.
3. Câu quá dài (khoảng trên 380 ký tự) tách tại dấu phẩy, không bao giờ tách giữa cụm từ.
4. Tổng hợp → ASR ngược lại → tỉ lệ lỗi ký tự (CER) trên 0.25 nghĩa là sửa *cách viết* của
   phần đó rồi thử lại.

## 6. Ví dụ hoàn chỉnh

**Thô:**
> Z.ai công bố GLM-5.3 ngày 14/8/2026. Mô hình đã phát hiện 2.436 lỗ hổng bảo mật, tăng 15% so với bản trước.

**Kịch bản:**
```
[hook] Ngày 14 tháng 8 năm 2026, công ty Z chấm AI công bố một mô hình mới.
[neutral] Nó tên là GLM phiên bản 5.3.
[emphasis] Và đây mới là con số đáng chú ý: mô hình này đã phát hiện 2.436 lỗ hổng bảo mật, tăng 15% so với bản trước.
```

Đã đổi: viết tên miền thành chữ · tách số phiên bản khỏi từ viết tắt · viết ngày bằng chữ ·
chia thành câu ngắn · gắn marker theo ý nghĩa. Để nguyên: `2.436` và `15%`, vì cả hai đều đã
đo là đúng.

*(Tên marker ở trên chỉ là ví dụ — dùng tên trong manifest của bạn.)*
