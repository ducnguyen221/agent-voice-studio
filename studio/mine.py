"""
mine.py — đào clip mẫu theo SẮC THÁI từ các file ghi âm dài.

Đầu vào: nhiều file audio của CÙNG một người. Đầu ra: work/<name>.candidates.json
+ các clip .wav ứng viên, đã gán tên marker.

Cách làm (xem DESIGN.md mục 6-7):
  segment -> feature (ngôn điệu) -> z-score trong nội bộ giọng -> KMeans (k do silhouette)
  -> đặt tên marker bằng luật trên tâm cụm -> mỗi cụm lấy 3 clip gần tâm nhất.

Vì sao z-score TRONG nội bộ giọng: "trầm" của người này là "vừa" của người khác. So sánh
tuyệt đối giữa các giọng là vô nghĩa; chỉ so mỗi người với chính họ mới ra sắc thái.

  python mine.py --dir "recordings/speaker-a" --name narrator
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from _env import bootstrap
# Engine song tren may nguoi dung, khong nam trong repo -> khong duoc doan vi tri.
OMNI_DIR, VOICES = bootstrap()

import numpy as np
import soundfile as sf

SR = 24000
FRAME = 0.020          # cửa sổ RMS 20 ms
PAUSE_MIN = 0.25       # ngừng >= 0.25s mới tính là ranh giới câu
SIL_DROP_DB = 32.0     # ngưỡng lặng = (đỉnh RMS của file) - 32 dB
WIN_MIN, WIN_MAX = 12.0, 22.0   # độ dài clip ứng viên
WIN_IDEAL = 18.0
MAX_GAP = 1.2          # không nối hai đoạn nói cách nhau lâu hơn ngần này
LEAD_IN, TAIL_MAX = 0.15, 0.40
TAIL_MARGIN = 0.05     # chừa lại trước khi câu sau bắt đầu
K_RANGE = range(3, 9)
PICK_PER_CLUSTER = 3
SEED = 42

# Đặt tên MÔ TẢ theo ba trục z-score: P=cao độ, T=tốc độ, E=năng lượng.
#
# Bản đầu dùng bảng "vector nguyên mẫu" (hao-hung, thi-tham, ...) rồi gán cụm về nguyên mẫu
# gần nhất. Chạy thật trên 127 cửa sổ của một giọng thật thì 3/5 cụm không khớp nguyên mẫu nào — dữ
# liệu có những tổ hợp bảng đó không lường (vd cao giọng NHƯNG chậm). Nới ngưỡng cho khớp
# bừa còn tệ hơn: gọi một cụm NHANH là "thì thầm" là đặt tên sai sự thật. Nên bỏ bảng
# nguyên mẫu — tên sinh thẳng từ trục nào thực sự lệch.
TRAIT_MIN = 0.5        # |z| tối thiểu để một trục được coi là đặc điểm
AXIS_WORDS = (("cao", "tram"), ("nhanh", "cham"), ("manh", "nhe"))  # (dương, âm) cho P,T,E


def _ffmpeg():
    import mcp_server as ov
    return ov._ffmpeg_exe()


def decode(path):
    """Giải mã về mono 24 kHz float32.

    Tên file tạm phải DUY NHẤT: máy này hay chạy nhiều phiên agent song song, dùng chung
    một tên cố định thì phiên sau đè giữa chừng phiên trước -> feature rác, không báo lỗi.
    """
    fd, tmp = tempfile.mkstemp(prefix="vlab_dec_", suffix=".wav")
    os.close(fd)
    subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", path,
                    "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", tmp],
                   check=True, capture_output=True)
    y, sr = sf.read(tmp, dtype="float32")
    try:
        os.remove(tmp)
    except OSError:
        pass
    return y, sr


def utterance_runs(y, sr):
    """Trả các đoạn nói [(bắt đầu, kết thúc)] tách bởi khoảng ngừng >= PAUSE_MIN."""
    hop = int(sr * FRAME)
    n = len(y) // hop
    if n < 2:
        return []
    rms = np.sqrt(np.mean(y[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    peak = np.percentile(rms, 95)
    thr = peak * (10 ** (-SIL_DROP_DB / 20.0))
    voiced = rms > thr

    runs, i = [], 0
    min_sil = int(PAUSE_MIN / FRAME)
    while i < n:
        if not voiced[i]:
            i += 1
            continue
        j = i
        gap = 0
        while j < n:
            if voiced[j]:
                gap = 0
            else:
                gap += 1
                if gap >= min_sil:
                    break
            j += 1
        end = (j - gap) if gap else j
        if end > i:
            runs.append((i * FRAME, end * FRAME))
        i = j + 1
    return runs


def windows_from_runs(runs):
    """Gộp các đoạn nói liên tiếp thành cửa sổ WIN_MIN..WIN_MAX giây.

    Trả [(bắt_đầu, kết_thúc, khe_lặng_sau)].

    Cửa sổ luôn MỞ ở đầu một đoạn nói và ĐÓNG ở cuối một đoạn nói -> hai đầu đều là
    ranh giới câu. Đây chính là luật chống stutter-leak.

    KHÔNG nối qua khe lặng dài hơn MAX_GAP: độ dài cửa sổ tính cả phần im lặng ở giữa,
    nên nếu người nói nghỉ 10s (uống nước) thì một cửa sổ 21s "hợp lệ" có thể gần nửa là
    dead air -> pause_ratio méo, phân cụm sai, và clip mẫu rỗng tuếch.

    `khe_lặng_sau` để bên gọi cắt đuôi cho vừa: TAIL cố định 0.40s DÀI HƠN ngưỡng ngắt câu
    0.25s, nên với khe lặng ngắn thì đuôi clip sẽ nuốt luôn âm đầu của câu kế tiếp.
    """
    out = []
    for a in range(len(runs)):
        for b in range(a, len(runs)):
            if b > a and runs[b][0] - runs[b - 1][1] > MAX_GAP:
                break               # nghỉ quá lâu -> không nối tiếp nữa
            length = runs[b][1] - runs[a][0]
            if length < WIN_MIN:
                continue
            if length > WIN_MAX:
                break
            gap = (runs[b + 1][0] - runs[b][1]) if b + 1 < len(runs) else TAIL_MAX
            out.append((runs[a][0], runs[b][1], gap))
            break   # với mỗi điểm mở, lấy đúng một cửa sổ ngắn nhất hợp lệ
    # bỏ cửa sổ chồng lấn nhiều: giữ cái nào gần WIN_IDEAL nhất
    out.sort(key=lambda w: w[0])
    kept = []
    for w in out:
        if kept and w[0] < kept[-1][1] - 2.0:
            if abs((w[1] - w[0]) - WIN_IDEAL) < abs((kept[-1][1] - kept[-1][0]) - WIN_IDEAL):
                kept[-1] = w
            continue
        kept.append(w)
    return kept


def tail_for(gap):
    """Đuôi im được phép lấy: không bao giờ chạm vào âm đầu của câu kế tiếp."""
    return max(0.10, min(TAIL_MAX, gap - TAIL_MARGIN))


def features(seg, sr):
    """Đặc trưng NGÔN ĐIỆU (không phải nội dung): cao độ, tốc độ, năng lượng, nhịp ngừng."""
    import librosa
    f0 = librosa.yin(seg, fmin=60, fmax=400, sr=sr, hop_length=512)
    ok = f0[(f0 > 65) & (f0 < 350)]
    if ok.size < 20:
        return None
    hop = int(sr * FRAME)
    n = len(seg) // hop
    rms = np.sqrt(np.mean(seg[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    peak = np.percentile(rms, 95)
    thr = peak * (10 ** (-SIL_DROP_DB / 20.0))
    dur = len(seg) / sr
    onsets = librosa.onset.onset_detect(y=seg, sr=sr, units="time")
    return {
        "f0_med": float(np.median(ok)),
        "f0_range": float(np.percentile(ok, 90) - np.percentile(ok, 10)),
        "rate": float(len(onsets) / dur) if dur > 0 else 0.0,
        "rms_db": float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)),
        "pause_ratio": float(np.mean(rms <= thr)),
        "centroid": float(np.mean(librosa.feature.spectral_centroid(y=seg, sr=sr))),
        "peak_db": float(20 * np.log10(np.max(np.abs(seg)) + 1e-12)),
        "f0_fail": float(1.0 - ok.size / max(1, f0.size)),
    }


def slugify(s):
    """Tên file -> slug ASCII dùng được làm marker ([a-z0-9-])."""
    s = os.path.splitext(os.path.basename(s))[0]
    s = s.split("-", 1)[1] if "-" in s else s          # bỏ tiền tố tên người
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d")
    s = "".join(c if c.isalnum() else "-" for c in s)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


def _describe(pte):
    """Tên mô tả từ tâm cụm: ghép các trục lệch mạnh, theo thứ tự cố định P-T-E."""
    parts = [AXIS_WORDS[i][0 if z > 0 else 1]
             for i, z in enumerate(pte) if abs(z) >= TRAIT_MIN]
    if parts:
        return "-".join(parts)
    # Không trục nào đủ mạnh nhưng cũng không phải cụm trung tính -> lấy trục lệch nhất.
    i = int(np.argmax([abs(z) for z in pte]))
    return "hoi-" + AXIS_WORDS[i][0 if pte[i] > 0 else 1]


def label_clusters(centroids_pte):
    """Gán tên marker cho từng cụm. Deterministic; tên MÔ TẢ đúng cái đo được.

    Cụm gần gốc toạ độ nhất = giọng nền của người này -> 'giang-bai', và nó thành clip
    trung tính của profile.
    """
    norms = [float(np.linalg.norm(c)) for c in centroids_pte]
    neutral = int(np.argmin(norms))
    names = {neutral: "giang-bai"}

    for i, c in enumerate(centroids_pte):
        if i == neutral:
            continue
        nm = _describe(c)
        if nm in names.values():   # trùng tên: thêm hậu tố phân biệt
            nm = f"{nm}-2"
            while nm in names.values():
                nm = nm[:-1] + str(int(nm[-1]) + 1)
        names[i] = nm
    return names, neutral


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="Thư mục chứa file ghi âm nguồn.")
    ap.add_argument("--files", nargs="*", default=[], help="Hoặc liệt kê file cụ thể.")
    ap.add_argument("--name", required=True, help="Tên profile sẽ dựng, vd narrator.")
    ap.add_argument("--no-per-source", action="store_true",
                    help="Chỉ lấy marker theo phân cụm âm học, bỏ marker theo tình huống.")
    args = ap.parse_args()

    srcs = list(args.files)
    if args.dir:
        for ext in ("*.mp3", "*.MP3", "*.wav", "*.WAV", "*.m4a"):
            srcs += glob.glob(os.path.join(args.dir, ext))
    srcs = sorted(set(os.path.abspath(s) for s in srcs))
    if not srcs:
        ap.error("không có file nguồn")

    work = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", args.name)
    clips_dir = os.path.join(work, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    rows = []
    for path in srcs:
        print(f"[mine] {os.path.basename(path)} ...", flush=True)
        y, sr = decode(path)
        runs = utterance_runs(y, sr)
        wins = windows_from_runs(runs)
        print(f"[mine]   {len(runs)} đoạn nói -> {len(wins)} cửa sổ ứng viên", flush=True)
        for (a, b, gap) in wins:
            seg = y[int(a * sr):int(b * sr)]
            f = features(seg, sr)
            if f is None:
                continue
            f.update({"file": path, "start": round(a, 3), "dur": round(b - a, 3),
                      "tail": round(tail_for(gap), 3)})
            rows.append(f)

    if len(rows) < 12:
        print(f"[mine] quá ít cửa sổ ({len(rows)}) — không phân cụm được.")
        sys.exit(1)
    print(f"[mine] tổng {len(rows)} cửa sổ ứng viên", flush=True)

    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    # Trung hoà MỨC THU theo từng file trước khi phân cụm.
    #
    # rms_db tuyệt đối không đo cách nói, nó đo mức thu. Đo thật: "Thuyết trình tự nhiên"
    # có RMS -30.9 dB còn các file khác -20..-24 dB — chênh gần 10 dB chỉ vì gain lúc thu.
    # Hậu quả bắt được tận tay: cụm âm học 'tram-nhanh-nhe' (n=28) trùng khít file đó (n=27),
    # tức thuật toán đang phân cụm theo FILE chứ không theo sắc thái. Trừ đi trung vị của
    # chính file mình thì rms_db mới mang nghĩa "câu này nói to/nhỏ hơn thường ngày của
    # người ấy". Không đụng f0: cùng một người thì cao độ tuyệt đối vẫn có nghĩa qua các buổi.
    med_by_file = {}
    for r in rows:
        med_by_file.setdefault(r["file"], []).append(r["rms_db"])
    med_by_file = {f: float(np.median(v)) for f, v in med_by_file.items()}
    for r in rows:
        r["rms_rel"] = r["rms_db"] - med_by_file[r["file"]]

    keys = ["f0_med", "f0_range", "rate", "rms_rel", "pause_ratio", "centroid"]
    X = np.array([[r[k] for k in keys] for r in rows], dtype="float64")
    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
    Z = (X - mu) / sd

    best = None
    for k in K_RANGE:
        if k >= len(rows):
            break
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Z)
        s = silhouette_score(Z, km.labels_)
        print(f"[mine]   k={k}  silhouette={s:.4f}")
        if best is None or s > best[0]:
            best = (s, k, km)
    score, k, km = best
    print(f"[mine] chọn k={k} (silhouette={score:.4f})")

    # gộp cụm quá nhỏ vào cụm gần nhất
    labels = km.labels_.copy()
    for ci in range(k):
        if np.sum(labels == ci) >= 4:
            continue
        others = [c for c in range(k) if c != ci and np.sum(labels == c) >= 4]
        if not others:
            continue
        d = [np.linalg.norm(km.cluster_centers_[ci] - km.cluster_centers_[c]) for c in others]
        labels[labels == ci] = others[int(np.argmin(d))]

    alive = sorted(set(int(v) for v in labels))
    idx_of = {c: i for i, c in enumerate(alive)}
    pte = [(km.cluster_centers_[c][keys.index("f0_med")],
            km.cluster_centers_[c][keys.index("rate")],
            km.cluster_centers_[c][keys.index("rms_rel")]) for c in alive]
    names, neutral_i = label_clusters(pte)

    out = {"name": args.name, "k": len(alive), "silhouette": round(float(score), 4),
           "neutral": names[neutral_i], "seed": SEED, "clusters": {}}

    for c in alive:
        i = idx_of[c]
        marker = names[i]
        mask = labels == c
        members = [j for j in range(len(rows)) if mask[j]]
        d = [float(np.linalg.norm(Z[j] - km.cluster_centers_[c])) for j in members]
        order = [members[t] for t in np.argsort(d)]
        # ưu tiên clip dài gần WIN_IDEAL trong nhóm 8 gần tâm nhất
        head = order[:8]
        head.sort(key=lambda j: abs(rows[j]["dur"] - WIN_IDEAL))
        picks = head[:PICK_PER_CLUSTER]

        cands = []
        for rank, j in enumerate(picks, 1):
            r = rows[j]
            wav = os.path.join(clips_dir, f"{marker}_{rank}.wav")
            ss = max(0.0, r["start"] - LEAD_IN)
            tt = r["dur"] + LEAD_IN + r["tail"]
            subprocess.run([_ffmpeg(), "-y", "-v", "error", "-ss", f"{ss:.3f}",
                            "-t", f"{tt:.3f}", "-i", r["file"], "-vn", "-ac", "1",
                            "-ar", str(SR), "-c:a", "pcm_s16le", wav],
                           check=True, capture_output=True)
            cands.append({"rank": rank, "wav": wav,
                          "source": {"file": os.path.basename(r["file"]),
                                     "start": r["start"], "dur": r["dur"]},
                          "features": {kk: round(r[kk], 3) for kk in
                                       keys + ["peak_db", "f0_fail"]}})
        out["clusters"][marker] = {
            "kind": "acoustic",
            "size": int(mask.sum()),
            "centroid_pte": [round(float(v), 3) for v in pte[i]],
            "candidates": cands,
        }
        print(f"[mine] {marker:<12} n={int(mask.sum()):<4} "
              f"P={pte[i][0]:+.2f} T={pte[i][1]:+.2f} E={pte[i][2]:+.2f}  "
              f"-> {len(cands)} clip")

    # ---- Marker theo TÌNH HUỐNG (nguồn) ----------------------------------------------
    # Phân cụm thuần âm học vứt mất một thông tin quý: người thu đã CHỦ Ý ghi từng tình
    # huống riêng và đặt tên file theo tình huống đó. Đấy là nhãn ngữ cảnh do con người gán,
    # máy không suy ra được từ sóng âm. Silhouette lại có thiên hướng chọn ít cụm (ở đây k=3),
    # nên nếu chỉ nghe theo nó thì 5 tình huống thu công phu bị gộp còn 3 sắc thái.
    # Hai loại marker bổ sung cho nhau, không thay thế nhau.
    if not args.no_per_source:
        for path in srcs:
            marker = slugify(path)
            if not marker or marker in out["clusters"]:
                print(f"[mine] bỏ marker nguồn '{marker}' (trùng tên hoặc rỗng)")
                continue
            members = [j for j in range(len(rows)) if rows[j]["file"] == path]
            if len(members) < 3:
                print(f"[mine] bỏ marker nguồn '{marker}' (chỉ {len(members)} cửa sổ)")
                continue
            centre = Z[members].mean(axis=0)
            order = sorted(members, key=lambda j: float(np.linalg.norm(Z[j] - centre)))
            head = order[:8]
            head.sort(key=lambda j: abs(rows[j]["dur"] - WIN_IDEAL))
            cands = []
            for rank, j in enumerate(head[:PICK_PER_CLUSTER], 1):
                r = rows[j]
                wav = os.path.join(clips_dir, f"{marker}_{rank}.wav")
                ss = max(0.0, r["start"] - LEAD_IN)
                tt = r["dur"] + LEAD_IN + r["tail"]
                subprocess.run([_ffmpeg(), "-y", "-v", "error", "-ss", f"{ss:.3f}",
                                "-t", f"{tt:.3f}", "-i", r["file"], "-vn", "-ac", "1",
                                "-ar", str(SR), "-c:a", "pcm_s16le", wav],
                               check=True, capture_output=True)
                cands.append({"rank": rank, "wav": wav,
                              "source": {"file": os.path.basename(r["file"]),
                                         "start": r["start"], "dur": r["dur"]},
                              "features": {kk: round(r[kk], 3) for kk in
                                           keys + ["peak_db", "f0_fail"]}})
            pte = [float(centre[keys.index(k)]) for k in ("f0_med", "rate", "rms_rel")]
            out["clusters"][marker] = {
                "kind": "situation", "size": len(members),
                "centroid_pte": [round(v, 3) for v in pte], "candidates": cands}
            print(f"[mine] {marker:<24} n={len(members):<4} "
                  f"P={pte[0]:+.2f} T={pte[1]:+.2f} E={pte[2]:+.2f}  (tình huống)")

    js = os.path.join(work, "candidates.json")
    with open(js, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"[mine] -> {js}")


if __name__ == "__main__":
    main()
