---
name: refund-policy
description: Tra cứu chính sách hoàn tiền và xác định điều kiện, thời hạn, phí theo ngày mua của khách hàng. Dùng khi người dùng hỏi có được hoàn tiền hoặc chính sách hoàn tiền nào áp dụng cho đơn hàng.
---

# Tra cứu chính sách hoàn tiền

- Cần ngày mua, ngày yêu cầu hoàn và trạng thái kích hoạt. Nếu thiếu hoặc mơ hồ, hỏi lại thông tin còn thiếu trước khi kết luận; không tự giả định chưa kích hoạt. Dùng ngày yêu cầu người dùng cung cấp, không dùng ngày hiện tại. Nếu ngày yêu cầu trước ngày mua, yêu cầu xác nhận lại ngày.
- Dùng `list_files` với `data/policies/` (đường dẫn từ gốc workspace), rồi `read_file` với đường dẫn trong kết quả để đọc tài liệu. Không cố định tên file; đọc các tài liệu chính sách để xác định phạm vi hiệu lực từ nội dung.
- Chọn phiên bản theo **ngày mua**, không theo ngày yêu cầu hoàn hoặc tên file. Đọc rõ mốc bắt đầu/kết thúc và quy định có bao gồm ngày biên hay không. Nếu không có phiên bản phù hợp, nội dung mâu thuẫn hoặc có nhiều phiên bản cùng áp dụng mà không rõ ưu tiên, báo chưa đủ căn cứ và hỏi lại; không đoán.
- Tính số ngày bằng chênh lệch ngày lịch giữa ngày yêu cầu và ngày mua. Bằng đúng giới hạn vẫn đạt điều kiện thời gian. Kiểm tra cả thời hạn và trạng thái kích hoạt theo chính sách đã đọc. Chỉ nêu phí áp dụng khi đủ điều kiện; nếu thiếu giá trị đơn hàng, nêu tỷ lệ hoặc quy tắc phí thay vì tự tính số tiền.
- Trước khi trả lời, đọc [mẫu câu trả lời](references/answer-template.md) bằng `read_file` tại `skills/refund-policy/references/answer-template.md`. Dẫn đúng đường dẫn tài liệu đã đọc làm căn cứ.
- Thực hiện bằng `list_files` và `read_file`; không yêu cầu Bash hay script.
