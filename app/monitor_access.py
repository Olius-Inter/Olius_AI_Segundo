"""Acesso interno ao monitor por senha e sessão própria."""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from getpass import getpass

from fastapi import HTTPException, Request
from pymongo import timeout
from pymongo.errors import PyMongoError

from app.resource_limits import _colecao, _cota

COOKIE_MONITOR = "__Host-olius-monitor"
VALIDADE_SESSAO = 30 * 60
_ITERACOES = 600_000
_VERIFICADOR = re.compile(r"[0-9a-f]{32}:[0-9a-f]{64}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_LOCAIS = {"localhost", "127.0.0.1", "::1"}


def _derivar(senha: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, _ITERACOES).hex()


def gerar_verificador(senha: str) -> str:
    if len(senha) != 20:
        raise ValueError("A senha precisa ter 20 caracteres.")
    salt = secrets.token_bytes(16)
    return f"{salt.hex()}:{_derivar(senha, salt)}"


def validar_origem(request: Request) -> None:
    origem = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") not in (None, "none", "same-origin"):
        raise HTTPException(403, "Acesse o monitor pelo endereço da aplicação.")
    if origem is not None and origem != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Acesse o monitor pelo endereço da aplicação.")
    if request.url.scheme != "https":
        if request.url.hostname not in _LOCAIS or not request.client or request.client.host not in _LOCAIS:
            raise HTTPException(403, "Use HTTPS para acessar o monitor.")


def _id_sessao(token: str | None) -> str | None:
    if token and _TOKEN.fullmatch(token):
        return "monitor:session:" + hashlib.sha256(token.encode("ascii")).hexdigest()
    return None


def _versao_senha(verificador: str) -> str:
    return hashlib.sha256(verificador.encode("ascii")).hexdigest()


def abrir_sessao_monitor(senha: object, endereco: str) -> str:
    verificador = os.getenv("MONITOR_PASSWORD_HASH", "")
    if not _VERIFICADOR.fullmatch(verificador):
        raise HTTPException(503, "O acesso ao monitor ainda não foi configurado.")

    agora = datetime.now(timezone.utc)
    try:
        with timeout(5):
            colecao = _colecao()
            _cota(colecao, f"monitor:ip:{endereco}", 6, 60, agora)
            _cota(colecao, "monitor:global", 30, 60, agora)
        salt, esperado = verificador.split(":")
        if not isinstance(senha, str) or len(senha) != 20:
            raise HTTPException(401, "Senha incorreta.")
        try:
            recebido = _derivar(senha, bytes.fromhex(salt))
        except UnicodeEncodeError:
            raise HTTPException(401, "Senha incorreta.") from None
        if not hmac.compare_digest(recebido, esperado):
            raise HTTPException(401, "Senha incorreta.")

        token = secrets.token_urlsafe(32)
        with timeout(5):
            colecao.insert_one({
                "_id": _id_sessao(token),
                "versao_senha": _versao_senha(verificador),
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=VALIDADE_SESSAO),
            })
        return token
    except (PyMongoError, RuntimeError):
        raise HTTPException(503, "Acesso ao monitor temporariamente indisponível.") from None


def tem_sessao_monitor(request: Request) -> bool:
    sessao = _id_sessao(request.cookies.get(COOKIE_MONITOR))
    verificador = os.getenv("MONITOR_PASSWORD_HASH", "")
    if sessao is None or not _VERIFICADOR.fullmatch(verificador):
        return False
    try:
        with timeout(5):
            return _colecao().find_one({
                "_id": sessao,
                "versao_senha": _versao_senha(verificador),
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }, {"_id": 1}) is not None
    except (PyMongoError, RuntimeError):
        raise HTTPException(503, "Acesso ao monitor temporariamente indisponível.") from None


def exigir_sessao_monitor(request: Request) -> None:
    if not tem_sessao_monitor(request):
        raise HTTPException(401, "Entre com a senha da equipe para acessar o monitor.")


def encerrar_sessao_monitor(request: Request) -> None:
    sessao = _id_sessao(request.cookies.get(COOKIE_MONITOR))
    if sessao is None:
        return
    try:
        with timeout(5):
            _colecao().delete_one({"_id": sessao})
    except (PyMongoError, RuntimeError):
        raise HTTPException(503, "Não foi possível encerrar a sessão do monitor.") from None


if __name__ == "__main__":
    try:
        print("MONITOR_PASSWORD_HASH=" + gerar_verificador(getpass("Senha de 20 caracteres: ")))
    except ValueError as exc:
        raise SystemExit(str(exc))
