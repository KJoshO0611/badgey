# Docker Deployment Guide

This guide covers the Docker deployment and configuration for Badgey Quiz Bot.

## Docker Overview

Badgey Quiz Bot is containerized using Docker to provide:

1. **Consistent Environment**: Same environment across development and production
2. **Isolation**: Bot runs in its own container without conflicting with other applications
3. **Resource Constraints**: Easy to limit CPU and memory usage
4. **Portability**: Deploy anywhere that supports Docker

## Dockerfile Explained

The `Dockerfile` uses a multi-stage build process to create a slim, secure runtime image:

```dockerfile
# Use the official Python image as the base image
FROM python:3.11-slim AS builder

# Set the working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install build dependencies and Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Runtime image
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r badgey && \
    useradd -r -g badgey -d /home/badgey -s /sbin/nologin -c "Badgey Bot User" badgey && \
    mkdir -p /home/badgey && \
    chown -R badgey:badgey /home/badgey

# Set the working directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Create log directory with correct permissions
RUN mkdir -p /app/logs && \
    chown -R badgey:badgey /app

# Switch to non-root user
USER badgey

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the bot
CMD ["python", "main.py"]
```

### Key Aspects:

1. **Multi-Stage Build**:
   - First stage installs build dependencies and Python packages
   - Second stage creates a clean runtime image

2. **Security Features**:
   - Uses a non-root user (`badgey`)
   - Minimizes installed packages
   - Runs with least privilege

3. **Health Check**:
   - Configured to check the bot's health endpoint
   - Allows Docker to detect and restart unhealthy containers

## Building the Image

To build the Docker image:

```bash
docker build -t badgey-bot:latest .
```

For production releases, include a version tag:

```bash
docker build -t badgey-bot:1.0.0 -t badgey-bot:latest .
```

## Environment Configuration

The bot requires environment variables for configuration. Create a `.env` file with:

```
TOKEN=your_discord_bot_token
GUILDID=your_guild_id_1,your_guild_id_2
PREFIX=-
DBHOST=db_host
DBPORT=3306
DBUSER=badgey_user
DBPASSWORD=secure_password
DBNAME=badgey
```

## Running the Container

### Basic Run

```bash
docker run -d --name badgey --env-file .env badgey-bot
```

### With Resource Limits

```bash
docker run -d --name badgey \
  --env-file .env \
  --memory=512m \
  --cpus=0.5 \
  badgey-bot
```

### With Volume for Logs

```bash
docker run -d --name badgey \
  --env-file .env \
  -v badgey_logs:/app/logs \
  badgey-bot
```

### With Health Check Port Exposed

```bash
docker run -d --name badgey \
  --env-file .env \
  -p 8080:8080 \
  badgey-bot
```

## Docker Compose

For a complete deployment including database, use Docker Compose:

```yaml
version: '3.8'

services:
  bot:
    image: badgey-bot:latest
    container_name: badgey-bot
    restart: unless-stopped
    env_file: .env
    depends_on:
      - db
    ports:
      - "8080:8080"
    volumes:
      - badgey_logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
  
  db:
    image: mysql:8.0
    container_name: badgey-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DBNAME}
      MYSQL_USER: ${DBUSER}
      MYSQL_PASSWORD: ${DBPASSWORD}
    volumes:
      - badgey_db:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  badgey_logs:
  badgey_db:
```

Save this as `docker-compose.yml` and run:

```bash
docker-compose up -d
```

## Monitoring and Management

### Checking Container Status

```bash
docker ps -a
```

### Viewing Logs

```bash
docker logs badgey
```

For continuous log monitoring:

```bash
docker logs -f badgey
```

### Checking Container Health

```bash
docker inspect --format='{{.State.Health.Status}}' badgey
```

### Manual Health Check

```bash
curl http://localhost:8080/health
```

### Restarting the Container

```bash
docker restart badgey
```

## Updating the Bot

1. Pull the latest code changes
2. Build a new Docker image
3. Stop the current container
4. Start a new container with the updated image

```bash
git pull
docker build -t badgey-bot:latest .
docker stop badgey
docker rm badgey
docker run -d --name badgey --env-file .env badgey-bot
```

## Production Deployment Considerations

### Security

1. **Network Security**:
   - Don't expose the health check endpoint publicly
   - Use a reverse proxy with TLS for public access

2. **Secret Management**:
   - Use Docker secrets or a secure vault for sensitive data
   - Don't store secrets in the Docker image

3. **Regular Updates**:
   - Keep the base image updated for security patches
   - Implement CI/CD for automated security scanning

### Performance

1. **Resource Allocation**:
   - Monitor CPU and memory usage to optimize limits
   - Adjust container resources based on actual usage

2. **Database Connection**:
   - Ensure the database connection is properly configured
   - Monitor connection pool usage

### High Availability

1. **Container Orchestration**:
   - Consider Kubernetes or Docker Swarm for high availability
   - Implement proper liveness and readiness probes

2. **Backup Strategy**:
   - Regularly backup the database volume
   - Document and test restore procedures

## Troubleshooting

### Container Won't Start

1. Check environment variables:
   ```bash
   docker run --env-file .env badgey-bot env
   ```

2. Check logs for errors:
   ```bash
   docker logs badgey
   ```

### Database Connection Issues

1. Verify database credentials in the `.env` file
2. Check if the database container is running
3. Test database connectivity:
   ```bash
   docker exec -it badgey python -c "import aiomysql; print('DB module loaded')"
   ```

### Health Check Failures

1. Check if the health server is running:
   ```bash
   docker exec -it badgey curl http://localhost:8080/health
   ```

2. Inspect health check logs:
   ```bash
   docker logs badgey | grep health
   ``` 