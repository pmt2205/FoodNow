FROM python:3.11-slim

# Đặt biến môi trường để không bị hỏi khi apt install
ENV DEBIAN_FRONTEND=noninteractive

# Cài mysql client, git, openssh trước khi chuyển sang user không phải root
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    git \
    openssh-client \
 && rm -rf /var/lib/apt/lists/*  # Dọn dẹp để giảm dung lượng image

# Tạo user không phải root
RUN useradd --create-home --shell /bin/bash appuser

# Chuyển sang user appuser
USER appuser

# Thêm github vào known_hosts để tránh lỗi khi clone SSH
RUN mkdir -p /home/appuser/.ssh && \
    ssh-keyscan github.com >> /home/appuser/.ssh/known_hosts && \
    chmod 600 /home/appuser/.ssh/known_hosts

# Thiết lập thư mục làm việc
WORKDIR /home/appuser/app

# Copy requirements và cài đặt thư viện Python
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn
COPY --chown=appuser:appuser . .

# Mở port 5000
EXPOSE 80

# Chạy ứng dụng
CMD ["sh", "-c", "sleep 15 && python run.py"]