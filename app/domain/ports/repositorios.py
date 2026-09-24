"""Portas de persistência.

O domínio declara o que precisa; a infraestrutura implementa. São Protocols:
o adaptador não herda de nada, basta ter a assinatura — e o teste passa um
adaptador em memória.
"""

from typing import Protocol

from app.domain.entities.partner import Partner
from app.domain.geo import Ponto


class PartnerRepositorio(Protocol):
    def obter(self, partner_id: str) -> Partner | None: ...

    def obter_por_documento(self, document: str) -> Partner | None: ...

    def criar(self, partner: Partner) -> Partner: ...

    def mais_proximo_que_cobre(self, ponto: Ponto) -> Partner | None:
        """O parceiro mais próximo entre os que cobrem o ponto.

        É a operação 1.3 do desafio, e a única com exigência de performance:
        a busca tem de ser resolvida por índice geoespacial, não varrendo a
        base.
        """
        ...
