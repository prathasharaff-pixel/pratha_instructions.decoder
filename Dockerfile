FROM python:3.12-slim

# Install Node.js (needed for npx, which runs the MCP filesystem server)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets $PORT dynamically, so we use shell form to expand it
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port $PORT"]
