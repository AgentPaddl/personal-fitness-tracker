"""Dedicated API-only entry point; legacy images keep app.main unchanged."""

import logging

from app.config import get_settings
from app.main import create_app
from app.pilot_release import validate_release, verify_ledger
from app.workload_auth import ApiIngress, WorkloadVerifier


def create_api_app():
    logger = logging.getLogger("app.pilot.events")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    class ConfiguredVerifier:
        def verify(self, token):
            return verifier().verify(token)

    from functools import lru_cache

    @lru_cache
    def verifier():
        return WorkloadVerifier.configured()

    def active():
        validate_release(get_settings())

    return ApiIngress(create_app(), ConfiguredVerifier(), active, verify_ledger)


app = create_api_app()