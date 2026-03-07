FROM python:3.11-slim

WORKDIR /app

# System tools agents might use during episodes
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget jq git poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy environment code
COPY apex_env/ /app/apex_env/

# Copy the server entry point
COPY app.py /app/app.py

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
