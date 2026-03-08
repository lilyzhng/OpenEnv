FROM python:3.11-slim

# Standard tools for professional analysis tasks
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq curl wget grep sed gawk poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Python packages for data analysis
RUN pip install --no-cache-dir \
    pandas openpyxl pdfplumber tabulate xlrd

# Non-root user for safety
RUN useradd -m -s /bin/bash agent
USER agent
WORKDIR /home/agent/workspace
