"""Renderiza o post 1080x1080 a partir do versículo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "fontes"

LADO = 1080
MARGEM = 96

# Azul-marinho profundo + dourado. Mantido em sincronia com a logo.
FUNDO_TOPO = (11, 29, 58)
FUNDO_BASE = (24, 52, 94)
DOURADO = (206, 170, 106)
DOURADO_FRACO = (150, 122, 76)
TEXTO = (243, 240, 233)

HANDLE = "@oversiculo.diario"


def _fonte(arquivo: str, tamanho: int, peso: str = "Regular") -> ImageFont.FreeTypeFont:
    """
    Carrega uma fonte variável já fixada num peso.

    As duas fontes do projeto são variáveis (um arquivo cobre vários pesos), mas
    não oferecem os mesmos: EB Garamond vai de Regular a ExtraBold, Cinzel tem só
    Regular/Bold/Black. Pedir um peso inexistente levanta ValueError, então
    caímos no mais próximo disponível em vez de quebrar o render.
    """
    fonte = ImageFont.truetype(str(FONTES / arquivo), tamanho)
    try:
        disponiveis = [
            n.decode() if isinstance(n, bytes) else n for n in fonte.get_variation_names()
        ]
    except OSError:
        return fonte  # fonte estática — o peso já é o do arquivo

    if peso not in disponiveis:
        escala = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]
        alvo = escala.index(peso) if peso in escala else 0
        peso = min(
            disponiveis,
            key=lambda n: abs((escala.index(n) if n in escala else 0) - alvo),
        )
    fonte.set_variation_by_name(peso)
    return fonte


def _fundo() -> Image.Image:
    """Gradiente vertical suave com vinheta, montado pequeno e ampliado."""
    altura = 256
    gradiente = Image.new("RGB", (1, altura))
    pixels = gradiente.load()
    for y in range(altura):
        proporcao = y / (altura - 1)
        pixels[0, y] = tuple(
            round(FUNDO_TOPO[c] + (FUNDO_BASE[c] - FUNDO_TOPO[c]) * proporcao)
            for c in range(3)
        )
    base = gradiente.resize((LADO, LADO), Image.Resampling.BICUBIC)

    # Vinheta: escurece os cantos para o texto ganhar peso no centro.
    vinheta = Image.radial_gradient("L").resize((LADO, LADO), Image.Resampling.BICUBIC)
    escuro = Image.new("RGB", (LADO, LADO), (4, 12, 26))
    return Image.composite(escuro, base, vinheta.point(lambda v: int(v * 0.55)))


def _moldura(desenho: ImageDraw.ImageDraw) -> None:
    externa = 44
    interna = 60
    desenho.rectangle(
        [externa, externa, LADO - externa - 1, LADO - externa - 1],
        outline=DOURADO_FRACO,
        width=2,
    )
    desenho.rectangle(
        [interna, interna, LADO - interna - 1, LADO - interna - 1],
        outline=DOURADO,
        width=1,
    )


def _quebrar(
    texto: str, fonte: ImageFont.FreeTypeFont, largura_maxima: int, desenho: ImageDraw.ImageDraw
) -> list[str]:
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if desenho.textlength(tentativa, font=fonte) <= largura_maxima:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _ajustar(
    texto: str, desenho: ImageDraw.ImageDraw, largura: int, altura: int
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """
    Encolhe a fonte até o versículo caber na área reservada.

    Versículos longos existem no pool (1 Coríntios 13:4-7 tem 315 caracteres),
    então isto não é um caso hipotético — sem o ajuste o texto vaza da moldura.
    """
    for tamanho in range(64, 27, -2):
        fonte = _fonte("EBGaramond.ttf", tamanho, "Regular")
        linhas = _quebrar(texto, fonte, largura, desenho)
        espacamento = round(tamanho * 1.42)
        if len(linhas) * espacamento <= altura:
            return fonte, linhas, espacamento
    fonte = _fonte("EBGaramond.ttf", 28, "Regular")
    return fonte, _quebrar(texto, fonte, largura, desenho), 40


def _ornamento(desenho: ImageDraw.ImageDraw, centro_y: int) -> None:
    meio = LADO // 2
    largura = 90
    desenho.line([meio - largura, centro_y, meio - 14, centro_y], fill=DOURADO_FRACO, width=1)
    desenho.line([meio + 14, centro_y, meio + largura, centro_y], fill=DOURADO_FRACO, width=1)
    desenho.polygon(
        [(meio, centro_y - 6), (meio + 6, centro_y), (meio, centro_y + 6), (meio - 6, centro_y)],
        outline=DOURADO,
    )


def gerar(texto: str, referencia: str, destino: Path) -> Path:
    imagem = _fundo()
    desenho = ImageDraw.Draw(imagem)
    _moldura(desenho)

    largura_util = LADO - 2 * MARGEM - 60
    altura_util = 470

    # Aspas decorativas
    aspas = _fonte("EBGaramond.ttf", 190, "Medium")
    desenho.text((MARGEM + 18, 150), "“", font=aspas, fill=DOURADO_FRACO)

    fonte_texto, linhas, espacamento = _ajustar(texto, desenho, largura_util, altura_util)

    bloco = len(linhas) * espacamento
    y = 300 + (altura_util - bloco) // 2
    for linha in linhas:
        desenho.text((LADO // 2, y), linha, font=fonte_texto, fill=TEXTO, anchor="ma")
        y += espacamento

    _ornamento(desenho, y + 44)

    fonte_referencia = _fonte("Cinzel.ttf", 40, "SemiBold")
    desenho.text(
        (LADO // 2, y + 88), referencia.upper(), font=fonte_referencia, fill=DOURADO, anchor="ma"
    )

    fonte_handle = _fonte("Cinzel.ttf", 21, "Regular")
    desenho.text(
        (LADO // 2, LADO - 118),
        " ".join(HANDLE.upper()),  # espaçado, como marca d'água discreta
        font=fonte_handle,
        fill=DOURADO_FRACO,
        anchor="ma",
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino, "PNG", optimize=True)
    return destino
