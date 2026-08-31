FROM python:3.11-slim

WORKDIR /app

# System libs empymod/scipy may dlopen at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tools ./tools
COPY sandbox_service ./sandbox_service

# Default command runs the agent backend. The sandbox service overrides this in
# docker-compose with:  uvicorn sandbox_service.main:app --port 8001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
