"""
Monta dados/versiculos.json buscando os textos na bible-api.com uma única vez.

Por que existe: a API limita requisições em rajada (HTTP 429 por volta da 15ª).
Um post por dia caberia tranquilo, mas não há motivo para a rotina diária
depender de um serviço externo — a tradução de Almeida é domínio público, então
guardamos o texto no repositório e o post do dia não faz requisição nenhuma.

Uso:
    python3 ferramentas/montar_pool.py                 # completa o que falta
    python3 ferramentas/montar_pool.py --refazer       # busca tudo de novo
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "dados" / "versiculos.json"

# Referências no formato aceito pela bible-api.com (nomes em português).
# Para acrescentar, basta escrever a referência aqui e rodar o script.
REFERENCIAS = [
    "joao 3:16", "salmos 23:1-3", "filipenses 4:13", "proverbios 3:5-6",
    "isaias 41:10", "romanos 8:28", "josue 1:9", "salmos 46:1",
    "mateus 11:28", "jeremias 29:11", "salmos 119:105", "2 corintios 12:9",
    "hebreus 11:1", "1 joao 4:19", "galatas 5:22-23", "efesios 2:8-9",
    "salmos 37:5", "tiago 1:5", "1 pedro 5:7", "colossenses 3:23",
    "salmos 121:1-2", "lamentacoes 3:22-23", "mateus 6:33", "romanos 12:2",
    "1 corintios 13:4-7", "salmos 34:8", "proverbios 16:3", "isaias 40:31",
    "salmos 91:1-2", "joao 14:6", "salmos 27:1", "filipenses 4:6-7",
    "romanos 15:13", "1 tessalonicenses 5:16-18", "salmos 51:10",
    "provérbios 4:23", "mateus 5:16", "efesios 4:32", "salmos 139:14",
    "hebreus 13:8", "tiago 1:2-3", "salmos 62:1-2", "isaias 43:2",
    "joao 16:33", "2 timoteo 1:7", "salmos 100:4-5", "miqueias 6:8",
    "romanos 5:8", "salmos 145:18", "eclesiastes 3:1",
]

TAMANHO_MAXIMO = 260  # acima disso o texto não cai bem no quadrado 1080x1080


def limpar(texto: str) -> str:
    """A API devolve espaços não-quebráveis e quebras de linha no meio do versículo."""
    return " ".join(texto.replace(" ", " ").split())


def buscar(referencia: str, tentativas: int = 5) -> dict | None:
    url = "https://bible-api.com/" + urllib.parse.quote(referencia) + "?translation=almeida"
    espera = 3.0
    for tentativa in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=20) as resposta:
                dados = json.load(resposta)
        except urllib.error.HTTPError as erro:
            if erro.code == 429:
                print(f"    429 — esperando {espera:.0f}s", file=sys.stderr)
                time.sleep(espera)
                espera *= 2
                continue
            print(f"    HTTP {erro.code}", file=sys.stderr)
            return None
        except Exception as erro:  # rede instável
            print(f"    erro: {erro}", file=sys.stderr)
            time.sleep(espera)
            espera *= 2
            continue

        texto = limpar(dados.get("text", ""))
        if not texto:
            return None
        return {
            "referencia": dados["reference"],
            "texto": texto,
            "consulta": referencia,
        }
    return None


def main() -> int:
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--refazer", action="store_true")
    opcoes = argumentos.parse_args()

    existentes: dict[str, dict] = {}
    if DESTINO.exists() and not opcoes.refazer:
        for item in json.loads(DESTINO.read_text(encoding="utf-8")):
            existentes[item["consulta"]] = item

    resultado: list[dict] = []
    longos: list[tuple[str, int]] = []

    for referencia in REFERENCIAS:
        if referencia in existentes:
            resultado.append(existentes[referencia])
            continue
        print(f"  buscando {referencia}")
        item = buscar(referencia)
        if item is None:
            print(f"  ! falhou: {referencia}", file=sys.stderr)
            continue
        if len(item["texto"]) > TAMANHO_MAXIMO:
            longos.append((item["referencia"], len(item["texto"])))
        resultado.append(item)
        time.sleep(1.5)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\n{len(resultado)} versículos em {DESTINO.relative_to(RAIZ)}")
    if longos:
        print(f"\n{len(longos)} passaram de {TAMANHO_MAXIMO} caracteres — confira o enquadramento:")
        for referencia, tamanho in sorted(longos, key=lambda x: -x[1]):
            print(f"  {tamanho:4d}  {referencia}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
