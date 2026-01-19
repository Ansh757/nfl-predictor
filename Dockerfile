# Stage 1: Build React Frontend
FROM node:18 AS frontend-build
WORKDIR /frontend
COPY demo/package*.json ./
RUN npm install
COPY demo/ ./
RUN npm run build

# Stage 2: Python Backend + Serve Frontend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY agent-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python backend
COPY agent-service/ .

# Copy React build from Stage 1
COPY --from=frontend-build /frontend/build ./demo/build

# Expose port
EXPOSE 8001

# Run
CMD ["python", "main.py"]