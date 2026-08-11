"""
Rotina do post do dia, em duas fases.

A divisão não é estética: a Graph API baixa a mídia de uma URL pública, então o
arquivo precisa já estar commitado e publicado no GitHub antes de a publicação
ser chamada. Fase 1 gera os arquivos, o workflow faz o commit, fase 2 publica.

    python3 -m src.principal --fase preparar
    python3 -m src.principal --fase publicar
    python3 -m src.principal --fase ensaio     # gera tudo e para; não publica

O post do dia é um Reel (vídeo vertical: a imagem do versículo + trilha) e o
MESMO vídeo vai também para o Story. A imagem quadrada (.jpg) continua sendo
gerada — é a fonte do vídeo, o arquivo do arquivo e a prévia da página de controle.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from src import imagem, instagram, legenda, versiculos, video

RAIZ = Path(__file__).resolve().parent.parent


class Caminhos:
    def __init__(self, dia: date):
        iso = dia.isoformat()
        self.rel_jpg = f"posts/{iso}.jpg"
        self.rel_mp4 = f"posts/{iso}.mp4"
        self.jpg = RAIZ / self.rel_jpg
        self.mp4 = RAIZ / self.rel_mp4
        self.txt = RAIZ / f"posts/{iso}.txt"


def url_publica(caminho_relativo: str) -> str:
    """
    URL crua do arquivo no GitHub, fixada no commit que o publicou.

    Usamos o SHA e não o nome do branch porque o raw do GitHub tem cache por
    referência: apontar para `main` logo após o push pode servir a versão
    anterior — ou um 404 — e o Instagram falha sem explicar direito.

    Exige repositório público: num privado o raw pede autenticação e o
    Instagram não consegue ler o arquivo.
    """
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    if not repositorio:
        raise RuntimeError("GITHUB_REPOSITORY não definido — rode dentro do workflow")
    ref = os.environ.get("IMAGEM_REF") or os.environ.get("GITHUB_SHA") or "main"
    return f"https://raw.githubusercontent.com/{repositorio}/{ref}/{caminho_relativo}"


def preparar(dia: date, ensaio: bool) -> int:
    escolhido = versiculos.escolher(dia)
    print(f"[versiculo] {escolhido.referencia} — {len(escolhido.texto)} caracteres")

    c = Caminhos(dia)
    caminho = imagem.gerar(escolhido.texto, escolhido.referencia, c.jpg, seed=dia.isoformat())
    print(f"[imagem] {c.rel_jpg} ({caminho.stat().st_size // 1024} KB)")

    # O vídeo (Reel/Story) é a imagem do dia + trilha, em 9:16. Precisa de ffmpeg
    # (existe no runner do GitHub Actions). Na máquina local sem ffmpeg, seguimos
    # sem o vídeo — o ensaio ainda mostra imagem e legenda.
    try:
        video.montar(c.jpg, c.mp4, seed=dia.isoformat())
        print(f"[video] {c.rel_mp4} ({c.mp4.stat().st_size // 1024} KB)")
    except video.VideoIndisponivel as erro:
        if not ensaio:
            print(f"::error::Não foi possível montar o vídeo: {erro}", file=sys.stderr)
            return 1
        print(f"[video] pulado no ensaio ({erro})")

    texto_legenda = legenda.gerar(escolhido.texto, escolhido.referencia, escolhido.consulta)
    c.txt.write_text(texto_legenda + "\n", encoding="utf-8")
    print(f"[legenda]\n{texto_legenda}\n")

    # Atualiza a agenda prevista dos próximos dias (a página de controle lê daqui).
    versiculos.escrever_agenda()
    print("[agenda] próximos dias atualizados em dados/agenda.json")

    if ensaio:
        print("[ensaio] arquivos gerados; nada foi publicado")
    return 0


def publicar(dia: date) -> int:
    # Idempotente: se o dia já está no histórico, o post de hoje já saiu (um
    # retry, ou o cron acordou depois de um disparo manual). Não publica duas vezes.
    ja_publicado = any(h.get("data") == dia.isoformat() for h in versiculos.carregar_historico())
    if ja_publicado:
        print(f"[instagram] o post de {dia.isoformat()} já foi publicado; nada a fazer")
        return 0

    c = Caminhos(dia)
    if not c.mp4.exists() or not c.txt.exists():
        print("::error::Arquivos do dia não encontrados — a fase preparar rodou?", file=sys.stderr)
        return 1

    texto_legenda = c.txt.read_text(encoding="utf-8").strip()
    url = url_publica(c.rel_mp4)
    capa = url_publica(c.rel_jpg)  # thumbnail = a imagem do versículo
    print(f"[video] {url}")

    try:
        id_reel = instagram.publicar_reel(url, texto_legenda, cover_url=capa)
        print(f"[instagram] Reel publicado: {id_reel}")
        # O Story é o mesmo vídeo do dia. Se falhar, não derruba o post do feed —
        # o Reel já foi publicado; só avisamos.
        try:
            id_story = instagram.publicar_story(url)
            print(f"[instagram] Story publicado: {id_story}")
        except instagram.ErroInstagram as erro:
            print(f"::warning::Reel publicado, mas o Story falhou: {erro}")
    except instagram.ErroInstagram as erro:
        print(f"::error::Falha ao publicar: {erro}", file=sys.stderr)
        return 1

    # Registra também as características do post (a inteligência aprende delas).
    import datetime as _dt
    hora_brt = (_dt.datetime.now(_dt.timezone.utc).hour - 3) % 24
    extras = {
        "estilo": imagem.escolher_estilo(
            versiculos.escolher(dia).texto, dia.isoformat()
        ),
        "hora": hora_brt,
        "trilha": video.escolher_trilha(dia.isoformat()).name,
    }
    versiculos.registrar(versiculos.escolher(dia), dia, id_reel, extras)
    # Regrava a agenda JÁ COM o post de hoje no histórico — senão o painel
    # continua mostrando o dia publicado como "próximo a publicar".
    versiculos.escrever_agenda()
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
