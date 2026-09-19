"""API-only ingress: authenticate the workload before buffering bounded input."""

import asyncio
import hmac
import json
import logging
import os
import time
from uuid import UUID, uuid4

import jwt
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 4 * 1024 * 1024 + 65536
logger = logging.getLogger("app.pilot.events")


class WorkloadVerifier:
    def __init__(self, tenant, audience, principal, client, key_client=None):
        self.tenant = str(UUID(tenant))
        self.audience = str(UUID(audience))
        self.principal = str(UUID(principal))
        self.client = str(UUID(client))
        self.issuer = f"https://login.microsoftonline.com/{self.tenant}/v2.0"
        self.keys = key_client or jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{self.tenant}/discovery/v2.0/keys",
            cache_keys=False, lifespan=300, timeout=3,
        )

    @classmethod
    def configured(cls):
        return cls(*(os.environ[name] for name in (
            "AI_PILOT_TENANT_ID", "GATEWAY_WORKLOAD_AUDIENCE",
            "GATEWAY_BACKEND_PRINCIPAL_ID", "GATEWAY_BACKEND_CLIENT_ID",
        )))

    def verify(self, authorization):
        if not authorization.startswith("Bearer ") or len(authorization) > 16384:
            raise ValueError("Workload authorization failed.")
        token = authorization[7:]
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError("Workload authorization failed.")
        claims = jwt.decode(
            token, self.keys.get_signing_key_from_jwt(token).key,
            algorithms=["RS256"], audience=self.audience, issuer=self.issuer,
            options={"require": ["exp", "nbf", "iat", "iss", "aud", "tid", "oid", "azp", "roles", "ver", "idtyp"],
                     "strict_aud": True},
        )
        if (claims["tid"] != self.tenant or claims["oid"] != self.principal
                or claims["azp"] != self.client or claims["ver"] != "2.0"
                or claims["idtyp"] != "app" or "scp" in claims
                or claims["roles"] != ["Gateway.Invoke"]
                or any(type(claims[field]) is not int for field in ("exp", "nbf", "iat"))):
            raise ValueError("Workload authorization failed.")


class ApiIngress:
    def __init__(self, app, verifier, active, ready):
        self.app, self.verifier, self.active, self.ready = app, verifier, active, ready
        self.log_window, self.log_count, self.log_suppressed = 0, 0, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope.get("path") == "/healthz" and scope["method"] == "GET":
            return await JSONResponse({"status": "ok"})(scope, receive, send)
        started = time.monotonic()
        request_id = str(uuid4())
        scope["headers"] = [(name, value) for name, value in scope.get("headers", [])
                            if name.lower() != b"x-request-id"] + [(b"x-request-id", request_id.encode())]
        scope["pilot_boundary"] = "route"
        response_status = None

        async def observed(message):
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        try:
            await self._dispatch(scope, receive, observed)
        except Exception:
            scope["pilot_boundary"] = "internal"
            if response_status is None:
                await self.reject(scope, receive, observed, 500)
        finally:
            window = int(time.monotonic() // 60)
            if window != self.log_window:
                if self.log_suppressed:
                    logger.warning("pilot_events_suppressed count=%d", self.log_suppressed)
                self.log_window, self.log_count, self.log_suppressed = window, 0, 0
            if self.log_count < 60:
                self.log_count += 1
                logger.info("pilot_request boundary=%s status=%d request_id=%s latency_ms=%d",
                            scope["pilot_boundary"], response_status or 499, request_id,
                            round((time.monotonic() - started) * 1000))
            else:
                self.log_suppressed += 1

    async def _dispatch(self, scope, receive, send):
        route = scope.get("path")
        if route == "/healthz" and scope["method"] == "GET":
            return await JSONResponse({"status": "ok"})(scope, receive, send)
        readiness = route == "/readyz" and scope["method"] == "GET"
        analysis = route == "/v1/food-analysis" and scope["method"] == "POST"
        if not (readiness or analysis) or scope.get("query_string"):
            return await self.reject(scope, receive, send, 404)
        headers = Headers(scope=scope)
        scope["pilot_boundary"] = "shape"
        protected = ("authorization", "x-service-token", "x-pilot-authorization", "x-operation-id", "content-length", "content-type")
        if any(len(headers.getlist(name)) > 1 for name in protected):
            return await self.reject(scope, receive, send, 400)
        try:
            length = headers.get("content-length")
            if length is not None and (not length.isascii() or not length.isdecimal()):
                raise ValueError()
            if length is not None and int(length) > MAX_BODY_BYTES:
                return await self.reject(scope, receive, send, 413)
            if analysis and headers.get("content-type", "").split(";")[0] != "application/json":
                return await self.reject(scope, receive, send, 415)
        except ValueError:
            return await self.reject(scope, receive, send, 400)
        scope["pilot_boundary"] = "workload"
        try:
            secret = os.environ.get("GATEWAY_SERVICE_TOKEN", "")
            if not secret or not hmac.compare_digest(secret, headers.get("x-service-token", "")):
                raise ValueError()
            await asyncio.to_thread(self.verifier.verify, headers.get("authorization", ""))
        except Exception:
            return await self.reject(scope, receive, send, 403)
        scope["api_only_workload_verified"] = True
        body = bytearray()
        if analysis:
            scope["pilot_boundary"] = "body"
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] != "http.request":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > MAX_BODY_BYTES:
                            return await self.reject(scope, receive, send, 413)
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await self.reject(scope, receive, send, 408)
            if length is not None and len(body) != int(length):
                return await self.reject(scope, receive, send, 400)
            try:
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValueError()
            except (ValueError, UnicodeError, RecursionError):
                return await self.reject(scope, receive, send, 400)
            scope["pilot_boundary"] = "assertion"
            try:
                from app.pilot_access import configured_allowlist, verify

                identity = verify(headers, payload)
                if identity is None or identity[0] not in configured_allowlist():
                    raise ValueError()
            except Exception:
                return await self.reject(scope, receive, send, 403)
        scope["pilot_boundary"] = "release"
        try:
            self.active()
        except Exception:
            return await self.reject(scope, receive, send, 503)
        if readiness:
            scope["pilot_boundary"] = "ledger"
            try:
                await self.ready()
            except Exception:
                return await self.reject(scope, receive, send, 503)
            return await JSONResponse({"status": "ready"})(scope, receive, send)
        supplied = False

        async def buffered():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        scope["pilot_boundary"] = "domain"
        await self.app(scope, buffered, send)

    @staticmethod
    async def reject(scope, receive, send, status):
        code = "pilot_unavailable" if status == 503 else "pilot_input" if status == 413 else "pilot_forbidden"
        await JSONResponse({"error": {"code": code, "message": "Request not admitted."}}, status_code=status)(scope, receive, send)