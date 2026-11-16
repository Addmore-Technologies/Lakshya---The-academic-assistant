FROM python:3.12-slim

WORKDIR /app

# OCR for JPG syllabus images and conversion for legacy PowerPoint files
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

# Install requirements first for layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend package
COPY backend/ .

# Copy the ai package (Token Factory client, quiz generation)
COPY ai/ ai/

# Run with a single worker — the login rate limiter is in-memory
# and would not be consistent across multiple workers.
EXPOSE 8000
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
