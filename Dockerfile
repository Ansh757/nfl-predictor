# Stage 1: Build React Frontend
FROM node:18 AS frontend-build
WORKDIR /frontend
COPY demo/package*.json ./
RUN npm install
COPY demo/ ./

# Create React App inlines REACT_APP_* at build time, so this has to be a build
# arg - setting it as a runtime variable does nothing, the bundle is already
# compiled. Leave it unset to keep calling the Python service directly; set it
# to the gateway's public URL to route the dashboard through Spring Boot.
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL

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

# Drop root. A container process that does not need to write outside its own
# working directory has no reason to be uid 0, and root is what turns a
# file-write bug into a container compromise. Ownership is handed over first so
# the SQLite database stays writable - the schedule loader runs DDL on import.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

# Run
CMD ["python", "main.py"]