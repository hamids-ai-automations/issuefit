# syntax=docker/dockerfile:1
FROM python:3.12-slim

LABEL org.opencontainers.image.title="issuefit" \
      org.opencontainers.image.description="Score GitHub issues for contribution fit" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 issuefit
USER issuefit

# ENTRYPOINT keeps the binary fixed so `docker run image scan --query ...` passes args through.
ENTRYPOINT ["issuefit"]
CMD ["demo"]
