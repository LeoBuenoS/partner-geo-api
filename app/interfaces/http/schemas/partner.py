"""Contratos HTTP.

Os nomes dos campos são os do desafio (`tradingName`, `ownerName`,
`coverageArea`), em camelCase — o contrato externo não muda por conveniência
interna. A conversão para os nomes do domínio acontece aqui.
"""

from pydantic import BaseModel, Field

from app.domain.entities.partner import Partner
from app.domain.geo import MultiPoligono, Ponto


class PartnerIn(BaseModel):
    id: str | None = Field(
        default=None, description="Opcional; o domínio gera um UUID se ausente"
    )
    tradingName: str = Field(min_length=1, max_length=200)  # noqa: N815
    ownerName: str = Field(min_length=1, max_length=200)  # noqa: N815
    document: str = Field(min_length=1, max_length=200)
    coverageArea: dict  # noqa: N815  — GeoJSON MultiPolygon
    address: dict  # GeoJSON Point

    def para_entidade(self) -> Partner:
        campos = {
            "trading_name": self.tradingName,
            "owner_name": self.ownerName,
            "document": self.document,
            "coverage_area": MultiPoligono.de_geojson(self.coverageArea),
            "address": Ponto.de_geojson(self.address),
        }
        if self.id:
            campos["id"] = self.id
        return Partner(**campos)


class PartnerOut(BaseModel):
    id: str
    tradingName: str  # noqa: N815
    ownerName: str  # noqa: N815
    document: str
    coverageArea: dict  # noqa: N815
    address: dict

    @classmethod
    def de_entidade(cls, partner: Partner) -> "PartnerOut":
        return cls(
            id=partner.id,
            tradingName=partner.trading_name,
            ownerName=partner.owner_name,
            document=partner.document,
            coverageArea=partner.coverage_area.para_geojson(),
            address=partner.address.para_geojson(),
        )
