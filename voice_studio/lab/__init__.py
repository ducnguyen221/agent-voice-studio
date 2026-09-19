"""voice_studio.lab — bộ công cụ dựng profile ĐA SẮC THÁI (voicelab).

    vlab      lõi: đọc manifest `<tên>.profile.json`, cắt text theo marker, tổng hợp và nối
    verify    6 cổng kiểm tự động cho một clip mẫu (nghe ngược bằng ASR)
    mine      đào clip ứng viên theo sắc thái từ nhiều file ghi âm dài
    build     dựng/nạp thêm biến thể từ clip ứng viên đã đào
    split     tách một profile đa biến thể thành nhiều profile độc lập
    organize  sắp xếp kho giọng, archive file cũ (không xoá thẳng)

Gọi qua CLI: `voice-studio lab <mine|build|split|organize> …`, `voice-studio verify …`.
Chỗ làm việc (ứng viên, staging, demo) nằm ở `<VOICE_STUDIO_WORK>/lab/<tên>/` — ngoài repo.
"""
