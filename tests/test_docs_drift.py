"""Cổng chống trôi tài liệu: README và trang giới thiệu phải nói đúng thứ mã đang làm.

Vì sao cần cổng này: tài liệu và trang web là thứ người ngoài đọc TRƯỚC khi chạy lệnh đầu
tiên. Khi mã đổi mà chữ không đổi, người đọc không thấy lỗi — họ chỉ thấy một lệnh không tồn
tại, hoặc không bao giờ biết một lệnh đã có. Cổng rẻ tiền: đọc `cli.COMMANDS` (nguồn duy nhất
mà `--help` cũng đọc) rồi đối chiếu với chữ.

Hai chiều, cố ý:
  · mã → chữ: lệnh nào có trong `COMMANDS` mà không được nhắc tới là đỏ (thêm lệnh, quên kể).
  · chữ → mã: tên nào nằm trong BẢNG LỆNH của trang mà không có trong `COMMANDS` là đỏ
    (bỏ lệnh, quên xoá — kiểu trôi im lặng hơn, vì không ai thử lệnh trong tài liệu cũ).
"""
import re
from pathlib import Path

import pytest

from voice_studio import __version__, cli

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "index.html"
READMES = ("README.md", "README.vi.md")


def _page():
    if not PAGE.is_file():
        pytest.skip("repo chưa có trang giới thiệu")
    return PAGE.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(cli.COMMANDS))
def test_page_lists_every_command(name):
    assert name in _page(), f"trang giới thiệu không nhắc lệnh `{name}`"


@pytest.mark.parametrize("name", sorted(cli.COMMANDS))
def test_readme_lists_every_command(name):
    for rel in READMES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert name in text, f"{rel} không nhắc lệnh `{name}`"


@pytest.mark.parametrize("name", sorted(cli.LAB))
def test_lab_subcommands_are_documented(name):
    assert name in _page(), f"trang giới thiệu không nhắc lệnh con `lab {name}`"


def _page_command_table():
    """Tên lệnh in trong BẢNG LỆNH của trang (mục #lenh), theo ô `<td class="lbl…">`."""
    text = _page()
    block = re.search(r'<section id="lenh">(.*?)</section>', text, flags=re.S)
    assert block, "trang giới thiệu phải có mục #lenh chứa bảng lệnh"
    return set(re.findall(r'<td class="lbl[^"]*">([a-z][a-z-]*)</td>', block.group(1)))


def test_page_command_table_invents_nothing():
    thua = _page_command_table() - set(cli.COMMANDS)
    assert not thua, f"bảng lệnh của trang kể lệnh không có trong mã: {sorted(thua)}"


def test_page_command_table_is_complete():
    thieu = set(cli.COMMANDS) - _page_command_table()
    assert not thieu, f"bảng lệnh của trang thiếu lệnh: {sorted(thieu)}"


def test_page_states_the_current_version():
    assert __version__ in _page(), (
        f"trang giới thiệu không nói đúng phiên bản {__version__} — "
        "phát hành bản mới thì sửa cả trang")


def test_page_states_the_exit_code_contract():
    """Hợp đồng mã thoát là thứ pipeline khác dựa vào; trang không được kể sai hay bỏ sót."""
    text = _page()
    for code in ("0", "1", "2", "3"):
        assert f"<b>{code}</b>" in text, f"trang thiếu mã thoát {code} trong hợp đồng"
