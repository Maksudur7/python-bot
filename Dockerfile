# Official Playwright Python image with Chromium pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . ./

# Expose server port
EXPOSE 8000

# Run standalone HTTP server and automation bot
CMD ["python", "standalone_app.py"]
