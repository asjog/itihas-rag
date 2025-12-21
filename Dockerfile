# Dockerfile for itihas-rag Marathi Text Search Application
FROM python:3.13-slim

# Install system dependencies including Xapian
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-xapian \
    libxapian-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p corpus indexes vectors

# Expose port
EXPOSE 8000

# Set Python path to include xapian
ENV PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH}"

# Index is pre-built and committed to git for fast startup
# To rebuild: python scripts/index_corpus.py --force

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

