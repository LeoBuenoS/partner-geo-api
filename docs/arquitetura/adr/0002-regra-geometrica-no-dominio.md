# ADR-0002 — A regra geométrica vive no domínio, e o banco a executa em escala

**Status:** Aceita · **Data:** 2026-09 · **Contexto TOGAF:** Fase C (Aplicação)

## Contexto

"A área de cobertura inclui esta localização" é a regra central do produto.
Ela poderia existir apenas como `ST_Covers` dentro de uma query — é o caminho
mais curto e o mais comum nesse desafio.

O problema é o que se perde: a regra some do código, só é testável com um
PostGIS de pé, e a camada de negócio fica sem o conceito mais importante do
domínio.

## Alternativas consideradas

| Alternativa | Por que não |
|-------------|-------------|
| Só no banco (`ST_Covers`) | Regra invisível no código e teste caro; o domínio não tem o conceito |
| Só na aplicação | Testável e explícito, mas O(n) por request — inviável com volume |
| **Nos dois, com teste de paridade** | **Escolhida** |

## Decisão

`app/domain/geo.py` implementa `MultiPoligono.contem(ponto)` com ray casting,
incluindo buracos, e `Ponto.distancia_em_metros` com haversine. O adaptador
PostGIS delega a mesma pergunta ao banco.

`tests/db/test_paridade_postgis.py` popula os dois adaptadores com a mesma
base, sorteia 50 pontos com semente fixa e exige a **mesma resposta** dos dois.

## Consequências

**A favor**

- A regra de negócio é legível e testável em milissegundos, sem banco.
- O adaptador em memória deixa de ser um dublê pobre: com `REPOSITORIO=memory`
  a API sobe inteira sem infraestrutura.
- A otimização no banco não pode mudar a semântica sem quebrar o CI.

**Contra**

- Duas implementações da mesma regra, que podem divergir — é exatamente o
  risco que o teste de paridade converte em falha de CI.
- O ray casting é simplificado: não trata o anti-meridiano nem geodésicas
  sobre o esferoide. Para áreas de entrega urbanas a diferença é irrelevante,
  e a limitação está anotada no código, não escondida.
- Haversine (esfera) e `ST_Distance` (esferoide) diferem em ~0,5%. Isso não
  muda **qual** parceiro é o mais próximo em distâncias urbanas, mas mudaria o
  valor se a distância virasse parte da resposta — e aí o domínio precisaria de
  um cálculo geodésico.
