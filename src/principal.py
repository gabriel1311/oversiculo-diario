"""
Rotina do post do dia, em duas fases.

A divisão não é estética: a Graph API baixa a imagem de uma URL pública, então o
JPEG precisa já estar commitado e publicado no GitHub antes de a publicação ser
chamada. Fase 1 gera os arquivos, o workflow faz o commit, fase 2 publica.

    python3 -m src.principal --fase preparar
    python3 -m src.principal --fase publicar
    python3 -m src.principal --fase ensaio     # gera tudo e para; não publica
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from src import imagem, instagram, legenda, versiculos

RAIZ = Path(__file__).resolve().parent.parent


def _caminhos(dia: date) -> tuple[str, Path, Path]:
    relativo = f"posts/{dia.isoformat()}.jpg"
    return relativo, RAIZ / relativo, RAIZ / f"posts/{dia.isoformat()}.txt"


def url_publica(caminho_relativo: str) -> str:
    """
    URL crua do arquivo no GitHub, fixada no commit que o publicou.

    Usamos o SHA e não o nome do branch porque o raw do GitHub tem cache por
    referência: apontar para `main` logo após o push pode servir a versão
    anterior — ou um 404 — e o Instagram falha sem explicar direito.

    Exige repositório público: num privado o raw pede autenticação e o
    Instagram não consegue ler a imagem.
    """
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    if not repositorio:
        raise RuntimeError("GITHUB_REPOSITORY não definido — rode dentro do workflow")
    ref = os.environ.get("IMAGEM_REF") or os.environ.get("GITHUB_SHA") or "main"
    return f"https://raw.githubusercontent.com/{repositorio}/{ref}/{caminho_relativo}"


def preparar(dia: date, ensaio: bool) -> int:
    escolhido = versiculos.escolher(dia)
    print(f"[versiculo] {escolhido.referencia} — {len(escolhido.texto)} caracteres")

    relativo, destino_jpg, destino_txt = _caminhos(dia)
    caminho = imagem.gerar(escolhido.texto, escolhido.referencia, destino_jpg, seed=dia.isoformat())
    print(f"[imagem] {relativo} ({caminho.stat().st_size // 1024} KB)")

    texto_legenda = legenda.gerar(escolhido.texto, escolhido.referencia, escolhido.consulta)
    destino_txt.write_text(texto_legenda + "\n", encoding="utf-8")
    print(f"[legenda]\n{texto_legenda}\n")

    # Atualiza a agenda prevista dos próximos dias (a página de controle lê daqui).
    versiculos.escrever_agenda()
    print("[agenda] próximos dias atualizados em dados/agenda.json")

    if ensaio:
        print("[ensaio] arquivos gerados; nada foi publicado")
    return 0


def publicar(dia: date) -> int:
    relativo, destino_jpg, destino_txt = _caminhos(dia)
    if not destino_jpg.exists() or not destino_txt.exists():
        print("::error::Arquivos do dia não encontrados — a fase preparar rodou?", file=sys.stderr)
        return 1

    texto_legenda = destino_txt.read_text(encoding="utf-8").strip()

    restantes = instagram.dias_ate_expirar()
    if restantes is not None:
        print(f"[token] expira em {restantes} dias")
        if restantes <= 7:
            print(
                f"::warning::O token do Instagram expira em {restantes} dias. "
                "Gere um novo no Meta for Developers e atualize o secret IG_ACCESS_TOKEN."
            )

    url = url_publica(relativo)
    print(f"[imagem] {url}")

    try:
        id_post = instagram.publicar(url, texto_legenda)
    except instagram.ErroInstagram as erro:
        print(f"::error::Falha ao publicar: {erro}", file=sys.stderr)
        return 1

    print(f"[instagram] publicado: {id_post}")
    versiculos.registrar(versiculos.escolher(dia), dia, id_post)
    return 0


def main() -> int:
    opcoes = argparse.ArgumentParser()
    opcoes.add_argument("--fase", choices=("preparar", "publicar", "ensaio"), required=True)
    argumentos = opcoes.parse_args()

    hoje = date.today()
    if argumentos.fase == "publicar":
        return publicar(hoje)
    return preparar(hoje, ensaio=argumentos.fase == "ensaio")


if __name__ == "__main__":
    raise SystemExit(main())
