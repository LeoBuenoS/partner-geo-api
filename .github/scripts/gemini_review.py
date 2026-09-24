#!/usr/bin/env python3
"""Revisão independente do diff por um modelo de outro fornecedor.

Por que existe: o código deste repositório é escrito com apoio do Claude. Uma
revisão feita pelo mesmo modelo que escreveu herda os mesmos pontos cegos.
O Gemini é de outro fornecedor, treinado de outro jeito — serve como segundo
canal de validação, independente por construção.

Só depende da biblioteca padrão: nada para instalar no CI.

Uso:
    gemini_review.py --base origin/main --head HEAD --saida revisao.md
    gemini_review.py --dry-run          # testa o encanamento sem chave nem rede
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API_RAIZ = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_S = 180

# Limite de caracteres do diff enviado. Diff gigante estoura contexto e degrada
# a revisão; acima disso, trunca e avisa no relatório.
LIMITE_DO_DIFF = 120_000

# Severidades, da mais grave para a mais leve. Só a primeira reprova o CI.
SEVERIDADES = ("blocker", "major", "minor", "nit")
SEVERIDADE_QUE_REPROVA = "blocker"

EMOJI = {"blocker": "🔴", "major": "🟠", "minor": "🟡", "nit": "🔵"}

INSTRUCOES = """\
Você é um revisor de código sênior e cético. Revise o diff abaixo e reporte
apenas defeitos que você consegue justificar com um cenário concreto de falha.

Classifique cada achado em uma severidade:

- "blocker": defeito que causa comportamento incorreto, perda de dados, falha
  em produção ou vulnerabilidade de segurança. Exige um cenário concreto
  (entrada/estado -> resultado errado). Na dúvida, NÃO use blocker.
- "major": bug provável, contrato violado ou caso de borda não tratado, sem a
  certeza do blocker.
- "minor": problema real, mas de impacto limitado.
- "nit": estilo, nomenclatura, preferência pessoal.

Regras:
- Não reporte ausência de testes como blocker.
- Não reporte preferência de estilo como blocker ou major.
- Não invente problema para ter o que reportar: lista vazia é uma resposta
  legítima e esperada quando o diff está correto.
- Cada achado precisa de arquivo e, quando possível, linha.
- Responda em português.

Responda SOMENTE com um objeto JSON, sem cercas de código, neste formato:

