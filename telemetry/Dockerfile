# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy your Python files
COPY site24x7-reporter.py ./
COPY .env ./

# Install dependencies
RUN pip install aiohttp python-dotenv

# Run the script
CMD ["python", "site24x7-reporter.py"]
