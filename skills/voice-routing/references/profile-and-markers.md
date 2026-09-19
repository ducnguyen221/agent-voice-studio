# Profile có nhiều phong cách nói

Một profile là **một danh tính giọng chứa nhiều clip tham chiếu**, chuyển đổi bằng marker nằm
trong văn bản. Người viết kịch bản chỉ thấy một cái tên; cách đọc thay đổi đúng chỗ kịch bản
bảo.

Hình dạng này do engine ép, không phải chọn cho đẹp: một lần gọi generate dùng đúng một clip,
và không có tham số cảm xúc. Xem `engine-limits.md`.

---

## Trên đĩa

```
voices/
    <name>.wav  .txt  .prompt.pt      ← neutral clip, FLAT, non-negotiable
    <name>.profile.json               ← manifest
    <name>.variants/
        <marker>.wav  .txt  .prompt.pt
```

**Clip trung tính nằm phẳng trong `voices/`.** Loader đơn giản đọc đúng `voices/<name>.wav` +
`.txt`, và pipeline ghim giọng theo tên. Giữ hợp đồng đó nghĩa là profile nhiều phong cách vẫn
chạy được ở mọi nơi profile thường chạy — chỉ là nó nói bằng giọng trung tính. Thư mục con của
profile không làm bẩn danh sách profile, vì việc liệt kê chỉ quét `*.wav` ở cấp trên cùng.

Manifest cho mỗi variant: đường dẫn wav tương đối, transcript của nó, speed tuỳ chọn, nguồn
(file và offset), các đặc trưng đã đo, và dấu thời gian build. Nguồn và dấu thời gian quan
trọng hơn vẻ ngoài của chúng — nhiều tháng sau, đó là cách duy nhất trả lời "clip này từ đâu ra,
và đợt nào thêm nó vào".

## Speed mặc định 1.0 và nên giữ nguyên

Clip đã mang sẵn nhịp của nó. Thêm hệ số speed là tính hai lần. Trường này tồn tại để chỉnh tay
sau khi nghe, không phải để builder đoán.

## Tổng hợp

Tách văn bản tại các marker; mỗi đoạn dùng clip của marker tương ứng; văn bản không có marker
dùng clip trung tính. **Tách mỗi đoạn thành câu và generate từng câu một** — khớp với cách các
pipeline đọc lời dẫn thực tế đang làm, và tránh việc một lần gọi nuốt trọn một đoạn dài.

Nối các đoạn cần ba thứ:

- **Chuẩn hoá mức âm của mỗi đoạn về RMS của clip trung tính.** Mỗi clip có độ to khác nhau;
  thiếu bước này thì chỗ nối nghe rõ bậc thang.
- **Fade ~30 ms ở mỗi mép đoạn trước khi chèn khoảng lặng.** Một câu tổng hợp thường kết thúc ở
  biên độ khác không, nên áp nó sát vào một khối số không là một chỗ gián đoạn — một tiếng click
  ở *mọi* chỗ nối của *mọi* lần render. Lỗi này từng được ship dưới dạng code chết: nhánh
  crossfade đã viết nhưng không bao giờ chạy được, vì khoảng lặng luôn được chèn trước. Hãy kiểm
  rằng nhánh như vậy thực sự chạy.
- **Chèn khoảng lặng dài hơn khi marker đổi** so với giữa các câu cùng một marker.

## Marker lạ phải bị gỡ, không bao giờ được đọc lên

Marker không có trong manifest phải biến mất khỏi văn bản. Kết cục tệ nhất là một từ trong
ngoặc bị đọc to trong file đã phát hành. Gỡ nó, quay về marker đang có hiệu lực, và báo lại —
nhưng không để nó lọt qua.

Tag nội tuyến gốc của engine thì ngược lại: để nguyên tại chỗ, engine sẽ tự xử lý.

## Thêm phong cách về sau

Build (`voice-studio lab build`) hỗ trợ chế độ **add** ngay từ đầu: gộp variant mới vào
manifest đã có mà không đụng các clip hiện có và không đổi clip trung tính trừ khi được bảo rõ.

Viết chế độ đó trước khi cần. Đợt ghi âm thứ hai lúc nào cũng tới, và vá thêm ngữ nghĩa gộp vào
một builder chỉ biết làm từ đầu là loại việc làm lại đáng tránh ngay từ lần đầu.

Chế độ add cần hai rào chắn:

- Ghi đè một marker đã có đòi hỏi cờ force tường minh.
- Force-ghi đè marker **trung tính** mà không cập nhật luôn bản phẳng sẽ để lại hai giọng gốc
  lệch nhau — đường có marker đọc một bản, loader thường đọc bản kia, không ai hay biết. Từ chối
  trường hợp này.

## Build nguyên tử

Dàn dựng mọi thứ trước, rồi commit trong một bước. Một lần build ghi variant dần dần rồi bỏ
giữa chừng — chẳng hạn vì cụm trung tính không đạt — sẽ để lại clip mới trên đĩa cạnh một
manifest cũ mô tả các clip khác. Không gì cảnh báo; manifest cứ thế nói sai.

## Bảo vệ kho giọng hiện có

Từ chối ghi đè một tên đã tồn tại dưới dạng profile thường không có manifest. Kho giọng thường
không nằm trong version control, nên gõ nhầm tên là mất không lấy lại được, và pipeline ghim
giọng theo đúng cái tên mà lỗi gõ đó sẽ phá hỏng.

## Profile độc lập từ variant

Đôi khi bạn muốn các phong cách thành những profile có tên riêng — để chọn một cái mỗi lần chạy,
hoặc để so sánh. Tách mỗi variant thành một profile thường; bản gốc nhiều phong cách vẫn nguyên
vẹn. Hai hình dạng phục vụ nhu cầu khác nhau: **marker** đổi cách đọc *bên trong* một tác phẩm;
**profile riêng** chọn giọng *cho* một tác phẩm.
