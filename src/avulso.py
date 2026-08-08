"""
Post avulso (fora da programação) — para publicar um versículo específico agora,
com o modelo novo (imagem, vídeo com trilha, legenda), SEM tocar na agenda nem no
histórico. Assim a programação diária continua exatamente igual.

    AVULSO_CONSULTA="filipenses 4:13" python3 -m src.avulso --fase preparar
    AVULSO_CONSULTA="filipenses 4:13" python3 -m src.avulso --fase publicar
    ... --fase ensaio    # gera e para; não publica

Arquivos vão para posts/avulso/<slug>.{jpg,mp4,txt} — nome próprio, não colide
com o post do dia (que é nomeado pela data).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src import imagem, instagram, legenda, versiculos, video
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
DIR_AVULSO = RAIZ / "posts" / "avulso"

CONSULTA_PADRAO = "filipenses 4:13"


def _slug(consulta: str) -> str:
    return consulta.replace(" ", "-").replace(":", "-")


def _versiculo():
    consulta = os.environ.get("AVULSO_CONSULTA", CONSULTA_PADRAO).strip().lower()
    pool = versiculos.carregar_pool()
    v = next((x for x in pool if x.consulta == consulta), None)
    if v is None:
        print(f"::error::Versículo '{consulta}' não está no acervo (dados/versiculos.json).", file=sys.stderr)
    return v


def _caminhos(consulta: str):
    slug = _slug(consulta)
    return (
        f"posts/avulso/{slug}.jpg", DIR_AVULSO / f"{slug}.jpg",
        f"posts/avulso/{slug}.mp4", DIR_AVULSO / f"{slug}.mp4",
        DIR_AVULSO / f"{slug}.txt",
    )


def preparar(ensaio: bool) -> int:
    v = _versiculo()
    if v is None:
        return 1
    print(f"[avulso] {v.referencia} — {len(v.texto)} caracteres")

    rel_jpg, jpg, rel_mp4, mp4, txt = _caminhos(v.consulta)
    seed = _slug(v.consulta)  # visual determinístico, mas diferente do post do dia
    imagem.gerar(v.texto, v.referencia, jpg, seed=seed)
    print(f"[imagem] {rel_jpg}")

    trilha_env = os.environ.get("AVULSO_TRILHA", "").strip()
    trilha = (RAIZ / "audio" / trilha_env) if trilha_env else None
    try:
        video.montar(jpg, mp4, seed=seed, trilha=trilha)
        print(f"[video] {rel_mp4} ({mp4.stat().st_size // 1024} KB){' | trilha ' + trilha_env if trilha_env else ''}")
    except video.VideoIndisponivel as erro:
        if not ensaio:
            print(f"::error::Não foi possível montar o vídeo: {erro}", file=sys.stderr)
            return 1
        print(f"[video] pulado no ensaio ({erro})")

    texto_legenda = legenda.gerar(v.texto, v.referencia, v.consulta)
    txt.write_text(texto_legenda + "\n", encoding="utf-8")
    print(f"[legenda]\n{texto_legenda}\n")

    if ensaio:
        print("[ensaio] avulso gerado; nada foi publicado")
    return 0


def publicar() -> int:
    v = _versiculo()
    if v is None:
        return 1
    rel_jpg, jpg, rel_mp4, mp4, txt = _caminhos(v.consulta)
    if not mp4.exists() or not txt.exists():
        print("::error::Arquivos do avulso não encontrados — rode a fase preparar.", file=sys.stderr)
        return 1

    texto_legenda = txt.read_text(encoding="utf-8").strip()
    url = url_publica(rel_mp4)
    capa = url_publica(rel_jpg)  # thumbnail = a imagem do versículo
    print(f"[video] {url}")

    try:
        id_reel = instagram.publicar_reel(url, texto_legenda, cover_url=capa)
        print(f"[instagram] Reel publicado: {id_reel}")
        try:
            id_story = instagram.publicar_story(url)
            print(f"[instagram] Story publicado: {id_story}")
        except instagram.ErroInstagram as erro:
            print(f"::warning::Reel publicado, mas o Story falhou: {erro}")
    except instagram.ErroInstagram as erro:
        print(f"::error::Falha ao publicar: {erro}", file=sys.stderr)
        return 1

    # Post avulso NÃO entra no histórico nem na agenda — a programação fica intacta.
    print("[avulso] publicado; agenda e histórico não foram alterados")
    return 0


def main() -> int:
    opcoes = argparse.ArgumentParser()
    opcoes.add_argument("--fase", choices=("preparar", "publicar", "ensaio"), required=True)
    argumentos = opcoes.parse_args()
    if argumentos.fase == "publicar":
        return publicar()
    return preparar(ensaio=argumentos.fase == "ensaio")


if __name__ == "__main__":
    raise SystemExit(main())
