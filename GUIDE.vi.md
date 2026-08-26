# Hướng dẫn — từ bản ghi âm đến một giọng điều khiển được

Toàn bộ đường đi, theo thứ tự, kèm những quyết định thật sự quan trọng.

**[English](GUIDE.md)** · [README](README.vi.md)

---

## 0. Trước khi thu

Hai quyết định ở đây nặng hơn mọi thứ phía sau.

**Thu theo TÌNH HUỐNG, không phải thu nhiều lần.** Hỏi người nói xem họ thật sự làm việc
trong những bối cảnh nào — giảng giải, thuyết phục, kể chuyện, đọc theo kịch bản, hướng dẫn
thao tác. Đặt tên file theo đúng tình huống đó. Cái nhãn ấy là **ngữ cảnh do con người gán**,
máy không suy ra được từ sóng âm, và nó là thứ giá trị nhất anh đưa vào quy trình.

**Giữ nguyên thiết lập thu qua các tình huống.** Cùng mic, cùng khoảng cách, cùng phòng. Đổi
thiết lập sẽ chẻ giọng thành các họ âm sắc mà không thuật toán nào hoà giải được, và làm
người nói trông như có nhiều sắc thái hơn thực tế.

Khoảng một giờ là thừa. Mỗi sắc thái chỉ cần một clip 16–19 giây; nút thắt luôn là **chọn**,
không bao giờ là lượng.

## 1. Cài

Xem [`install-omnivoice.md`](skills/voice-routing/references/install-omnivoice.md). Một biến
môi trường `OMNIVOICE_DIR` nối bộ script này với engine. Trỏ `VOICE_STUDIO_WORK` ra **ngoài
repo** để audio sinh ra không bao giờ có cơ hội lọt vào git.

## 2. Làm sạch — chỉ khi cần

Đo nền nhiễu và xem giữa các câu có khoảng lặng thật không. Audio liên tục không có khoảng
lặng nào nghĩa là đang có thứ gì phát bên dưới — cái đó mới cần làm sạch. Thứ đã sạch thì
**để yên**: model làm mượt, mà mượt chính là thứ xoá mất chất giọng anh đang muốn giữ.

Bản ghi dài thường pha trộn. Đo ở vài mốc; đoạn nào sạch thì khỏi đụng.

Chi tiết và cạm bẫy hai-môi-trường:
[`install-voice-clean.md`](skills/voice-routing/references/install-voice-clean.md).

## 3. Đào

```bash
python studio/mine.py --dir recordings/ --name narrator
```

Cắt audio thành cửa sổ có hai đầu là ranh giới câu, đo ngôn điệu, phân cụm trong nội bộ giọng,
đặt tên cụm theo đúng trục thật sự lệch, rồi cắt ba ứng viên mỗi cụm.

Kết quả có cả **marker âm học** do dữ liệu tìm ra lẫn **marker tình huống**, mỗi file nguồn
một cái. Giữ cả hai —
[`mining-protocol.md`](skills/voice-routing/references/mining-protocol.md) giải thích ba lần
sửa đã đổi hẳn kết quả, trong đó có lần phát hiện thuật toán đang phân cụm theo **mức thu**
chứ không theo cách nói.

## 4. Dựng

```bash
python studio/build.py --name narrator --mode new
```

Chạy sáu cổng qua từng ứng viên, giữ cái đầu tiên đạt. Có clip bị loại là **bình thường** —
đó là cổng đang làm việc. Kết quả kèm hai thứ để nghe: một câu đọc qua đủ mọi marker, và một
đoạn đổi marker liên tục để nghe mối nối.

**Hãy nghe mối nối.** Mọi thứ khác ở đây máy kiểm được; riêng chuyện chuyển giọng nghe có tự
nhiên không thì không.

Chi tiết cổng: [`verify-gates.md`](skills/voice-routing/references/verify-gates.md).

## 5. Viết kịch bản

Đây là chỗ quyết định chất lượng, và là bước người ta hay bỏ qua.

Văn để đọc bằng mắt khác văn để đọc thành tiếng. Viết lại: câu ngắn, mỗi câu một ý, câu hỏi
tu từ, những từ đệm người ta thật sự nói. Rồi áp luật phát âm — tách viết tắt khỏi số, viết
dấu ngăn cách thành chữ — và gắn marker theo ngữ nghĩa.

Bảng đo đầy đủ:
[`vietnamese-tts-script.md`](skills/voice-routing/references/vietnamese-tts-script.md).

## 6. Đọc

```bash
python studio/speak.py --file script.txt --profile narrator --out out.mp3
```

Cắt theo marker, rồi theo câu, ghim seed, chuẩn hoá mức, vuốt mối nối.

## 7. Kiểm

Tổng hợp, cho nhận dạng nghe lại, so. Tỉ lệ sai ký tự trên 0,25 nghĩa là sửa **cách viết**
đoạn đó, không phải sửa giọng. Câu nào cứ trượt mãi thì đổi seed — nhưng chỉ riêng câu đó.

---

## Những lỗi tốn thời gian nhất

**Tin vào tai.** Mọi khẳng định về giọng — clip này tốt không, cái thẻ kia có tác dụng gì
không, đoạn này đọc đúng chưa — đều phải chốt bằng phép đo. Nghe thì không đáng tin, không
lặp lại được, và không chấm nổi vài chục ứng viên.

**So sánh mà không ghim seed.** Engine không tái lập nếu không ghim. Hai lần render cùng một
text ra hai bản khác nhau. Phát hiện ra điều này đúng lúc đang đo xem một cái thẻ có tác dụng
gì — chênh lệch quan sát được chứa **cả** tác dụng của thẻ **lẫn** nhiễu của hai lần bốc, gỡ
không ra.

**Đổ lỗi cho engine trong khi clip quá ngắn.** Một tỉ lệ đáng ngạc nhiên của "engine này tệ"
hoá ra là "clip mẫu này dài bốn giây". Kiểm độ dài clip trước đã.

**Để một cổng đo hộ thứ mình thật sự quan tâm.** Có cổng từng kiểm "transcript có kết thúc
bằng dấu câu không", coi đó là dấu hiệu clip cắt gọn. Hoá ra nó đo **thói quen chấm câu của
bộ nhận dạng**, và loại oan nguyên một cụm tốt. Đo thẳng vào audio — một phần tư giây cuối có
im không — vừa đúng vừa đơn giản hơn.

**Đinh ninh một nhánh code có chạy.** Có đoạn crossfade được viết, được đọc lại, rồi ship
dưới dạng **code chết**: khe lặng luôn được chèn trước nên nhánh crossfade không bao giờ tới
lượt. Mọi mối nối của mọi bản render đều kêu cạch. Phải kiểm nhánh đó có thật sự chạy không.

## Đạo đức

Chỉ clone giọng của chính mình, hoặc giọng mà chủ nhân đã đồng ý bằng văn bản. Giọng là dữ
liệu cá nhân và nhận ra được. Repo này không kèm một file audio nào — đó là lựa chọn có chủ
đích, và là mặc định hợp lý cho bất cứ thứ gì anh xây tiếp lên trên.
