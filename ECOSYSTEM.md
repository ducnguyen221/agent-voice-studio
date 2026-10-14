# ECOSYSTEM — Agent Voice Studio trong hệ thống ACD

## 🤝 ACD Ecosystem Integration
- **Role in ACD:** Studio thuộc Nhóm 2 (Production Studio) — xưởng giọng nói và TTS: tách phong cách giọng từ bản ghi dài, cổng kiểm tự động, điều khiển cách đọc ngay trong kịch bản và bộ quy tắc phát âm tiếng Việt. `agent-skill-studio` là xưởng nền cấp chuẩn `SKILL.md` portable, công cụ kiểm (`validate`/`audit`/`package`) và đóng gói skill; repo này tự giữ nghiệp vụ của mình, không nhờ xưởng nền viết thay.
- **Upstream Controllers:** Repo marketing (podcast, quảng cáo audio) và `agent-academy-team` (giọng giảng bài) ở mức Cốt lõi, `agent-customer-team` (hướng dẫn bằng giọng) ở mức Thường xuyên. `agent-writing-studio` cấp kịch bản để đọc.
- **Downstream Consumers:** `agent-video-studio` nhận âm thanh kèm mốc thời gian để đồng bộ hiệu ứng; các Team nhận file âm thanh hoàn chỉnh.
- **Recommended Bundles:** Bundle A (lồng tiếng) và Bundle C (giảng bài tự động). Không thuộc Bundle E.
- **Handoff Artifacts:** Đầu vào là `production-brief.md` do Team giao kèm văn bản cần đọc và hồ sơ giọng. Đầu ra là file âm thanh cùng mốc thời gian và biên nhận nghiệm thu; chỉ phát hành sau các cổng kiểm đã có của repo.
