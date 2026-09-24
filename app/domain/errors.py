"""Erros de negócio, independentes de HTTP.

Quem traduz para status code é a camada de interface
(`app/interfaces/http/errors.py`).
"""


class ErroDeDominio(Exception):
    """Raiz de todos os erros de negócio."""


class RecursoNaoEncontrado(ErroDeDominio):
    """O parceiro pedido não existe, ou nenhum cobre a localização."""


class ConflitoDeDados(ErroDeDominio):
    """Violação de unicidade: `id` ou `document` já cadastrado."""


class DadosInvalidos(ErroDeDominio):
    """Geometria malformada ou campo obrigatório ausente."""
