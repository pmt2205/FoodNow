FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    default-mysql-client \
    git \
    openssh-client \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash appuser
USER appuser

WORKDIR /home/appuser/app

RUN mkdir -p ~/.ssh && \
    ssh-keyscan github.com >> ~/.ssh/known_hosts && \
    chmod 600 ~/.ssh/known_hosts

COPY --chown=appuser:appuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

EXPOSE 80

CMD ["python", "index.py"]
