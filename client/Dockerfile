# Use a Python 3 base image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy the requirements.txt file and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the client script and any required files
COPY client_tests.py .
COPY config.txt /app/config.txt

# Define the environment variables and their defaults
ENV SERVER_IP=127.0.0.1
ENV TARGET_CPS=100
ENV HTTPS_PERCENT=50
ENV AVG_OBJECT_SIZE_MB=5
ENV DURATION=60
ENV CONFIG_PATH=/app/config.txt

# Run the client script
CMD ["python", "client_tests.py"]