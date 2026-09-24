"""Geometria GeoJSON como objeto de valor do domínio.

A regra "a área de cobertura inclui esta localização" é de negócio, não de
banco: ela vive aqui, em Python puro, e é testável sem infraestrutura. O
PostGIS a executa em escala — e `tests/db/test_paridade_postgis.py` exige que
os dois concordem.

Referência do formato: RFC 7946 (GeoJSON). Coordenadas são sempre
[longitude, latitude], nessa ordem.
"""

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from app.domain.errors import DadosInvalidos

RAIO_DA_TERRA_METROS = 6_371_008.8
LONGITUDE_MINIMA, LONGITUDE_MAXIMA = -180.0, 180.0
LATITUDE_MINIMA, LATITUDE_MAXIMA = -90.0, 90.0
POSICOES_MINIMAS_NO_ANEL = 4


@dataclass(frozen=True)
class Ponto:
    """GeoJSON Point."""

    longitude: float
    latitude: float

    def __post_init__(self) -> None:
        if not LONGITUDE_MINIMA <= self.longitude <= LONGITUDE_MAXIMA:
            raise DadosInvalidos(f"longitude fora do intervalo: {self.longitude}")
        if not LATITUDE_MINIMA <= self.latitude <= LATITUDE_MAXIMA:
            raise DadosInvalidos(f"latitude fora do intervalo: {self.latitude}")

    @classmethod
    def de_geojson(cls, geojson: dict) -> "Ponto":
        if geojson.get("type") != "Point":
            raise DadosInvalidos("address deve ser um GeoJSON Point")
        coordenadas = geojson.get("coordinates")
        if not isinstance(coordenadas, (list, tuple)) or len(coordenadas) != 2:
            raise DadosInvalidos("Point.coordinates deve ter [longitude, latitude]")
        try:
            longitude, latitude = float(coordenadas[0]), float(coordenadas[1])
        except (TypeError, ValueError) as erro:
            raise DadosInvalidos("coordenadas devem ser numéricas") from erro
        return cls(longitude=longitude, latitude=latitude)

    def para_geojson(self) -> dict:
        return {"type": "Point", "coordinates": [self.longitude, self.latitude]}

    def distancia_em_metros(self, outro: "Ponto") -> float:
        """Distância de grande círculo (haversine).

        O PostGIS usa `geography`, que calcula sobre o esferoide WGS84; a
        diferença para o haversine fica na casa de 0,5%, o que não muda qual
        parceiro é o mais próximo em distâncias urbanas.
        """
        lon1, lat1, lon2, lat2 = map(
            radians, (self.longitude, self.latitude, outro.longitude, outro.latitude)
        )
        seno_lat = sin((lat2 - lat1) / 2) ** 2
        seno_lon = sin((lon2 - lon1) / 2) ** 2
        arco = seno_lat + cos(lat1) * cos(lat2) * seno_lon
        return 2 * RAIO_DA_TERRA_METROS * asin(sqrt(arco))


def _validar_anel(anel: object, rotulo: str) -> list[Ponto]:
    if not isinstance(anel, (list, tuple)) or len(anel) < POSICOES_MINIMAS_NO_ANEL:
        raise DadosInvalidos(
            f"{rotulo} precisa de ao menos {POSICOES_MINIMAS_NO_ANEL} posições"
        )
    pontos = [Ponto.de_geojson({"type": "Point", "coordinates": p}) for p in anel]
    if pontos[0] != pontos[-1]:
        raise DadosInvalidos(f"{rotulo} deve ser fechado (primeira = última posição)")
    return pontos


def _dentro_do_anel(ponto: Ponto, anel: list[Ponto]) -> bool:
    """Ray casting: conta cruzamentos de um raio horizontal com as arestas.

    Ímpar = dentro, par = fora. É o algoritmo clássico de ponto-em-polígono,
    suficiente para as áreas urbanas deste domínio (não trata anti-meridiano).
    """
    dentro = False
    for atual, anterior in zip(anel, anel[1:]):
        cruza_a_latitude = (atual.latitude > ponto.latitude) != (
            anterior.latitude > ponto.latitude
        )
        if not cruza_a_latitude:
            continue
        proporcao = (ponto.latitude - atual.latitude) / (
            anterior.latitude - atual.latitude
        )
        longitude_na_aresta = atual.longitude + proporcao * (
            anterior.longitude - atual.longitude
        )
        if ponto.longitude < longitude_na_aresta:
            dentro = not dentro
    return dentro


@dataclass(frozen=True)
class MultiPoligono:
    """GeoJSON MultiPolygon.

    Cada polígono é uma lista de anéis: o primeiro é o contorno externo e os
    demais são buracos (RFC 7946, §3.1.6).
    """

    poligonos: tuple[tuple[tuple[Ponto, ...], ...], ...]

    @classmethod
    def de_geojson(cls, geojson: dict) -> "MultiPoligono":
        if geojson.get("type") != "MultiPolygon":
            raise DadosInvalidos("coverageArea deve ser um GeoJSON MultiPolygon")
        coordenadas = geojson.get("coordinates")
        if not isinstance(coordenadas, (list, tuple)) or not coordenadas:
            raise DadosInvalidos("MultiPolygon.coordinates não pode ser vazio")

        poligonos = []
        for indice, poligono in enumerate(coordenadas):
            if not isinstance(poligono, (list, tuple)) or not poligono:
                raise DadosInvalidos(f"polígono {indice} não pode ser vazio")
            aneis = tuple(
                tuple(_validar_anel(anel, f"anel {j} do polígono {indice}"))
                for j, anel in enumerate(poligono)
            )
            poligonos.append(aneis)
        return cls(poligonos=tuple(poligonos))

    def para_geojson(self) -> dict:
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [[[p.longitude, p.latitude] for p in anel] for anel in poligono]
                for poligono in self.poligonos
            ],
        }

    def contem(self, ponto: Ponto) -> bool:
        """True se o ponto cai em algum polígono e fora de todos os seus buracos."""
        for poligono in self.poligonos:
            contorno, buracos = poligono[0], poligono[1:]
            if not _dentro_do_anel(ponto, list(contorno)):
                continue
            if any(_dentro_do_anel(ponto, list(buraco)) for buraco in buracos):
                continue
            return True
        return False
