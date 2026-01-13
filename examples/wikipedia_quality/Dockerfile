FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    redis \
    requests \
    ollama \
    python-dotenv

# Copy DonkeyKong package
COPY core/ /app/donkeykong/core/
COPY kong/ /app/donkeykong/kong/
COPY interfaces/ /app/donkeykong/interfaces/
COPY __init__.py /app/donkeykong/

# Copy example files
COPY examples/wikipedia_quality/worker.py /app/
COPY examples/wikipedia_quality/articles.txt /app/

# Create necessary directories
RUN mkdir -p /data /logs /backups /reports

# Default command
CMD ["python", "worker.py"]
