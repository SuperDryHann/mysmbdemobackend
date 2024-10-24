# Use the official Python image from Docker Hub
FROM python:3.11.9-slim

# Set environment variables to optimize Python behavior
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=backend.settings

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by Chromium and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Basic utilities
    git \
    libmagic1 \
    libglib2.0-0 \
    libgl1-mesa-glx \
    # Dependencies for Chromium
    libatk-bridge2.0-0 \
    libnspr4 \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libatk1.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    ca-certificates \
    fonts-liberation \
    libfontconfig1 \
    # Cleanup to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure Git (if necessary)
RUN git config --global user.email "han@askhomer.ai" \
    && git config --global user.name "SuperDryHann"

# Copy the requirements file first for better caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its browsers
RUN playwright install --with-deps

# Copy the rest of the application code
COPY . /app/

# (Optional) Run collectstatic if you're using Django
# RUN python manage.py collectstatic --noinput

# (Optional) Apply database migrations
# RUN python manage.py migrate

# Expose port 8000 for the application
EXPOSE 8000

# Define the default command to run the app with Uvicorn
CMD ["uvicorn", "backend.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
