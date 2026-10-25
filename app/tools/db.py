import psycopg
from psycopg.rows import dict_row
from app.config import DATABASE_URL


def get_conn():
    """Abre conexão de leitura com o Postgres. Quem chama deve fechar."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg.connect(
        DATABASE_URL, row_factory=dict_row, connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=5000 "
        "-c timezone=America/Sao_Paulo",
    )
