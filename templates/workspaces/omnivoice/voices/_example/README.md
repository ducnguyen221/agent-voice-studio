# Giọng ví dụ trung tính

Repo không phát hành giọng của ai — kể cả giọng mẫu. Thư mục này chỉ hướng dẫn bạn **tự tạo** một
giọng ví dụ trung tính để thử cả chuỗi mà không cần ghi âm ai.

Tên bắt đầu bằng `_` nên kho giọng không coi thư mục này là profile.

## Tạo giọng `sample` bằng thiết kế giọng (không cần bản ghi)

Sau khi venv engine đã cài và `voice-studio doctor` xanh:

```bash
voice-studio make-profile --name sample --instruct "female, young adult, moderate pitch"
voice-studio speak --file omnivoice/voices/_example/sample.txt --profile sample --out out/thu.wav --json
```

(Chạy từ gốc trạm.) `make-profile --instruct` đọc một câu mẫu cố định MỘT lần rồi **đóng băng** kết quả thành
`voices/sample.wav` + `voices/sample.txt`. Từ đó mọi câu dùng cùng một giọng. Từ khoá `--instruct`
là bộ tiếng Anh của OmniVoice (giới tính, tuổi, cao độ…); đổi từ khoá là ra giọng khác.

Muốn dùng làm mặc định: thêm `--set-default`, hoặc ghi `sample` vào `voices/_default.txt`.

## Giọng thật của bạn

Dùng `voice-studio make-profile --audio <bản ghi> --name <tên>` hoặc bộ `voice-studio lab`.
**Chỉ clone giọng của chính bạn, hoặc giọng mà chủ nhân đã đồng ý bằng văn bản.**
