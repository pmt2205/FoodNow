FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    default-mysql-client \
    git \
    openssh-client \
 && rm -rf /var/lib/apt/lists/*

# Tạo user không phải root
RUN useradd --create-home --shell /bin/bash appuser

USER appuser

WORKDIR /home/appuser/app

RUN mkdir -p /home/appuser/.ssh && \
    ssh-keyscan github.com >> /home/appuser/.ssh/known_hosts && \
    chmod 600 /home/appuser/.ssh/known_hosts

# Copy requirements và cài thư viện
COPY --chown=appuser:appuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn
COPY --chown=appuser:appuser . .

# Mở port 80 cho Flask
EXPOSE 80

# Sửa CMD để trỏ đúng file chạy
CMD ["sh", "-c", "sleep 15 && python Foodnow/index.py"]
