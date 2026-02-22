FROM python:3.11-slim

# Install system dependencies (OCR + PDF tools)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    ghostscript \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node (for React build)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Build React frontend
WORKDIR /app/frontend
RUN npm install && npm run build

# Return to root
WORKDIR /app

# Start FastAPI
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "10000"]