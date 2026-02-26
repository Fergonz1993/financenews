FROM python:3.12-slim AS backend

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 for Next.js frontend
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (cached layer)
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir -r requirements.txt

# Node dependencies (cached layer)
COPY package.json ./
RUN npm install --production=false

# Copy project files
COPY . .

# Build Next.js frontend
RUN npm run build

# Non-root user for security
RUN useradd -m appuser
USER appuser

# Environment
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

EXPOSE 8000 3000

# Start both FastAPI and Next.js
CMD ["python", "run_server.py"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
