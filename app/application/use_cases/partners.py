"""Casos de uso — as três operações do desafio.

Dependem só da porta `PartnerRepositorio`, então rodam em teste unitário com
um repositório falso: sem banco, sem HTTP.
"""

from dataclasses import dataclass

from app.domain.entities.partner import Partner
from app.domain.errors import ConflitoDeDados, RecursoNaoEncontrado
from app.domain.geo import Ponto
from app.domain.ports.repositorios import PartnerRepositorio


@dataclass
class CriarParceiro:
    """Operação 1.1 — Criar parceiro."""

    repositorio: PartnerRepositorio

    def executar(self, partner: Partner) -> Partner:
        # `document` é único por regra do desafio; `id` também.
        if self.repositorio.obter_por_documento(partner.document):
            raise ConflitoDeDados(f"document já cadastrado: {partner.document}")
        if self.repositorio.obter(partner.id):
            raise ConflitoDeDados(f"id já cadastrado: {partner.id}")
        return self.repositorio.criar(partner)


@dataclass
class ObterParceiro:
    """Operação 1.2 — Carregar parceiro pelo id."""

    repositorio: PartnerRepositorio

    def executar(self, partner_id: str) -> Partner:
        partner = self.repositorio.obter(partner_id)
        if not partner:
            raise RecursoNaoEncontrado("Parceiro não encontrado")
        return partner


@dataclass
class BuscarParceiroMaisProximo:
    """Operação 1.3 — Buscar parceiro.

    Duas condições, nesta ordem de importância: a área de cobertura precisa
    **conter** o ponto (filtro), e entre os que contêm vence o de endereço
    mais **próximo** (ordenação). Um parceiro perto mas que não cobre a
    localização não serve — é o erro comum nesse desafio.
    """

    repositorio: PartnerRepositorio

    def executar(self, ponto: Ponto) -> Partner:
        partner = self.repositorio.mais_proximo_que_cobre(ponto)
        if not partner:
            raise RecursoNaoEncontrado("Nenhum parceiro cobre a localização informada")
        return partner
