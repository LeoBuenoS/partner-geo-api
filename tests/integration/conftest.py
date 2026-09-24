"""Fixtures dos testes de integração da API.

Exercitam o stack HTTP inteiro (router → caso de uso → repositório), com o
adaptador em memória no lugar do PostGIS. Nenhum serviço externo é
necessário — o que é específico do PostGIS é coberto em `tests/db/`.
"""

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.repositories.partner_memory import PartnerRepositorioMemoria
from app.interfaces.http import deps
from app.main import app

AREA_UNITARIA = {
    "type": "MultiPolygon",
    "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]],
}

PAYLOAD = {
    "tradingName": "Adega da Cerveja - Pinheiros",
    "ownerName": "Zé da Silva",
    "document": "1432132123891/0001",
    "coverageArea": AREA_UNITARIA,
    "address": {"type": "Point", "coordinates": [0.5, 0.5]},
}


@pytest.fixture
def client():
    repositorio = PartnerRepositorioMemoria()
    app.dependency_overrides[deps.repositorio] = lambda: repositorio

    with TestClient(app) as cliente:
        yield cliente

    app.dependency_overrides.clear()
