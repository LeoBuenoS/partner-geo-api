# ADR-0001 — PostGIS com colunas `geography`

**Status:** Aceita · **Data:** 2026-09 · **Contexto TOGAF:** Fase C (Dados)

## Contexto

A operação 1.3 do desafio precisa de duas coisas ao mesmo tempo: saber se um
polígono **contém** um ponto e medir **distância** entre pontos. A base pode
crescer, e o desafio trata performance como critério de avaliação.

## Alternativas consideradas

| Alternativa | Por que não |
|-------------|-------------|
| Filtrar em memória na aplicação | Simples, mas é O(n) por request e ignora o critério de performance. Vira o adaptador `memory`, para dev e teste — não para produção |
| PostgreSQL sem PostGIS, guardando GeoJSON em `JSONB` | Não há índice geoespacial: toda busca vira varredura |
| MongoDB com índice `2dsphere` | Resolve bem, e `$geoIntersects` é equivalente. Descartado por preferir SQL com restrição de unicidade nativa para `document` |
| PostGIS com colunas `geometry` | `ST_Distance` devolveria **graus**. Um grau de longitude vale ~111 km no equador e ~0 nos polos: ordenar por graus produz "mais próximo" errado fora do equador |
| **PostGIS com colunas `geography`** | **Escolhida** |

## Decisão

Colunas `geography(Point, 4326)` e `geography(MultiPolygon, 4326)`, com índice
GIST em ambas. A busca é uma consulta só:

```sql
WHERE ST_Covers(coverage_area, ST_GeogFromText(:ponto))
ORDER BY ST_Distance(address, ST_GeogFromText(:ponto))
LIMIT 1
```

`ST_Covers` em vez de `ST_Contains` porque um ponto na fronteira da área deve
contar como coberto — `ST_Contains` devolve falso para pontos na borda.

## Consequências

**A favor**

- `ST_Distance` devolve metros sobre o esferoide WGS84, sem conversão manual.
- O índice GIST descarta a maioria dos candidatos pela bounding box antes do
  teste exato de cobertura.
- Filtro, ordenação e limite acontecem no banco: trafega uma linha.

**Contra**

- Exige a extensão PostGIS, então a imagem `postgres:15` oficial não serve —
  o compose usa `postgis/postgis:15-3.4`.
- Operações em `geography` são mais caras que em `geometry` plano.
- O autogenerate do Alembic não conhece esses tipos: as colunas geográficas são
  criadas por SQL explícito na migration.

## Como verificar

`tests/db/test_paridade_postgis.py` cobre a fronteira, a equivalência com a
regra de domínio e lê o `EXPLAIN` para garantir que o índice é usado.
