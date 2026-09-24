from dataclasses import dataclass, field
from uuid import uuid4

from app.domain.errors import DadosInvalidos
from app.domain.geo import MultiPoligono, Ponto

TAMANHO_MAXIMO_TEXTO = 200


@dataclass(frozen=True)
class Partner:
    """Parceiro (bar, distribuidor) com sua área de cobertura.

    O desafio exige que `id` seja único mas não necessariamente numérico, e
    que `document` seja único. Aqui o `id` é um UUID gerado no domínio: não
    depende de sequência do banco, o que mantém a entidade independente da
    persistência e evita colisão entre instâncias.
    """

    trading_name: str
    owner_name: str
    document: str
    coverage_area: MultiPoligono
    address: Ponto
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        for campo in ("trading_name", "owner_name", "document", "id"):
            valor = getattr(self, campo)
            if not valor or not str(valor).strip():
                raise DadosInvalidos(f"{campo} é obrigatório")
            if len(str(valor)) > TAMANHO_MAXIMO_TEXTO:
                raise DadosInvalidos(
                    f"{campo} excede {TAMANHO_MAXIMO_TEXTO} caracteres"
                )

    def cobre(self, ponto: Ponto) -> bool:
        return self.coverage_area.contem(ponto)

    def distancia_ate(self, ponto: Ponto) -> float:
        """Distância em metros entre o endereço do parceiro e o ponto."""
        return self.address.distancia_em_metros(ponto)
