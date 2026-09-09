# QShield — container image for the API and dashboard.
# Build:  docker build -t qshield .
# Run:    docker run -p 8000:8000 qshield      then open http://localhost:8000/

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    QSHIELD_POLICY=/data/policy.yaml

WORKDIR /app
COPY . .

# Editable install keeps app.config's path resolution (frontend/, mock_estate/,
# policy.yaml) anchored at /app. The qiskit extra powers the Quantum Lab tab
# (Shor/Grover as real Aer circuits); without it that tab falls back to a hint
# and everything else still runs on the bundled pure-Python simulator.
RUN pip install -e ./backend[api] -r requirements-qiskit.txt

# policy.yaml is rewritten by the hot-swap / migration demo endpoints, so it is
# kept on a writable volume; the app seeds it from the bundled copy on startup.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data \
 && chown -R app:app /app /data
USER app

EXPOSE 8000
CMD ["python", "-m", "app.api"]
