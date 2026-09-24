from dataclasses import replace

import pytest

from app.application.use_cases import partners as casos
from app.domain.entities.partner import Partner
from app.domain.errors import ConflitoDeDados, DadosInvalidos, RecursoNaoEncontrado
from app.domain.geo import MultiPoligono, Ponto
from app.infrastructure.repositories.partner_memory import PartnerRepositorioMemoria


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


def _parceiro(
    nome: str = "Adega da Cerveja",
    documento: str = "1432132123891/0001",
    area: MultiPoligono | None = None,
    endereco: Ponto | None = None,
) -> Partner:
    return Partner(
        trading_name=nome,
        owner_name="Zé da Silva",
        document=documento,
        coverage_area=area or _area(0, 0),
        address=endereco or Ponto(longitude=0.5, latitude=0.5),
    )


@pytest.fixture
def repo():
    return PartnerRepositorioMemoria()


def test_criar_gera_id_quando_ausente(repo):
    criado = casos.CriarParceiro(repo).executar(_parceiro())

    assert criado.id
    assert repo.obter(criado.id) == criado


def test_documento_duplicado(repo):
    criar = casos.CriarParceiro(repo)
    criar.executar(_parceiro())

    with pytest.raises(ConflitoDeDados):
        criar.executar(_parceiro(nome="Outro bar"))


def test_id_duplicado(repo):
    criar = casos.CriarParceiro(repo)
    primeiro = criar.executar(_parceiro())

    repetido = replace(_parceiro(documento="outro/0001"), id=primeiro.id)
    with pytest.raises(ConflitoDeDados):
        criar.executar(repetido)


def test_campo_obrigatorio_em_branco():
    with pytest.raises(DadosInvalidos):
        _parceiro(nome="   ")


def test_obter_inexistente(repo):
    with pytest.raises(RecursoNaoEncontrado):
        casos.ObterParceiro(repo).executar("nao-existe")


def test_busca_ignora_quem_nao_cobre(repo):
    criar = casos.CriarParceiro(repo)
    # Perto do ponto, mas a área de cobertura está longe.
    criar.executar(
        _parceiro(
            nome="Perto mas não cobre",
            documento="perto/0001",
            area=_area(10, 10),
            endereco=Ponto(longitude=0.51, latitude=0.51),
        )
    )
    cobre = criar.executar(
        _parceiro(
            nome="Cobre",
            documento="cobre/0001",
            area=_area(0, 0),
            endereco=Ponto(longitude=0.9, latitude=0.9),
        )
    )

    encontrado = casos.BuscarParceiroMaisProximo(repo).executar(
        Ponto(longitude=0.5, latitude=0.5)
    )

    assert encontrado.id == cobre.id


def test_busca_escolhe_o_mais_proximo_entre_os_que_cobrem(repo):
    criar = casos.CriarParceiro(repo)
    longe = criar.executar(
        _parceiro(
            nome="Cobre, mas longe",
            documento="longe/0001",
            area=_area(0, 0, lado=2),
            endereco=Ponto(longitude=1.9, latitude=1.9),
        )
    )
    perto = criar.executar(
        _parceiro(
            nome="Cobre e está perto",
            documento="perto/0001",
            area=_area(0, 0, lado=2),
            endereco=Ponto(longitude=0.55, latitude=0.55),
        )
    )

    encontrado = casos.BuscarParceiroMaisProximo(repo).executar(
        Ponto(longitude=0.5, latitude=0.5)
    )

    assert encontrado.id == perto.id
    assert encontrado.id != longe.id


def test_busca_sem_cobertura(repo):
    casos.CriarParceiro(repo).executar(_parceiro(area=_area(10, 10)))

    with pytest.raises(RecursoNaoEncontrado):
        casos.BuscarParceiroMaisProximo(repo).executar(
            Ponto(longitude=0.5, latitude=0.5)
        )
