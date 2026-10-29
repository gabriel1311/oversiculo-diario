"""
Trial Reel do dia (29/10/2026): um Reel extra mostrado SÓ para quem não segue o
perfil. O alcance dos posts ficou parado em ~145 por 3 meses — quase todo ele
vem de seguidores. O teste leva conteúdo a gente nova sem encher o feed de quem
já segue, e com SS_PERFORMANCE o Instagram "gradua" sozinho o que for bem.

O que vai para o teste: um versículo que JÁ saiu há 30+ dias e teve boa taxa de
(envios + salvos + comentários) por alcance — quem não segue nunca viu — num
visual e gancho NOVOS (seed e variação próprios). Não entra no histórico nem na
agenda: a programação diária continua igual. O registro fica em
dados/testes.json (a coleta de métricas lê de lá).

    python3 -m src.teste --fase preparar
    python3 -m src.teste --fase publicar
    python3 -m src.teste --fase ensaio
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
from pathlib import Path

from src import imagem, instagram, legenda, versiculos, video
from src.principal import url_publica

RAIZ = Path(__file__).resolve().parent.parent
DIR_TESTE = RAIZ / "posts" / "teste"
ARQ_TESTES = RAIZ / "dados" / "testes.json"
ARQ_METRICAS = RAIZ / "dados" / "metricas.json"

IDADE_MINIMA = 30      # dias desde o post original
INTERVALO_REPETIR = 45  # dias até o mesmo versículo voltar ao teste


def _ler(caminho: Path, padrao):
    if not caminho.exists():
        return padrao
    return json.loads(caminho.read_text(encoding="utf-8"))


def taxa(m: dict) -> float:
    """Sinal que distribui para quem não segue, por alcance (comparável entre
    posts com bases de seguidores diferentes)."""
    alcance = max(m.get("alcance") or 0, 50)
    return (5 * (m.get("compartilhamentos") or 0) + 3 * (m.get("salvos") or 0)
            + (m.get("comentarios") or 0)) / alcance


def escolher(hoje: datetime.date) -> versiculos.Versiculo | None:
    pool = {v.consulta: v for v in versiculos.carregar_pool()}
    testados = {
        t["consulta"] for t in _ler(ARQ_TESTES, [])
        if t.get("consulta") and t["data"] >= (hoje - datetime.timedelta(days=INTERVALO_REPETIR)).isoformat()
    }
    limite = (hoje - datetime.timedelta(days=IDADE_MINIMA)).isoformat()
    candidatos = [
        m for m in _ler(ARQ_METRICAS, {}).get("posts", [])
        if m["data"] <= limite and m.get("consulta") in pool and m["consulta"] not in testados
    ]
    if not candidatos:
        return None
    candidatos.sort(key=lambda m: -taxa(m))
    # Entre os 5 melhores, gira pelo dia — evita insistir sempre no 1º.
    topo = candidatos[:5]
    return pool[topo[hoje.toordinal() % len(topo)]["consulta"]]


class Caminhos:
    def __init__(self, dia: datetime.date):
        iso = dia.isoformat()
        self.rel_jpg = f"posts/teste/{iso}.jpg"
        self.rel_mp4 = f"posts/teste/{iso}.mp4"
        self.jpg = RAIZ / self.rel_jpg
        self.mp4 = RAIZ / self.rel_mp4
        self.txt = DIR_TESTE / f"{iso}.txt"
        self.info = DIR_TESTE / f"{iso}.json"


def preparar(hoje: datetime.date, ensaio: bool) -> int:
    v = escolher(hoje)
    if v is None:
        print("[teste] nenhum versículo elegível hoje; nada a fazer")
        return 0
    c = Caminhos(hoje)
    seed = f"teste-{hoje.isoformat()}"
    variacao = seed
    print(f"[teste] {v.referencia} — estilo {imagem.escolher_estilo(v.texto, seed)}")

    imagem.gerar(v.texto, v.referencia, c.jpg, seed=seed)
    frase = legenda.gancho(v.consulta, variacao)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            camadas = imagem.gerar_camadas(v.texto, v.referencia, Path(tmp), seed=seed)
            gancho = imagem.gerar_gancho(frase, Path(tmp) / "gancho.png", cartaz=None if camadas else c.jpg)
            video.montar(c.jpg, c.mp4, seed=seed, duracao=video.duracao_para(v.texto),
                         camadas=camadas, gancho=gancho)
        print(f"[video] {c.rel_mp4} ({c.mp4.stat().st_size // 1024} KB)")
    except video.VideoIndisponivel as erro:
        if not ensaio:
            print(f"::error::Não foi possível montar o vídeo: {erro}", file=sys.stderr)
            return 1
        print(f"[video] pulado no ensaio ({erro})")

    texto = legenda.gerar(v.texto, v.referencia, v.consulta, variacao)
    c.txt.write_text(texto + "\n", encoding="utf-8")
    c.info.write_text(json.dumps({
        "consulta": v.consulta, "referencia": v.referencia,
        "estilo": imagem.escolher_estilo(v.texto, seed), "gancho": frase,
        "duracao": video.duracao_para(v.texto),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[legenda]\n{texto}\n")
    if ensaio:
        print("[ensaio] teste gerado; nada foi publicado")
    return 0


def publicar(hoje: datetime.date) -> int:
    c = Caminhos(hoje)
    if not c.info.exists():
        print("[teste] nada preparado hoje; nada a fazer")
        return 0
    testes = _ler(ARQ_TESTES, [])
    if any(t["data"] == hoje.isoformat() and t.get("id_post") for t in testes):
        print("[teste] o teste de hoje já saiu; nada a fazer")
        return 0

    info = json.loads(c.info.read_text(encoding="utf-8"))
    registro = {"data": hoje.isoformat(), **info}
    try:
        registro["id_post"] = instagram.publicar_reel(
            url_publica(c.rel_mp4), c.txt.read_text(encoding="utf-8").strip(),
            cover_url=url_publica(c.rel_jpg), teste=True,
        )
        print(f"[instagram] Trial Reel publicado: {registro['id_post']}")
    except instagram.ErroInstagram as erro:
        # Teste é extra: falhar (ex.: a conta ainda não tem Trial Reels) não pode
        # virar alarme diário. Fica registrado para a rodada/relatório verem.
        registro["erro"] = str(erro)[:300]
        print(f"::warning::Trial Reel não publicado: {erro}")

    testes = [t for t in testes if t["data"] != hoje.isoformat()] + [registro]
    ARQ_TESTES.write_text(json.dumps(testes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    opcoes = argparse.ArgumentParser()
    opcoes.add_argument("--fase", choices=("preparar", "publicar", "ensaio"), required=True)
    argumentos = opcoes.parse_args()
    hoje = datetime.date.today()
    if argumentos.fase == "publicar":
        return publicar(hoje)
    return preparar(hoje, ensaio=argumentos.fase == "ensaio")


if __name__ == "__main__":
    raise SystemExit(main())
