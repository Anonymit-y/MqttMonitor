# Use an official lightweight Python runtime
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy and install dependencies first (leverages Docker caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY main.py /app/
# Note: sensor_profiles.json is mounted via docker-compose for real-time edits, 
# but copying a default version ensures it runs out of the box.
COPY sensor_profiles.json /app/

# Run the application
CMD ["python", "main.py"]
