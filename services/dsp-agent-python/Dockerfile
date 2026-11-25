# syntax=docker/dockerfile:1

# Install native extensions in the target image. The service is deployed only
# as linux/arm64, so NumPy/SciPy wheels match the runtime architecture.
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "src.main"]
