"""voice_studio.clean — tách giọng người + khử tạp âm, ra WAV sạch làm clip mẫu cho clone.

Hai tầng, hai venv RIÊNG (xung đột numpy >=2 / <2), đặt ở thư mục công cụ làm sạch của trạm
(`VOICE_CLEAN_DIR` → `$VOICE_STATION/voice-clean`):

    tầng 1  audio-separator (BS-Roformer)      tách vocal khỏi nhạc/tiếng động   .venv-sep
    tầng 2  ClearerVoice (MossFormer2_SE_48K)  khử nhiễu + dereverb              .venv-cv

Hai file trong gói này TỰ CHỨA (không import `voice_studio`) vì chúng được chạy bằng python
của hai venv tách — venv đó không cài package. Cài đặt + tải model: xem README.md cạnh file này.
"""
