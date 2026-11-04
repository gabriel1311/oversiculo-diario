"""Gera a narração de cada cena de um episódio da série (voz oficial do perfil).

    python3 serie/falar.py serie/quarenta

Lê <pasta>/roteiro.json, grava <pasta>/audio/<id>.mp3 e <pasta>/tempos.json
(duração de cada fala). Cenas já narradas não são refeitas (apague o mp3 para refazer).
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
voz = json.loads((RAIZ / "dados" / "voz.json").read_text())  # mesma voz oficial do perfil
chave = Path.home().joinpath(".elevenlabs-key").read_text().strip()
pasta = Path(sys.argv[1])
roteiro = json.loads((pasta / "roteiro.json").read_text())
(pasta / "audio").mkdir(exist_ok=True)
falas = [c for c in roteiro["cenas"] if c["fala"]]


def duracao(arq):
    s = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                       capture_output=True, text=True, check=True)
    return float(s.stdout)


tempos = {}
for i, c in enumerate(falas):
    destino = pasta / "audio" / f"{c['id']}.mp3"
    if not destino.exists():
        ajustes = dict(voz["ajustes"])
        if c["id"] == "gancho":
            ajustes.update(voz.get("ajustes_gancho", {}))
        corpo = {"text": c["fala"], "model_id": voz["modelo"], "voice_settings": ajustes}
        if i > 0:
            corpo["previous_text"] = falas[i - 1]["fala"]
        if i + 1 < len(falas):
            corpo["next_text"] = falas[i + 1]["fala"]
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voz['vozes'][0]['voice_id']}?output_format=mp3_44100_128",
            data=json.dumps(corpo).encode(), method="POST",
            headers={"xi-api-key": chave, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            destino.write_bytes(r.read())
    tempos[c["id"]] = round(duracao(destino), 3)
    print(c["id"], tempos[c["id"]])

(pasta / "tempos.json").write_text(json.dumps(tempos, indent=1))
print("total", round(sum(tempos.values()), 1))
