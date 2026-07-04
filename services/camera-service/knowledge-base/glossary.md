# Thuật ngữ - Camera-Service

## A

### AMQP
Advanced Message Queuing Protocol. Giao thức chuẩn cho message-oriented middleware. RabbitMQ implements AMQP 0-9-1.

### Auto-ack
Tự động gửi acknowledgment khi consumer nhận message. Nếu `auto_ack=True`, message bị xóa khỏi queue ngay khi gửi đến consumer, bất kể consumer xử lý thành công hay không.

## B

### Back-pressure
Cơ chế giới hạn tốc độ gửi message khi consumer không xử lý kịp. RabbitMQ tự nhiên cung cấp back-pressure qua queue depth.

### basic_consume
Phương thức AMQP để đăng ký consumer cho một queue. Consumer sẽ nhận message tự động khi có message mới.

### basic_publish
Phương thức AMQP để gửi message vào exchange.

## C

### Channel
Kênh giao tiếp ảo trong một AMQP connection. Nhiều channel có thể chia sẻ một connection, giảm overhead.

### Connection
Kết nối TCP đến RabbitMQ broker. Một connection có thể có nhiều channel.

### Consumer
Thành phần nhận message từ queue. Trong Camera-Service, `ResultConsumer` là consumer.

## D

### Delivery Mode
Thuộc tính của message xác định độ bền:
- `1`: Non-persistent (mất khi RabbitMQ restart).
- `2`: Persistent (ghi vào disk, tồn tại sau restart).

### Durable
Queue hoặc exchange tồn tại sau khi RabbitMQ restart. Ngược lại với `transient`.

## E

### Exchange
Thành phần nhận message từ publisher và định tuyến đến queue dựa trên routing key và exchange type.

### Exponential Backoff
Chiến lược retry: thời gian chờ giữa các lần thử tăng theo cấp số nhân (1s → 2s → 4s → 8s...).

## F

### FrameMessage
Pydantic model chứa metadata của một khung hình: `frame_id` và `timestamp`.

### FramePublisher
Publisher chịu trách nhiệm gửi JPEG frame lên RabbitMQ.

## H

### Header (AMQP)
Metadata của message được gửi kèm trong AMQP `BasicProperties`. Camera-Service dùng headers để gửi `frame_id` và `timestamp`.

### HUD (Heads-Up Display)
Overlay hiển thị thông tin trạng thái lên khung hình camera. Gồm: Sleepy status, Seatbelt status, FPS.

## I

### Inference (Suy luận)
Quá trình AI model xử lý dữ liệu đầu vào và đưa ra kết quả. Camera-Service KHÔNG thực hiện inference.

## J

### JPEG Quality
Tham số nén JPEG (0-100). 85 là giá trị cân bằng tốt giữa chất lượng và kích thước file.

## O

### Orchestrator
Thành phần điều phối vòng đời của tất cả messaging components. `MessagingOrchestrator` quản lý start/stop các publisher và consumer.

### Overlay
Lớp thông tin được vẽ đè lên khung hình camera trước khi hiển thị.

## P

### Pika
Thư viện Python client cho RabbitMQ, implements AMQP 0-9-1.

### Publisher
Thành phần gửi message lên exchange. Trong Camera-Service, `FramePublisher` là publisher.

### Pydantic
Thư viện data validation cho Python, sử dụng type annotations.

## Q

### Queue
Hàng đợi lưu trữ message cho đến khi consumer xử lý.

## R

### Routing Key
Chuỗi định tuyến được publisher gửi kèm message. Exchange dùng routing key để quyết định queue nào nhận message.

## S

### Sliding Window
Kỹ thuật phân tích chuỗi thời gian: theo dõi N frame gần nhất để đưa ra quyết định. Driver-Service dùng sliding window cho drowsiness detection. Camera-Service KHÔNG có sliding window.

### Stop Event
`threading.Event` dùng để báo hiệu thread nên dừng. Mỗi thread dài hạn trong Camera-Service có một stop event riêng.

## T

### Thread Safety
Khả năng code chạy đúng khi nhiều thread truy cập đồng thời. Camera-Service đạt được thread safety qua `threading.Lock`.

### Topic Exchange
Loại exchange cho phép routing dựa trên pattern matching của routing key (vd: `driver.*`, `*.result`).

## V

### Virtual Host (vHost)
Phân vùng logic trong RabbitMQ, cho phép nhiều môi trường chia sẻ cùng broker.
