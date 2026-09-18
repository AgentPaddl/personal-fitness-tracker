"""Explicit user-assigned managed identity; no CLI or default-credential fallback."""

from functools import lru_cache
import logging
import os
import time
from uuid import UUID


def validate_workload_config():
    if (os.environ.get("APP_ENV") != "production" or os.environ.get("AI_PILOT_ENABLED") != "true"
            or os.environ.get("EASY_AUTH_ENABLED") != "true"):
        raise ValueError("Pilot workload configuration is incomplete.")
    for name in ("GATEWAY_BACKEND_CLIENT_ID", "GATEWAY_WORKLOAD_AUDIENCE", "AI_PILOT_TENANT_ID"):
        if str(UUID(os.environ[name])) != os.environ[name]:
            raise ValueError("Pilot workload configuration is incomplete.")


@lru_cache
def _credential(client_id):
    from azure.identity import ManagedIdentityCredential

    logger = logging.Logger(__name__ + ".sdk")
    logger.disabled = True
    logger.propagate = False
    return ManagedIdentityCredential(client_id=client_id, logging_enable=False, logger=logger,
                                     retry_total=0, connection_timeout=2, read_timeout=3)


def gateway_access_token():
    validate_workload_config()
    token = _credential(os.environ["GATEWAY_BACKEND_CLIENT_ID"]).get_token(
        f"api://{os.environ['GATEWAY_WORKLOAD_AUDIENCE']}/.default")
    if not token.token or token.expires_on <= time.time() + 30:
        raise ValueError("Workload token unavailable.")
    return token.token