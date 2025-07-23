FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    cron \
    unzip \
    tar \
    gzip \
    bzip2 \
    && rm -rf /var/lib/apt/lists/*

# Install restic
RUN curl -L https://github.com/restic/restic/releases/download/v0.16.2/restic_0.16.2_linux_amd64.bz2 \
    | bunzip2 > /usr/local/bin/restic && \
    chmod +x /usr/local/bin/restic

# Install rclone
RUN curl -L https://downloads.rclone.org/rclone-current-linux-amd64.zip -o rclone.zip && \
    unzip rclone.zip && \
    cp rclone-*/rclone /usr/local/bin/ && \
    chmod +x /usr/local/bin/rclone && \
    rm -rf rclone*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p /data /volumes

# Create cron job for automated backups
RUN echo "0 2 * * * cd /app && /usr/local/bin/python /app/cron_backup.py >> /data/cron.log 2>&1" > /etc/cron.d/backup-cron && \
    chmod 0644 /etc/cron.d/backup-cron && \
    crontab /etc/cron.d/backup-cron

# Create startup script
RUN echo '#!/bin/bash\n\
# Start cron daemon\n\
cron\n\
\n\
# Start Flask application\n\
exec python app.py' > /app/start.sh && \
    chmod +x /app/start.sh

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Start application
CMD ["/app/start.sh"]
