# Personal AI Gateway - container image for Azure Container Apps.
#
# Runtime requirements this depends on (see README.md / AGENTS.md for the
# full deployment rationale):
# - Python 3.13 (matches the version this codebase is developed/tested against).
# - The official github-copilot-sdk, which bundles/downloads the Copilot CLI
#   runtime via `python -m copilot download-runtime`. That step needs network
#   access and is run here at *build* time so the running container never
#   needs to fetch it itself.
# - Authentication: MUST use COPILOT_GITHUB_TOKEN (a non-interactive,
#   server-to-server GitHub token with the "Copilot Requests" permission),
#   injected at runtime as an Azure Container Apps secret/environment
#   variable - never baked into this image. The interactive `copilot`/
#   `/login` device-code flow used for local development cannot run in a
#   headless container and is not used here.
# - Writable filesystem: the Copilot CLI keeps its own runtime state/logs
#   under $HOME (here /home/gateway); Container Apps' default ephemeral,
#   writable container filesystem is sufficient - no persistent volume is
#   required, since COPILOT_GITHUB_TOKEN-based auth needs no persisted
#   session across restarts.
# - Memory: image-analysis requests decode/hold a base64 payload up to
#   MAX_IMAGE_BYTES (a few MiB) plus normal Pillow/model-call overhead;
#   budget at least 512Mi, and more headroom if AI_PROVIDER_MAX_CONCURRENCY
#   is raised above its default of 2 (each concurrent image request holds
#   its own decoded buffer).

FROM python:3.13-slim

RUN useradd --create-home --uid 1000 gateway
WORKDIR /app
ENV HOME=/home/gateway

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-fetches the Copilot CLI runtime into the image at build time, so the
# running container has no first-request download/network dependency for it.
RUN python -m copilot download-runtime

COPY app ./app

RUN chown -R gateway:gateway /app /home/gateway
USER gateway

EXPOSE 8000

# APP_ENV, AI_PROVIDER, COPILOT_MODEL_ROUTES_JSON, GATEWAY_SERVICE_TOKEN, and
# COPILOT_GITHUB_TOKEN must all be supplied at deploy time (Container Apps
# environment variables/secrets) - none have safe baked-in defaults; the
# app fails closed at startup if any required one is missing.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
