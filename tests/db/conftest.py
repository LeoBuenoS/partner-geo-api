"""Fixtures dos testes contra um PostGIS de verdade.

Os testes rápidos usam o adaptador em memória, que é cego para o que só o
PostGIS decide: `ST_Covers` na fronteira, `ST_Distance` sobre o esferoide, o
uso efetivo do índice GIST. Estes aqui fecham essa lacuna e rodam no job
`integracao-postgis` do CI. Sem `TEST_POSTGRES_URL`, a suíte é pulada.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.fixture(scope="session")
def engine_postgis():
    if not POSTGRES_URL:
        pytest.skip("TEST_POSTGRES_URL não definida")

    # O schema vem das migrations — o mesmo caminho da produção.
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", POSTGRES_URL)
    command.upgrade(config, "head")

    engine = create_engine(POSTGRES_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def sessao(engine_postgis):
    Session = sessionmaker(bind=engine_postgis, autoflush=False, autocommit=False)
    with Session() as sessao:
        yield sessao
        sessao.rollback()

    with engine_postgis.begin() as conexao:
        conexao.execute(text("TRUNCATE partners"))
