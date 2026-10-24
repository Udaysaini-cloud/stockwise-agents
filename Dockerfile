# Use official lightweight Python 3.12 image
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and data
COPY core/ ./core/
COPY data/ ./data/
COPY agents/ ./agents/

# Create directory for persistent SQLite database
RUN mkdir -p /app/data

# Default port for coordinator HTTP endpoint
EXPOSE 8001

# Run the coordinator agent
CMD ["python", "agents/coordinator.py"]
