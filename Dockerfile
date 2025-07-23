FROM python:3.11-slim

# Allow platform-aware builds
ARG TARGETARCH

# Install system packages
RUN apt-get update && apt-get install -y \
    curl \
    cron \
    unzip \
    tar \
    gzip \
    bzip2 \
    rclone \
    && rm -rf /var/lib/apt/lists/*

# Install restic (arch-specific)
RUN set -ex \
    && RESTIC_VERSION=0.16.2 \
    && case "$TARGETARCH" in \
         "arm64") ARCH="arm64";; \
         "amd64") ARCH="amd64";; \
         *) echo "Unsupported arch $TARGETARCH"; exit 1;; \
       esac \
    && curl -L "https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/restic_${RESTIC_VERSION}_linux_${ARCH}.bz2" \
        | bunzip2 > /usr/local/bin/restic \
    && chmod +x /usr/local/bin/restic

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . /app
WORKDIR /app

# Copy entrypoint script if you have one
# COPY entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

# Expose port for Flask
EXPOSE 5000

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1

# Default command: start Flask app and cron (adjust if you use entrypoint.sh)
CMD ["python", "app.py"]
