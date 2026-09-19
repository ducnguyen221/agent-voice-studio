"""contract.py — hợp đồng gọi từ pipeline khác: mã thoát, lỗi có tên, một dòng JSON cuối stdout.

Mọi lệnh `voice-studio …` mà một chương trình khác gọi (marketing, trạm video, lịch chạy)
tuân cùng một hợp đồng, để bên gọi chỉ cần đọc MÃ THOÁT và DÒNG JSON CUỐI:

    0  ok
    1  lỗi engine / render — chạy lại có thể được (hết VRAM, ffmpeg sập…)
    2  hợp đồng sai — thiếu tham số, thiếu profile, text rỗng: phải SỬA CẤU HÌNH, chạy lại vô ích
    3  trạm thiếu — chưa có trạm giọng, chưa cài engine: phải CÀI TIẾP (`voice-studio doctor`)

Với `--json`: stdout kết thúc bằng ĐÚNG MỘT dòng JSON (`{"ok": true, …}` hoặc
`{"ok": false, "code": N, "error": "…"}`); mọi log người đọc đi ra stderr. Bên gọi lấy dòng
cuối không rỗng của stdout — log lạc vào stdout phía trước vẫn không làm hỏng việc parse.

Bẫy PowerShell 5.1: đừng `2>&1` khi gọi lệnh native — mỗi dòng stderr bị bọc thành lỗi và
`$?` thành False dù mã thoát là 0. Đọc `$LASTEXITCODE`.
"""
import json
import sys
import traceback

OK, ENGINE_ERROR, CONTRACT_ERROR, STATION_MISSING = 0, 1, 2, 3

__all__ = [
    "OK", "ENGINE_ERROR", "CONTRACT_ERROR", "STATION_MISSING",
    "VoiceStudioError", "EngineError", "ContractError", "StationMissing",
    "log", "emit", "run", "parse",
]


class VoiceStudioError(Exception):
    code = ENGINE_ERROR


class EngineError(VoiceStudioError):
    """Engine/render hỏng giữa chừng — thử lại có thể qua."""
    code = ENGINE_ERROR


class ContractError(VoiceStudioError):
    """Bên gọi truyền sai: thiếu tham số, profile không có, text rỗng."""
    code = CONTRACT_ERROR


class StationMissing(VoiceStudioError):
    """Trạm giọng hoặc engine chưa cài — `voice-studio doctor` sẽ chỉ bước còn thiếu."""
    code = STATION_MISSING


def log(*parts):
    """Log cho người đọc: LUÔN ra stderr, để stdout chỉ còn kết quả."""
    print(*parts, file=sys.stderr, flush=True)


def emit(payload):
    """In một dòng JSON (UTF-8, không escape tiếng Việt) ra stdout."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def classify(exc):
    """Map một exception về mã thoát của hợp đồng."""
    if isinstance(exc, VoiceStudioError):
        return exc.code
    from .profiles import ProfileError
    if isinstance(exc, ProfileError):
        return CONTRACT_ERROR
    if isinstance(exc, ImportError):
        # torch / omnivoice / soundfile chưa cài trong venv đang chạy = trạm chưa đủ.
        return STATION_MISSING
    return ENGINE_ERROR


def run(fn, args, as_json=False):
    """Chạy `fn(args) -> dict`, trả mã thoát; `as_json` ⇒ in dòng JSON cuối stdout.

    `fn` trả dict kết quả (sẽ được thêm `"ok": true`); ném exception để báo lỗi.
    """
    try:
        result = fn(args) or {}
    except KeyboardInterrupt:
        raise
    except Exception as exc:        # noqa: BLE001 — biên của CLI: mọi lỗi phải thành mã thoát
        code = classify(exc)
        msg = str(exc) or exc.__class__.__name__
        log(f"[voice-studio] LỖI ({code}): {msg}")
        if code == ENGINE_ERROR:
            log(traceback.format_exc().rstrip())
        if as_json:
            emit({"ok": False, "code": code, "error": msg})
        return code
    if as_json:
        emit({"ok": True, **result})
    return OK


def parse(ap, argv=None):
    """argparse theo hợp đồng: -> (args, None) hoặc (None, mã thoát).

    `--help` ⇒ mã 0; tham số sai ⇒ mã 2 (và dòng JSON lỗi nếu người gọi xin `--json`),
    thay vì để SystemExit của argparse lọt ra ngoài.
    """
    try:
        return ap.parse_args(argv), None
    except SystemExit as e:
        if e.code in (0, None):
            return None, OK
        raw = sys.argv[1:] if argv is None else list(argv)
        if "--json" in raw:
            emit({"ok": False, "code": CONTRACT_ERROR, "error": "tham số không hợp lệ (xem stderr)"})
        return None, CONTRACT_ERROR
