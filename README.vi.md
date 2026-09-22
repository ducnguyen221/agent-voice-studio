# Agent Voice Studio

Quy trình sản xuất giọng để một AI agent chạy trọn vẹn: từ hàng giờ ghi âm thô đến một giọng
đọc đã được kiểm chứng, mà sắc thái do chính kịch bản điều khiển.

**[English](README.md)** · [Hướng dẫn](GUIDE.vi.md) · [Trang giới thiệu](https://ducnguyen.vn/agent-voice-studio/) · MIT

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

Cũng **không phải một mảnh của bộ nào phải cài đủ**. Repo này đứng một mình: cài nó khi anh
cần một giọng đọc, và chỉ khi đó. Một quy trình sản xuất nội dung (ví dụ
`agent-marketing-studio`) *gọi được* nó qua hợp đồng mã thoát + dòng JSON cuối stdout nếu nó
có mặt — nhưng quy trình đó chạy bình thường khi anh chưa cài, và sẽ nói rõ là đang thiếu
năng lực giọng thay vì nổ giữa chừng. Không có thứ tự cài bắt buộc, không có "bộ ba".

## Cài

```bash
git clone https://github.com/ducnguyen221/agent-voice-studio
cd agent-voice-studio
```

Tạo venv, cài torch theo hệ điều hành + `omnivoice==0.2.1`, rồi cài package và dựng trạm giọng.
Các bước đầy đủ ở [`docs/INSTALL.md`](docs/INSTALL.md) — cài vào venv nào, hai chế độ trạm, khuôn
`.env`, và bảng **cái gì đã chạy thật trên nền tảng nào**. Phần riêng của engine, kèm cảnh báo
giấy phép weights (CC-BY-NC) và hai cạm bẫy từng tốn thời gian thật, nằm ở
[`skills/voice-routing/references/install-omnivoice.md`](skills/voice-routing/references/install-omnivoice.md).

```bash
pip install -e .          # trong venv engine — lệnh voice-studio
voice-studio init         # hỏi đặt trạm trong repo (embedded, khuyến nghị) hay ngoài (separate)
voice-studio doctor       # thiếu gì thì chỉ bước cài tiếp
```

`init` **trình bảng hai lựa chọn rồi mới làm**, chứ không hỏi trống: `embedded` (trạm ở
`<repo>/workspace/`, biến cấu hình ở `<repo>/.env`) là **khuyến nghị** — bấm Enter là xong,
không phải đặt biến môi trường nào. Chọn `separate` khi anh dùng nhiều máy, rành kỹ thuật,
hoặc repo này là bản public của chính anh. Không có ai trả lời (CI, lịch chạy) thì `init`
in bảng đó ra rồi **thoát mã 2 mà chưa ghi byte nào** — agent cài phải đưa bảng cho người
dùng xem, không tự chọn im lặng.

Chế độ `embedded` là "clone là chạy": `init` dựng sẵn cây trạm và chép `.env.example` thành
`<repo>/.env` cho anh điền. Cả `workspace/` lẫn `.env` đều bị `.gitignore` chặn và hook
`pre-commit` chặn lần nữa. `.env` giữ **đường dẫn và cấu hình**, không bao giờ giữ token.

Trạm giọng là nơi chứa venv, giọng, nhạc nền, output của anh — từng thư mục giải thích ở
[`docs/WORKSPACE.md`](docs/WORKSPACE.md). Nhạc nền tự sinh: [`docs/bgm-generation.md`](docs/bgm-generation.md).

Cài như plugin cho agent:

```bash
claude plugin marketplace add ducnguyen221/agent-voice-studio
claude plugin install agent-voice-studio@agent-voice-studio
```

## Dùng

```bash
voice-studio lab mine  --dir recordings/ --name narrator   # tìm các sắc thái
voice-studio lab build --name narrator --mode new          # chấm clip, dựng profile
voice-studio speak --file script.txt --profile narrator --out out.mp3
```

Đào và dựng làm **một lần** cho mỗi giọng. Viết và đọc thì làm mỗi lần.

### Lệnh `voice-studio` (package `voice_studio`)

Cùng bộ công cụ, gom về một lệnh chạy bằng python của venv engine
(`python -m voice_studio …` khi chưa cài lệnh):

Đây là **toàn bộ** danh sách — đúng bảng mà `voice-studio --help` in ra, và có một test giữ cho
hai bên không trôi khỏi nhau:

| Lệnh | Làm gì |
|---|---|
| `speak` | text → file audio (hợp đồng ổn định, `--json`, mã 0/1/2/3) |
| `narrate` | video câm + lời dẫn → MP4 có giọng (+ nhạc nền) |
| `make-profile` | tạo profile giọng từ bản ghi / video / instruct |
| `clone` | dựng profile từ media dài hoặc URL — **cần `--consent`** |
| `verify` | soi một clip mẫu qua 6 cổng kiểm |
| `reftext` | thêm dấu ngắt vào lời mẫu theo khoảng lặng thật |
| `clean` | tách giọng + khử tạp âm cho clip mẫu (xem `voice_studio/clean/README.md`) |
| `bgm` | thư viện nhạc nền: `list` \| `pick <style>` |
| `tts` | đọc nhanh một câu ra file |
| `ui` | giao diện web cục bộ để nghe thử |
| `doctor` | kiểm trạm giọng, chỉ bước cài còn thiếu |
| `mcp` | chạy MCP server (stdio) cho agent |
| `lab` | bộ dựng profile đa sắc thái: `mine` \| `build` \| `split` \| `organize` |
| `init` | dựng trạm (embedded \| separate) + `station.json` |
| `export` | đóng gói giọng cá nhân để chuyển máy (`--personal`) |
| `import` | nhập gói giọng cá nhân |
| `backup` | zip cả trạm (không venv/cache/out) |
| `migrate` | chuyển trạm embedded ra ngoài repo |
| `update` | cập nhật repo (`git pull --ff-only`) |

```bash
voice-studio speak --text "Xin chào" --profile narrator --out a.wav --json   # pipeline khác gọi
voice-studio narrate --video cam.mp4 --file script.txt --out final.mp4 --json
voice-studio make-profile --audio rec.wav --start 120 --dur 18 --name narrator
voice-studio clone --file talk.m4a --name narrator --consent
voice-studio lab mine|build|split|organize …     # bộ dựng đa sắc thái ở trên
voice-studio export --personal --out giong.zip   # chuyển máy: giọng + nhạc nền + station.json
```

`speak`/`narrate` là **hợp đồng ổn định** cho pipeline khác: `--json` in đúng một dòng JSON
cuối stdout, log ra stderr, mã thoát `0` ok · `1` lỗi engine · `2` gọi/cấu hình sai (thiếu
profile, text rỗng) · `3` trạm/engine chưa cài. Các lệnh `python studio/*.py` cũ vẫn chạy
(là alias). `clone` và `make-profile` chỉ dùng cho giọng **đã được đồng ý** — xem luật 4.

Agent đã cài plugin sẽ đọc `skills/voice-routing/SKILL.md` và chỉ nạp đúng reference của bước
đang làm.

## Quy tắc

Đây không phải lời khuyên. Ba luật đầu là lý do quy trình này tồn tại; luật thứ tư là **điều
kiện** để được dùng nó.

1. **Đừng tin tai — hãy đo.** Tổng hợp, cho nhận dạng nghe lại, so. "Nghe hay hơn" không phải
   kết quả.
2. **Ghim seed.** Engine không tái lập nếu không ghim. Phép so không seed là đang đo nhiễu.
3. **Clip mẫu hỏng thì hỏng mọi thứ sinh ra từ nó.** Đừng bao giờ cho qua lấy lệ.
4. **Chỉ clone giọng của chính mình, hoặc người đã đồng ý bằng văn bản.** `clone` và
   `make-profile` chỉ dùng cho giọng đã được đồng ý; `clone` đòi cờ `--consent` tường minh để
   không ai lỡ tay. **Xin phép TRƯỚC khi clone giọng người khác** là điều kiện dùng repo này,
   không phải một bước có thể bỏ khi vội.
5. **Kiểm giấy phép của từng checkpoint mình tải.** Giấy phép của weights đi đường riêng với
   giấy phép của code — xem mục [Ghi công](#ghi-công).

Repo này **không chứa một file audio nào**, và một cổng trong bộ test chặn tên profile thật,
đường dẫn máy cùng các file `*.wav` / `*.mp3` / `*.pt` trước khi một commit đi qua.

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
