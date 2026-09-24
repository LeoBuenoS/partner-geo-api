"""Adaptador em memória e composition root.

O adaptador PostGIS não aparece aqui de propósito: ele só faz sentido contra
um banco real e é coberto em `tests/db/`, no job `integracao-postgis` do CI.
"""

import pytest

from app.domain.entities.partner import Partner
from app.domain.errors import DadosInvalidos
from app.domain.geo import MultiPoligono, Ponto
from app.infrastructure.repositories.partner_memory import PartnerRepositorioMemoria
from app.interfaces.http import deps

AREA = MultiPoligono.de_geojson(
    {
        "type": "MultiPolygon",
        "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]],
    }
)


def _parceiro(indice: int = 1) -> Partner:
    return Partner(
        id=f"parceiro-{indice}",
        trading_name=f"Parceiro {indice}",
        owner_name="Zé da Silva",
        document=f"doc-{indice}",
        coverage_area=AREA,
        address=Ponto(longitude=0.5, latitude=0.5),
    )


def test_repositorio_aceita_carga_inicial():
    repo = PartnerRepositorioMemoria([_parceiro(1), _parceiro(2)])

    assert repo.obter("parceiro-1") is not None
    assert repo.obter_por_documento("doc-2") is not None
    assert repo.obter_por_documento("inexistente") is None


def test_busca_em_base_vazia():
    assert (
        PartnerRepositorioMemoria().mais_proximo_que_cobre(
            Ponto(longitude=0.5, latitude=0.5)
        )
        is None
    )


def test_campo_longo_demais_e_rejeitado():
    with pytest.raises(DadosInvalidos):
        Partner(
            trading_name="a" * 201,
            owner_name="Zé",
            document="doc",
            coverage_area=AREA,
            address=Ponto(longitude=0.5, latitude=0.5),
        )


def test_composition_root_respeita_a_configuracao(monkeypatch):
    """REPOSITORIO=memory sobe a API sem banco; o padrão usa PostGIS."""
    from app.infrastructure.config import settings
    from app.infrastructure.repositories.partner_postgis import (
        PartnerRepositorioPostGIS,
    )

    monkeypatch.setattr(settings, "repositorio", "memory")
    assert isinstance(deps.repositorio(db=None), PartnerRepositorioMemoria)

    monkeypatch.setattr(settings, "repositorio", "postgis")
    assert isinstance(deps.repositorio(db=None), PartnerRepositorioPostGIS)
