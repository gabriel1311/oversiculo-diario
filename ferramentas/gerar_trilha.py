"""Gera a trilha instrumental ORIGINAL (sintetizada) para os vídeos.

Nada de sample nem de música de catálogo — cada nota é uma soma de senoides
calculada aqui, então não há risco de direitos autorais.

Pegada ELEGANTE: um pad de cordas quente, com acordes maj7/6 e swells lentos
(entra e sai suave, tipo naipe de cordas). Sem arpejo/plim-plim de caixinha de
música. Progressão maior e serena (Cmaj7–Fmaj7–G6–Cmaj7), pensada para ficar
por baixo do versículo com sofisticação.

    python3 ferramentas/gerar_trilha.py      # grava audio/trilha.wav (+2, +3)

Para trocar por outra música é só substituir audio/trilha.wav.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SR = 22050
SEG = 4.0          # segundos por acorde (respiração calma)
CF = 1.6           # crossfade longo entre acordes → legato de cordas
TOTAL = 16.0       # 4 acordes × 4 s — laço perfeito

NOTAS = {
    "C2": 65.41, "G2": 98.00,
    "F3": 174.61, "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "G4": 392.00, "B4": 493.88,
}
# Cmaj7 – Fmaj7 – G6 – Cmaj7 (I–IV–V–I com extensões): quente e elegante.
PROGRESSAO = [
    ["C4", "E4", "G4", "B4"],   # Cmaj7
    ["F3", "A3", "C4", "E4"],   # Fmaj7
    ["G3", "B3", "D4", "E4"],   # G6
    ["C4", "E4", "G4", "B4"],   # Cmaj7
]
ROOTS = ["C2", "F3", "G2", "C2"]  # nota grave (drone) de cada acorde

# Timbre de cordas: fundamental + harmônicos decrescentes (dá corpo sem estridência).
PARCIAIS = [(1, 1.0), (2, 0.5), (3, 0.32), (4, 0.20), (5, 0.12)]
# Naipe: três vozes levemente desafinadas por nota → largura e calor de conjunto.
DETUNES = [1.0, 1.0018, 0.9982]


def _voz_cordas(freq: float, t: float) -> float:
    vib = 1.0 + 0.0025 * math.sin(2 * math.pi * 5.0 * t)  # vibrato sutil
    val = 0.0
    for det in DETUNES:
        f = freq * det * vib
        for n, amp in PARCIAIS:
            val += amp * math.sin(2 * math.pi * f * n * t)
    return val / (len(DETUNES) * 2.2)


def _swell(t: float, dur: float) -> float:
    """Entrada/saída em cosseno (attack/release longos) → swell de cordas."""
    if t < CF:
        return 0.5 * (1 - math.cos(math.pi * t / CF))
    if t > dur - CF:
        return 0.5 * (1 - math.cos(math.pi * (dur - t) / CF))
    return 1.0


def gerar(nome: str = "trilha.wav", semitons: int = 0, desce: bool = False) -> Path:
    fator = 2.0 ** (semitons / 12.0)
    destino = RAIZ / "audio" / nome
    n_total = int(TOTAL * SR)
    buf = [0.0] * n_total
    dur_janela = SEG + CF
    n_janela = int(dur_janela * SR)

    for i, acorde in enumerate(PROGRESSAO):
        freqs = [NOTAS[n] * fator for n in acorde]
        drone = NOTAS[ROOTS[i]] * fator
        inicio = int((i * SEG - CF / 2) * SR)  # negativo dá a volta (laço)
        for n in range(n_janela):
            t = n / SR
            env = _swell(t, dur_janela)
            if env <= 0:
                continue
            amostra = sum(_voz_cordas(f, t) for f in freqs) / len(freqs)
            amostra += 0.5 * _voz_cordas(drone, t)  # base grave, suave
            buf[(inicio + n) % n_total] += env * amostra

    pico = max(abs(v) for v in buf) or 1.0
    ganho = 0.62 / pico

    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v * ganho)) * 32767)) for v in buf)
        )
    return destino


# Três variações em rotação (chaves diferentes), todas no mesmo timbre elegante.
VARIACOES = [
    ("trilha.wav", 0, False),    # Dó
    ("trilha2.wav", -2, False),  # Si bemol (mais grave/quente)
    ("trilha3.wav", 3, False),   # Mi bemol (um pouco mais claro)
]


if __name__ == "__main__":
    for nome, semitons, desce in VARIACOES:
        caminho = gerar(nome, semitons, desce)
        print(f"[trilha] {caminho.name} ({caminho.stat().st_size // 1024} KB, {TOTAL:.0f}s)")
