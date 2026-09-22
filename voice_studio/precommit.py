"""precommit.py — hook pre-commit của chế độ `embedded`: chặn commit dữ liệu trạm và secret.

Chế độ embedded đặt trạm (giọng thật) và `.env` NGAY TRONG repo. `.gitignore` đã chặn chúng,
nhưng `git add -f` hay một `.gitignore` bị sửa là đủ để rò. Hook này là lớp rào thứ hai:

    - file dưới `workspace/`, `.env` / `.env.*` (trừ `.env.example`), `studio.local.json`
    - dòng THÊM MỚI trong diff trông giống token (GitHub, Hugging Face, OpenAI/Anthropic, AWS,
      Slack, Google, khoá riêng PEM, hoặc `token|secret|api_key = "<chuỗi dài>"`)

`voice-studio init` (embedded) cài hook gọi `python -m voice_studio.precommit`. Bỏ qua một lần
có chủ đích: `git commit --no-verify` — và tự chịu trách nhiệm.
"""
import re
import subprocess
import sys

BLOCKED_PREFIXES = ("workspace/",)
BLOCKED_FILES = ("studio.local.json",)

TOKEN_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{30,}"),
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(token|secret|api[_-]?key|password)\b\s*[:=]\s*['\"][^'\"\s]{16,}['\"]"),
]


def _git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return r.stdout


def _blocked_path(path):
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if p.startswith(BLOCKED_PREFIXES) or p in BLOCKED_FILES:
        return True
    if base == ".env" or (base.startswith(".env.") and base != ".env.example"):
        return True
    return False


def check(repo="."):
    """Danh sách vấn đề của phần đã stage (rỗng = cho commit)."""
    problems = []
    names = [n for n in _git(repo, "diff", "--cached", "--name-only", "-z").split("\0") if n]
    for n in names:
        if _blocked_path(n):
            problems.append(f"{n}: dữ liệu trạm/secret không được vào repo")
    current = None
    for line in _git(repo, "diff", "--cached", "-U0", "--no-color").splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            continue
        if line.startswith("+") and not line.startswith("+++"):
            for pat in TOKEN_PATTERNS:
                if pat.search(line):
                    problems.append(f"{current}: dòng thêm mới trông giống token/secret")
                    break
    return problems


def main(argv=None):
    try:
        problems = check(".")
    except (RuntimeError, OSError) as e:
        print(f"[voice-studio pre-commit] không kiểm được: {e}", file=sys.stderr)
        return 1
    if problems:
        print("[voice-studio pre-commit] CHẶN commit:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        print("Gỡ khỏi stage: git restore --staged <file>. Cố ý thì --no-verify.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
