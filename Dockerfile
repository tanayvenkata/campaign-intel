# Lightweight production image - no heavy ML dependencies
FROM python:3.11-slim

WORKDIR /app

# Install only production dependencies (no torch, no sentence-transformers)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY eval/ ./eval/
COPY data/ ./data/
COPY prompts/ ./prompts/
COPY political-consulting-corpus/ ./political-consulting-corpus/

# Expose port
EXPOSE 8000

# Railway sets PORT env var
ENV PORT=8000

# Start server (Railway will override PORT)
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
