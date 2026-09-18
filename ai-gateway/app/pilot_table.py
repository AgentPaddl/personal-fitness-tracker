"""Azure Table CAS transactions. No provisioning or request-time ledger reset."""

import asyncio
import json
import logging
import os
import re
from urllib.parse import urlsplit

from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.data.tables import UpdateMode
from azure.data.tables.aio import TableClient
from azure.identity.aio import ManagedIdentityCredential

from app.pilot import Conflict, PilotError, canonical


_sdk_logger = logging.Logger(__name__ + ".sdk")
_sdk_logger.disabled = True
_sdk_logger.propagate = False


class AzureTableStore:
    def __init__(self, client, partition="pilot-v1"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", partition):
            raise PilotError()
        self.client, self.partition = client, partition

    @classmethod
    def connect(cls, endpoint, table_name):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9]+\.table\.core\.windows\.net", parsed.netloc)
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,62}", table_name)):
            raise PilotError()
        client_id = os.environ.get("AI_PILOT_GATEWAY_CLIENT_ID")
        credential = ManagedIdentityCredential(**({"client_id": client_id} if client_id else {}))
        client = TableClient(endpoint, table_name, credential=credential, retry_total=0,
                             logging_enable=False, logger=_sdk_logger, tracing_enable=False,
                             connection_timeout=2, read_timeout=3)
        store = cls(client)
        store.credential = credential
        return store

    async def close(self):
        async with asyncio.timeout(2):
            await self.client.close()
            if hasattr(self, "credential"):
                await self.credential.close()

    async def read(self, key):
        try:
            async with asyncio.timeout(5):
                entity = await self.client.get_entity(self.partition, key, logging_enable=False)
            return json.loads(entity["data"]), entity.metadata["etag"]
        except ResourceNotFoundError:
            return None, None
        except Exception:
            raise PilotError() from None

    async def commit(self, changes):
        operations = []
        for key, data, etag in changes:
            serialized = canonical(data).decode()
            if len(serialized.encode("utf-16-le")) > 60000:
                raise PilotError()
            entity = {"PartitionKey": self.partition, "RowKey": key, "data": serialized}
            if etag is None:
                operations.append(("create", entity))
            else:
                operations.append(("update", entity, {"mode": UpdateMode.REPLACE, "etag": etag,
                                                       "match_condition": MatchConditions.IfNotModified}))
        try:
            async with asyncio.timeout(5):
                await self.client.submit_transaction(operations, logging_enable=False)
        except HttpResponseError as exc:
            if exc.status_code in {409, 412}:
                raise Conflict() from None
            raise PilotError() from None
        except Exception:
            raise PilotError() from None

    async def cleanup(self, now, retention_seconds):
        ledger, ledger_etag = await self.read("ledger")
        if ledger is None or now < ledger["last_time"]:
            raise PilotError()
        ledger["last_time"] = now
        ledger["buckets"] = {key: value for key, value in ledger["buckets"].items()
                             if value["created"] >= now - retention_seconds}
        await self.commit([("ledger", ledger, ledger_etag)])
        removed = 0
        try:
            async with asyncio.timeout(15):
                entities = self.client.query_entities(
                    "PartitionKey eq @partition and RowKey ge 'op-' and RowKey lt 'op.'",
                    parameters={"partition": self.partition}, logging_enable=False)
                async for entity in entities:
                    record = json.loads(entity["data"])
                    if record["expires"] >= now:
                        continue
                    if record["state"] in {"pending", "unknown"}:
                        current, current_etag = await self.read("ledger")
                        if current is None:
                            raise PilotError()
                        current["blocked"] = True
                        current["active"].pop(entity["RowKey"], None)
                        await self.commit([("ledger", current, current_etag)])
                    await self.client.delete_entity(self.partition, entity["RowKey"],
                                                    etag=entity.metadata["etag"],
                                                    match_condition=MatchConditions.IfNotModified,
                                                    logging_enable=False)
                    removed += 1
                    if removed >= 50:
                        break
        except Exception:
            raise PilotError() from None
        return removed