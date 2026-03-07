FROM python:3.11-slim

WORKDIR /app

# Install system tools the agent might need
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy OpenEnv core
COPY src/ /app/src/

# Copy apex_env
COPY envs/apex_env/ /app/envs/apex_env/

# Install dependencies
RUN pip install --no-cache-dir \
    "openenv-core[core]>=0.2.1" \
    "fastapi>=0.115.0" \
    "pydantic>=2.0.0" \
    "uvicorn[standard]>=0.24.0" \
    "datasets>=2.14.0"

# Install OpenEnv core from source
RUN pip install --no-cache-dir -e /app/src/

# Install apex_env from source
RUN pip install --no-cache-dir -e /app/envs/apex_env/

EXPOSE 8000

ENV PYTHONPATH=/app/src:/app/envs

CMD ["uvicorn", "apex_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
