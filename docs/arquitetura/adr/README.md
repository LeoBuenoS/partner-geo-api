# Architecture Decision Records

Cada arquivo registra **uma** decisão: contexto, alternativas, escolha e o que
ela custou. Decisão registrada não é revogada em silêncio — se mudar, entra um
ADR novo que substitui o anterior.

| ADR | Decisão | Status |
|-----|---------|--------|
| [0001](0001-postgis-geography.md) | PostGIS com colunas `geography` e índice GIST | Aceita |
| [0002](0002-regra-geometrica-no-dominio.md) | Regra geométrica no domínio, com teste de paridade contra o banco | Aceita |
| [0003](0003-clean-architecture.md) | Clean Architecture com portas e adaptadores | Aceita |
| [0004](0004-estrategia-de-testes.md) | Pirâmide de testes, banco real em job separado | Aceita |
