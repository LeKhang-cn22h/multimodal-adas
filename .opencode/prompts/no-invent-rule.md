# Prompt dùng chung: Không tự suy diễn

Dùng đoạn này trong agent/command ở các bước ra quyết định (architect,
techsolution, implement khi gặp mơ hồ).

---

Trước khi giả định bất kỳ điều gì chưa rõ trong yêu cầu: kiểm tra
`.opencode/memory/open-questions.md` xem đã có câu hỏi tương tự chưa. Nếu
điều mơ hồ ẢNH HƯỞNG tới quyết định kiến trúc hoặc acceptance criteria,
PHẢI hỏi lại người dùng, không tự chọn phương án "hợp lý nhất" rồi âm thầm
implement. Nếu điều mơ hồ KHÔNG ảnh hưởng tới kết quả cuối (chỉ là chi tiết
trình bày), có thể tự quyết và nêu rõ giả định đã chọn trong output.