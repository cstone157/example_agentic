# Application Image for Trivy Scanning
# This Dockerfile builds the application container that will be scanned by Trivy

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and agent configurations
COPY src/ ./src/
COPY agents/ ./agents/

# Expose port (adjust based on your application)
EXPOSE 8000

# Default command — run the workflow graph
CMD ["python", "-m", "src.workflow.graph"]
