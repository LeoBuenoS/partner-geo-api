"""A regra geoespacial em Python puro — sem banco, sem HTTP."""

import pytest

from app.domain.errors import DadosInvalidos
from app.domain.geo import MultiPoligono, Ponto

# Quadrado de 1° x 1° com o canto em (0,0).
QUADRADO = {
    "type": "MultiPolygon",
    "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]],
}

# Mesmo quadrado, com um buraco central de 0,2° x 0,2°.
QUADRADO_COM_BURACO = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
            [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]],
        ]
    ],
}


def test_ponto_valido():
    ponto = Ponto.de_geojson({"type": "Point", "coordinates": [-46.57, -21.78]})
    assert ponto.longitude == -46.57
    assert ponto.latitude == -21.78


@pytest.mark.parametrize(
    "geojson",
    [
        {"type": "Polygon", "coordinates": [0, 0]},
        {"type": "Point", "coordinates": [0]},
        {"type": "Point", "coordinates": ["a", "b"]},
        {"type": "Point", "coordinates": [181, 0]},
        {"type": "Point", "coordinates": [0, 91]},
    ],
)
def test_ponto_invalido(geojson):
    with pytest.raises(DadosInvalidos):
        Ponto.de_geojson(geojson)


def test_multipoligono_valido():
    area = MultiPoligono.de_geojson(QUADRADO)
    assert area.para_geojson() == QUADRADO


@pytest.mark.parametrize(
    "geojson",
    [
        {"type": "Polygon", "coordinates": []},
        {"type": "MultiPolygon", "coordinates": []},
        {"type": "MultiPolygon", "coordinates": [[]]},
        # anel com menos de 4 posições
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [0, 0]]]]},
        # anel não fechado
        {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 1]]]]},
    ],
)
def test_multipoligono_invalido(geojson):
    with pytest.raises(DadosInvalidos):
        MultiPoligono.de_geojson(geojson)


@pytest.mark.parametrize(
    "lon,lat,esperado",
    [
        (0.5, 0.5, True),  # centro
        (0.01, 0.01, True),  # perto do canto, dentro
        (1.5, 0.5, False),  # fora, à direita
        (-0.1, 0.5, False),  # fora, à esquerda
        (0.5, 1.5, False),  # fora, acima
    ],
)
def test_cobertura_de_um_quadrado(lon, lat, esperado):
    area = MultiPoligono.de_geojson(QUADRADO)
    assert area.contem(Ponto(longitude=lon, latitude=lat)) is esperado


def test_buraco_nao_e_coberto():
    area = MultiPoligono.de_geojson(QUADRADO_COM_BURACO)

    assert area.contem(Ponto(longitude=0.5, latitude=0.5)) is False  # no buraco
    assert area.contem(Ponto(longitude=0.2, latitude=0.2)) is True  # fora do buraco


def test_multiplos_poligonos_desconexos():
    area = MultiPoligono.de_geojson(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]],
            ],
        }
    )

    assert area.contem(Ponto(longitude=0.5, latitude=0.5)) is True
    assert area.contem(Ponto(longitude=10.5, latitude=10.5)) is True
    assert area.contem(Ponto(longitude=5, latitude=5)) is False


def test_distancia_conhecida():
    """1° de latitude no equador ≈ 111,2 km."""
    origem = Ponto(longitude=0, latitude=0)
    destino = Ponto(longitude=0, latitude=1)

    distancia = origem.distancia_em_metros(destino)

    assert 111_000 < distancia < 111_400


def test_distancia_e_simetrica_e_nula_no_mesmo_ponto():
    a = Ponto(longitude=-46.57, latitude=-21.78)
    b = Ponto(longitude=-46.65, latitude=-21.80)

    assert a.distancia_em_metros(b) == pytest.approx(b.distancia_em_metros(a))
    assert a.distancia_em_metros(a) == pytest.approx(0)
