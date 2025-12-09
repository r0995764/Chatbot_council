# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
# We install gunicorn explicitly for the production server
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn

# Expose the port (Google Cloud Run expects port 8080 by default)
ENV PORT=8080

# Command to run the app using Gunicorn
# "app:app" means: look in file 'app.py' for the object named 'app'
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app

