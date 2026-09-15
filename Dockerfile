FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml requirements.txt requirements-production.txt ./
COPY src ./src
RUN python -m pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src \
    DOCPILOT_MODE=demo \
    DOCPILOT_VECTOR_BACKEND=memory \
    DOCPILOT_AI_BACKEND=deterministic
EXPOSE 8000
CMD ["uvicorn", "docpilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
