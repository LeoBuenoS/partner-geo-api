"""Adaptador PostGIS.

A operação 1.3 do desafio é uma consulta só, resolvida pelo banco:

    WHERE  ST_Covers(coverage_area, :ponto)   -- filtro por índice GIST
    ORDER BY ST_Distance(address, :ponto)     -- ordena os que sobraram
    LIMIT 1

`ST_Covers` (e não `ST_Contains`) porque um ponto exatamente na fronteira da
área deve contar como coberto. As colunas são `geography`, então `ST_Distance`
já devolve metros sobre o esferoide WGS84 — sem conversão de graus para
distância, que é onde esse desafio costuma dar resultado errado.
"""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.entities.partner import Partner
from app.domain.errors import ConflitoDeDados
from app.domain.geo import MultiPoligono, Ponto

_COLUNAS = """
    id,
    trading_name,
    owner_name,
    document,
    ST_AsGeoJSON(address)::json       AS address,
    ST_AsGeoJSON(coverage_area)::json AS coverage_area
"""

_MAIS_PROXIMO_QUE_COBRE = text(f"""
    SELECT {_COLUNAS}
    FROM partners
    WHERE ST_Covers(coverage_area, ST_GeogFromText(:ponto))
    ORDER BY ST_Distance(address, ST_GeogFromText(:ponto))
    LIMIT 1
    """)


class PartnerRepositorioPostGIS:
    def __init__(self, db: Session):
        self.db = db

    def obter(self, partner_id: str) -> Partner | None:
        linha = (
            self.db.execute(
                text(f"SELECT {_COLUNAS} FROM partners WHERE id = :id"),
                {"id": partner_id},
            )
            .mappings()
            .first()
        )
        return self._para_entidade(linha) if linha else None

    def obter_por_documento(self, document: str) -> Partner | None:
        linha = (
            self.db.execute(
                text(f"SELECT {_COLUNAS} FROM partners WHERE document = :document"),
                {"document": document},
            )
            .mappings()
            .first()
        )
        return self._para_entidade(linha) if linha else None

    def criar(self, partner: Partner) -> Partner:
        try:
            self.db.execute(
                text("""
                    INSERT INTO partners (
                        id, trading_name, owner_name, document,
                        address, coverage_area
                    ) VALUES (
                        :id, :trading_name, :owner_name, :document,
                        ST_GeogFromText(:address),
                        ST_GeogFromText(:coverage_area)
                    )
                    """),
                {
                    "id": partner.id,
                    "trading_name": partner.trading_name,
                    "owner_name": partner.owner_name,
                    "document": partner.document,
                    "address": _para_ewkt_ponto(partner.address),
                    "coverage_area": _para_ewkt_multipoligono(partner.coverage_area),
                },
            )
            self.db.commit()
        except IntegrityError as erro:
            self.db.rollback()
            # O índice único do banco é a última linha de defesa contra corrida:
            # dois requests simultâneos passam pela checagem do caso de uso.
            raise ConflitoDeDados("id ou document já cadastrado") from erro
        return partner

    def mais_proximo_que_cobre(self, ponto: Ponto) -> Partner | None:
        linha = (
            self.db.execute(_MAIS_PROXIMO_QUE_COBRE, {"ponto": _para_ewkt_ponto(ponto)})
            .mappings()
            .first()
        )
        return self._para_entidade(linha) if linha else None

    @staticmethod
    def _para_entidade(linha) -> Partner:
        return Partner(
            id=linha["id"],
            trading_name=linha["trading_name"],
            owner_name=linha["owner_name"],
            document=linha["document"],
            address=Ponto.de_geojson(linha["address"]),
            coverage_area=MultiPoligono.de_geojson(linha["coverage_area"]),
        )


def _para_ewkt_ponto(ponto: Ponto) -> str:
    return f"SRID=4326;POINT({ponto.longitude} {ponto.latitude})"


def _para_ewkt_multipoligono(area: MultiPoligono) -> str:
    poligonos = []
    for poligono in area.poligonos:
        aneis = [
            "(" + ", ".join(f"{p.longitude} {p.latitude}" for p in anel) + ")"
            for anel in poligono
        ]
        poligonos.append("(" + ", ".join(aneis) + ")")
    return "SRID=4326;MULTIPOLYGON(" + ", ".join(poligonos) + ")"