{
  "resumo": "uma frase sobre o que o diff faz e a qualidade geral",
  "achados": [
    {
      "severidade": "blocker|major|minor|nit",
      "arquivo": "caminho/do/arquivo.py",
      "linha": 42,
      "titulo": "frase curta",
      "descricao": "o defeito",
      "cenario_de_falha": "entrada/estado concreto -> resultado errado"
    }
  ]
}
"""


# --- git --------------------------------------------------------------------


def obter_diff(base: str, head: str) -> tuple[str, bool]:
    """Devolve (diff, foi_truncado)."""
    try:
        diff = subprocess.run(
            ["git", "diff", "--unified=3", f"{base}...{head}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        # `...` exige ancestral comum; num push isolado ele pode não existir.
        diff = subprocess.run(
            ["git", "diff", "--unified=3", base, head],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    if len(diff) > LIMITE_DO_DIFF:
        return diff[:LIMITE_DO_DIFF], True
    return diff, False


# --- API --------------------------------------------------------------------


def _requisitar(url: str, chave: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers={"x-goog-api-key": chave, "Content-Type": "application/json"},
        method="POST" if corpo is not None else "GET",
    )
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT_S) as resposta:
        return json.loads(resposta.read().decode())


def escolher_modelo(chave: str, preferido: str | None) -> str:
    """Escolhe um modelo entre os que a conta realmente tem.

    Nome de modelo cravado no código envelhece e quebra o CI sem aviso. Aqui a
    lista vem da própria conta: se `GEMINI_MODEL` estiver definido, ele manda;
    senão, escolhe o melhor disponível que suporte generateContent.
    """
    resposta = _requisitar(f"{API_RAIZ}/models", chave)
    disponiveis = [
        m["name"].removeprefix("models/")
        for m in resposta.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    if not disponiveis:
        raise RuntimeError("nenhum modelo com generateContent nesta conta")

    if preferido:
        if preferido in disponiveis:
            return preferido
        raise RuntimeError(
            f"GEMINI_MODEL={preferido!r} não está disponível. "
            f"Disponíveis: {', '.join(sorted(disponiveis))}"
        )

    # Sem preferência explícita: prioriza a família "pro" (mais capaz), depois
    # "flash", e dentro de cada uma a maior versão. Evita previews e modelos
    # especializados (embedding, imagem, TTS).
    def pontuar(nome: str) -> tuple:
        if any(t in nome for t in ("embedding", "image", "vision", "tts", "aqa")):
            return (-1, 0.0)
        familia = 2 if "pro" in nome else (1 if "flash" in nome else 0)
        estavel = 0 if any(t in nome for t in ("preview", "exp")) else 1
        versao = re.search(r"(\d+(?:\.\d+)?)", nome)
        return (familia, estavel, float(versao.group(1)) if versao else 0.0)

    melhor = max(disponiveis, key=pontuar)
    if pontuar(melhor)[0] < 0:
        raise RuntimeError(
            f"nenhum modelo de texto adequado. Disponíveis: {', '.join(disponiveis)}"
        )
    return melhor


def _extrair_json(texto: str) -> dict:
    """Tolera cercas de código e texto solto em volta do JSON."""
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = re.sub(r"^```[a-zA-Z]*\n?", "", limpo)
        limpo = re.sub(r"\n?```$", "", limpo.strip())
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        inicio, fim = limpo.find("{"), limpo.rfind("}")
        if inicio == -1 or fim <= inicio:
            raise
        return json.loads(limpo[inicio : fim + 1])


def revisar(chave: str, modelo: str, diff: str) -> dict:
    corpo = {
        "contents": [{"parts": [{"text": f"{INSTRUCOES}\n\n--- DIFF ---\n{diff}"}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    resposta = _requisitar(f"{API_RAIZ}/models/{modelo}:generateContent", chave, corpo)

    candidatos = resposta.get("candidates") or []
    if not candidatos:
        # Normalmente é bloqueio por filtro de segurança.
        raise RuntimeError(f"resposta sem candidates: {json.dumps(resposta)[:500]}")

    partes = candidatos[0].get("content", {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes)
    if not texto.strip():
        raise RuntimeError("resposta vazia do modelo")
    return _extrair_json(texto)


# --- relatório --------------------------------------------------------------


def _normalizar(resultado: dict) -> list[dict]:
    achados = resultado.get("achados")
    if not isinstance(achados, list):
        return []

    validos = []
    for achado in achados:
        if not isinstance(achado, dict):
            continue
        severidade = str(achado.get("severidade", "")).lower().strip()
        if severidade not in SEVERIDADES:
            severidade = "minor"  # severidade desconhecida não vira blocker
        # Blocker sem cenário concreto de falha não é blocker: é opinião.
        if severidade == SEVERIDADE_QUE_REPROVA and not str(
            achado.get("cenario_de_falha", "")
        ).strip():
            severidade = "major"
        validos.append({**achado, "severidade": severidade})
    return validos


def montar_markdown(resultado: dict, modelo: str, truncado: bool) -> str:
    achados = _normalizar(resultado)
    contagem = {s: sum(1 for a in achados if a["severidade"] == s) for s in SEVERIDADES}

    linhas = [
        "## 🔎 Revisão independente (Gemini)",
        "",
        f"_Segundo canal de validação, de outro fornecedor. Modelo: `{modelo}`._",
        "",
    ]
    if resumo := str(resultado.get("resumo", "")).strip():
        linhas += [f"> {resumo}", ""]
    if truncado:
        linhas += [
            f"⚠️ O diff excedeu {LIMITE_DO_DIFF:,} caracteres e foi truncado; "
            "a revisão cobriu apenas o começo.",
            "",
        ]

    if not achados:
        linhas.append("✅ Nenhum achado.")
        return "\n".join(linhas)

    placar = " · ".join(
        f"{EMOJI[s]} {contagem[s]} {s}" for s in SEVERIDADES if contagem[s]
    )
    linhas += [placar, ""]

    ordem = {s: i for i, s in enumerate(SEVERIDADES)}
    for achado in sorted(achados, key=lambda a: ordem[a["severidade"]]):
        local = str(achado.get("arquivo", "?"))
        if linha := achado.get("linha"):
            local += f":{linha}"
        linhas += [
            f"### {EMOJI[achado['severidade']]} {achado['severidade']} — "
            f"{achado.get('titulo', 'sem título')}",
            f"`{local}`",
            "",
            str(achado.get("descricao", "")).strip(),
        ]
        if cenario := str(achado.get("cenario_de_falha", "")).strip():
            linhas += ["", f"**Como falha:** {cenario}"]
        linhas.append("")

    if contagem[SEVERIDADE_QUE_REPROVA]:
        linhas += [
            "---",
            "",
            "🔴 **Este job reprova por achado `blocker`.** Se for falso positivo, "
            "aplique a etiqueta `gemini-override` no PR e rode de novo.",
        ]
    return "\n".join(linhas)


def decidir_saida(resultado: dict, override: bool) -> int:
    bloqueadores = [
        a for a in _normalizar(resultado) if a["severidade"] == SEVERIDADE_QUE_REPROVA
    ]
    if not bloqueadores:
        return 0
    if override:
        print(
            f"::warning::{len(bloqueadores)} achado(s) blocker ignorado(s) "
            "por etiqueta gemini-override"
        )
        return 0
    for achado in bloqueadores:
        print(
            f"::error file={achado.get('arquivo', '')}::"
            f"{achado.get('titulo', 'achado blocker')}"
        )
    return 1


# --- entrada ----------------------------------------------------------------


RESULTADO_DE_TESTE = {
    "resumo": "Execução de teste: nenhuma chamada de rede foi feita.",
    "achados": [
        {
            "severidade": "minor",
            "arquivo": "exemplo.py",
            "linha": 1,
            "titulo": "Achado de exemplo",
            "descricao": "Serve para conferir o encanamento do relatório.",
            "cenario_de_falha": "",
        }
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--saida", default="revisao-gemini.md")
    parser.add_argument(
        "--override",
        action="store_true",
        help="não reprova mesmo com achado blocker (etiqueta de escape)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="gera um relatório de exemplo, sem chave e sem rede",
    )
    args = parser.parse_args()

    if args.dry_run:
        markdown = montar_markdown(RESULTADO_DE_TESTE, "dry-run", truncado=False)
        print(markdown)
        return 0

    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chave:
        raise SystemExit("GEMINI_API_KEY não definida")

    diff, truncado = obter_diff(args.base, args.head)
    if not diff.strip():
        print("Nenhuma mudança de código para revisar.")
        return 0

    modelo = escolher_modelo(chave, os.environ.get("GEMINI_MODEL", "").strip() or None)
    print(f"Revisando com {modelo} ({len(diff):,} caracteres de diff)")

    resultado = revisar(chave, modelo, diff)
    markdown = montar_markdown(resultado, modelo, truncado)

    with open(args.saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(markdown)
    print(markdown)

    return decidir_saida(resultado, args.override)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as erro:
        # Falha de infraestrutura (rede, cota, chave, filtro) NÃO é defeito do
        # código e não deve travar o merge de todo mundo. Fica visível como
        # aviso; o gate continua valendo só para achado blocker de verdade.
        detalhe = erro.read().decode()[:500] if hasattr(erro, "read") else str(erro)
        print(f"::warning::revisão do Gemini indisponível: {detalhe}")
        sys.exit(0)
