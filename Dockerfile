# Use the official Python image from Docker Hub
FROM python:3.11.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=backend.settings

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    libmagic1 \
    libglib2.0-0 \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure Git (if necessary)
RUN git config --global user.email "han@askhomer.ai" \
    && git config --global user.name "SuperDryHann"

# Copy the requirements file and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# (Optional) Run collectstatic
# RUN python manage.py collectstatic --noinput

# (Optional) Apply database migrations
# RUN python manage.py migrate

# Expose port 8000 for the application
EXPOSE 8000

# Define the default command to run the app with Uvicorn
CMD ["uvicorn", "backend.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
