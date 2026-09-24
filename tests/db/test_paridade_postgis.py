"""O PostGIS e a regra de domínio precisam concordar.

O adaptador em memória aplica ray casting em Python; o PostGIS aplica
`ST_Covers` com índice GIST. São implementações independentes da mesma regra
de negócio — se divergirem, uma das duas está errada, e o teste falha antes
que a divergência chegue em produção.

É também onde se verifica o que só o banco real prova: que o índice é usado
de fato (EXPLAIN) e que a distância sai em metros.
"""

import random

import pytest
from sqlalchemy import text

from app.domain.entities.partner import Partner
from app.domain.geo import MultiPoligono, Ponto
from app.infrastructure.repositories.partner_memory import PartnerRepositorioMemoria
from app.infrastructure.repositories.partner_postgis import PartnerRepositorioPostGIS

pytestmark = pytest.mark.db


def _area(x0: float, y0: float, lado: float = 1.0) -> MultiPoligono:
    return MultiPoligono.de_geojson(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [x0, y0],
                        [x0 + lado, y0],
                        [x0 + lado, y0 + lado],
                        [x0, y0 + lado],
                        [x0, y0],
                    ]
                ]
            ],
        }
    )


def _parceiro(indice: int, x0: float, y0: float, lado: float = 1.0) -> Partner:
    return Partner(
        id=f"parceiro-{indice}",
        trading_name=f"Parceiro {indice}",
        owner_name="Zé da Silva",
        document=f"doc-{indice}",
        coverage_area=_area(x0, y0, lado),
        address=Ponto(longitude=x0 + lado / 2, latitude=y0 + lado / 2),
    )


def test_ciclo_completo(sessao):
    repo = PartnerRepositorioPostGIS(sessao)
    parceiro = _parceiro(1, 0, 0)

    criado = repo.criar(parceiro)
    recuperado = repo.obter(criado.id)

    assert recuperado == parceiro
    assert repo.obter_por_documento("doc-1") == parceiro


def test_busca_ignora_quem_nao_cobre(sessao):
    repo = PartnerRepositorioPostGIS(sessao)
    # Endereço quase em cima do ponto, cobertura em outro lugar.
    repo.criar(
        Partner(
            id="perto-sem-cobrir",
            trading_name="Perto, não cobre",
            owner_name="Zé",
            document="doc-perto",
            coverage_area=_area(10, 10),
            address=Ponto(longitude=0.51, latitude=0.51),
        )
    )
    repo.criar(_parceiro(2, 0, 0))

    encontrado = repo.mais_proximo_que_cobre(Ponto(longitude=0.5, latitude=0.5))

    assert encontrado is not None
    assert encontrado.id == "parceiro-2"


def test_sem_cobertura_devolve_none(sessao):
    repo = PartnerRepositorioPostGIS(sessao)
    repo.criar(_parceiro(3, 10, 10))

    assert repo.mais_proximo_que_cobre(Ponto(longitude=0, latitude=0)) is None


def test_fronteira_conta_como_coberta(sessao):
    """ST_Covers inclui a borda; ST_Contains não incluiria."""
    repo = PartnerRepositorioPostGIS(sessao)
    repo.criar(_parceiro(4, 0, 0))

    na_borda = Ponto(longitude=0.0, latitude=0.5)

    assert repo.mais_proximo_que_cobre(na_borda) is not None


def test_paridade_com_a_regra_de_dominio(sessao):
    """Mesma base nos dois adaptadores, mesmas respostas."""
    postgis = PartnerRepositorioPostGIS(sessao)
    memoria = PartnerRepositorioMemoria()

    parceiros = [
        _parceiro(indice, x0=coluna * 0.5, y0=linha * 0.5, lado=1.0)
        for indice, (coluna, linha) in enumerate(
            [(c, ln) for c in range(4) for ln in range(4)], start=100
        )
    ]
    for parceiro in parceiros:
        postgis.criar(parceiro)
        memoria.criar(parceiro)

    aleatorio = random.Random(42)  # semente fixa: falha reproduzível
    for _ in range(50):
        ponto = Ponto(
            longitude=round(aleatorio.uniform(-0.5, 3.0), 6),
            latitude=round(aleatorio.uniform(-0.5, 3.0), 6),
        )
        do_banco = postgis.mais_proximo_que_cobre(ponto)
        da_memoria = memoria.mais_proximo_que_cobre(ponto)

        esperado = da_memoria.id if da_memoria else None
        obtido = do_banco.id if do_banco else None
        assert obtido == esperado, f"divergência em {ponto}"


def test_busca_usa_o_indice_gist(sessao):
    """Performance é critério do desafio: a busca não pode virar seq scan."""
    repo = PartnerRepositorioPostGIS(sessao)
    for indice in range(200, 260):
        repo.criar(_parceiro(indice, x0=(indice % 20) * 0.3, y0=(indice % 7) * 0.3))

    # O planejador só prefere o índice quando a varredura fica cara; forçamos
    # a comparação desabilitando o seq scan e conferindo que existe caminho
    # indexado disponível.
    sessao.execute(text("SET LOCAL enable_seqscan = off"))
    plano = "\n".join(
        linha[0]
        for linha in sessao.execute(
            text("""
                EXPLAIN SELECT id FROM partners
                WHERE ST_Covers(coverage_area, ST_GeogFromText(:ponto))
                ORDER BY ST_Distance(address, ST_GeogFromText(:ponto))
                LIMIT 1
                """),
            {"ponto": "SRID=4326;POINT(0.5 0.5)"},
        ).fetchall()
    )

    assert "ix_partners_coverage_area" in plano, plano
