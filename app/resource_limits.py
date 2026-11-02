"""Cotas e reservas atômicas no MongoDB, compartilhadas por todos os workers."""
import asyncio
import math
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import HTTPException
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from app.config import MONGODB_URI
from app.limits import (
    GLOBAL_CONCURRENCY, GLOBAL_PER_DAY, LEASE_SECONDS, OPERATION_SECONDS,
    USER_PER_DAY, USER_PER_MINUTE,
)


@lru_cache(maxsize=1)
def _colecao():
    if not MONGODB_URI:
        raise RuntimeError("MongoDB não configurado.")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000,
                         connectTimeoutMS=5000, socketTimeoutMS=5000)
    try:
        collection = client["olivia-olius"]["limites_api"]
        collection.create_index("expires_at", expireAfterSeconds=0)
        return collection
    except Exception:
        client.close()
        raise


def _cota(collection, key, maximum, seconds, now):
    bucket = math.floor(now.timestamp() / seconds)
    try:
        result = collection.update_one(
            {"_id": f"quota:{key}:{seconds}:{bucket}", "count": {"$lt": maximum}},
            {"$inc": {"count": 1}, "$setOnInsert": {
                "expires_at": datetime.fromtimestamp((bucket + 1) * seconds, timezone.utc) + timedelta(days=1),
            }}, upsert=True,
        )
        if not (result.modified_count or result.upserted_id):
            raise HTTPException(429, "Cota de uso atingida.", headers={"Retry-After": str(seconds)})
    except DuplicateKeyError:
        raise HTTPException(429, "Cota de uso atingida.", headers={"Retry-After": str(seconds)}) from None


def _reservar(collection, key, owner, now):
    try:
        result = collection.update_one(
            {"_id": key, "expires_at": {"$lte": now}},
            {"$set": {"owner": owner, "expires_at": now + timedelta(seconds=LEASE_SECONDS)}},
            upsert=True,
        )
        return bool(result.modified_count or result.upserted_id)
    except DuplicateKeyError:
        return False


def _adquirir(user_id, owner):
    collection = _colecao()
    now = datetime.now(timezone.utc)
    for key, maximum, seconds in ((user_id, USER_PER_MINUTE, 60), (user_id, USER_PER_DAY, 86400),
                                  ("global", GLOBAL_PER_DAY, 86400)):
        _cota(collection, key, maximum, seconds, now)
    user_key = f"busy:{user_id}"
    if not _reservar(collection, user_key, owner, now):
        raise HTTPException(429, "Já existe uma operação em andamento para este usuário.", headers={"Retry-After": "5"})
    try:
        for index in range(GLOBAL_CONCURRENCY):
            if _reservar(collection, f"slot:{index}", owner, now):
                return
        raise HTTPException(429, "Serviço ocupado. Tente novamente em instantes.", headers={"Retry-After": "5"})
    except BaseException:
        collection.delete_many({"owner": owner})
        raise


@asynccontextmanager
async def operacao(user_id):
    owner = uuid.uuid4().hex
    try:
        async with asyncio.timeout(10):
            await asyncio.to_thread(_adquirir, user_id, owner)
    except (RuntimeError, PyMongoError, TimeoutError):
        raise HTTPException(503, "Controle de uso indisponível.") from None
    try:
        async with asyncio.timeout(OPERATION_SECONDS):
            yield
    except TimeoutError:
        # Não liberar antecipadamente: chamadas síncronas canceladas podem terminar
        # em segundo plano. A reserva expira depois dos timeouts dos provedores.
        raise HTTPException(504, "Tempo máximo da operação excedido.") from None
    except asyncio.CancelledError:
        raise
    except BaseException:
        await asyncio.to_thread(_colecao().delete_many, {"owner": owner})
        raise
    else:
        await asyncio.to_thread(_colecao().delete_many, {"owner": owner})
