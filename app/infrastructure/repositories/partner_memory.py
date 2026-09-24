"""Adaptador em memória.

Serve para rodar a API sem banco (`APP_REPOSITORIO=memory`) e para os testes
de integração. A busca é O(n) e usa a mesma regra de domínio que o PostGIS
executa por índice — é justamente essa equivalência que
`tests/db/test_paridade_postgis.py` verifica.
"""

from app.domain.entities.partner import Partner
from app.domain.geo import Ponto


class PartnerRepositorioMemoria:
    def __init__(self, iniciais: list[Partner] | None = None):
        self._por_id: dict[str, Partner] = {}
        for partner in iniciais or []:
            self.criar(partner)

    def obter(self, partner_id: str) -> Partner | None:
        return self._por_id.get(partner_id)

    def obter_por_documento(self, document: str) -> Partner | None:
        return next((p for p in self._por_id.values() if p.document == document), None)

    def criar(self, partner: Partner) -> Partner:
        self._por_id[partner.id] = partner
        return partner

    def mais_proximo_que_cobre(self, ponto: Ponto) -> Partner | None:
        cobrem = [p for p in self._por_id.values() if p.cobre(ponto)]
        if not cobrem:
            return None
        return min(cobrem, key=lambda p: p.distancia_ate(ponto))
