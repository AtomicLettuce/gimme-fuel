"""Escala de color contínua verd pur (més barat) → vermell pur (més car)."""

import colorsys

import pandas as pd

# Tons HSL dels extrems: 120° = #00ff00, 0° = #ff0000, amb groc pur al mig.
TO_MES_BARAT = 120.0
TO_MES_CAR = 0.0
SATURACIO = 1.0
LLUMINOSITAT = 0.5

COLOR_SENSE_DADA = (137, 135, 129)


def calcula_posicions(preus: pd.Series) -> pd.Series:
    """Situa cada preu entre 0 (el més barat) i 1 (el més car) de la sèrie.

    Si tots els preus coincideixen, retorna 0 per a tots: l'únic preu possible
    es considera el més barat.

    :param preus: sèrie de preus, que pot contenir valors absents.
    :return: sèrie de posicions relatives, amb NaN on el preu és absent.
    """
    minim = preus.min()
    maxim = preus.max()
    if pd.isna(minim) or maxim == minim:
        return preus.notna().map({True: 0.0, False: float("nan")})
    return (preus - minim) / (maxim - minim)


def color_per_posicio(posicio: float) -> tuple[int, int, int]:
    """Interpola el color de l'escala per a una posició relativa.

    :param posicio: posició entre 0 (més barat) i 1 (més car); NaN si no hi ha
        preu, cas en què es retorna el gris de «sense dada».
    :return: component vermell, verd i blau, cada un entre 0 i 255.
    """
    if pd.isna(posicio):
        return COLOR_SENSE_DADA
    acotada = min(max(float(posicio), 0.0), 1.0)
    to = TO_MES_BARAT + (TO_MES_CAR - TO_MES_BARAT) * acotada
    vermell, verd, blau = colorsys.hls_to_rgb(to / 360.0, LLUMINOSITAT, SATURACIO)
    return (round(vermell * 255), round(verd * 255), round(blau * 255))


def a_hex(color: tuple[int, int, int]) -> str:
    """Converteix un color RGB a notació hexadecimal CSS.

    :param color: components vermell, verd i blau entre 0 i 255.
    :return: color en format #rrggbb.
    """
    return "#{:02x}{:02x}{:02x}".format(*color)


def hex_per_posicio(posicio: float) -> str:
    """Retorna directament el color hexadecimal d'una posició relativa.

    :param posicio: posició entre 0 (més barat) i 1 (més car), o NaN.
    :return: color en format #rrggbb.
    """
    return a_hex(color_per_posicio(posicio))


def genera_mostres(total: int) -> list[str]:
    """Genera colors equidistants de l'escala, del més barat al més car.

    Serveix per pintar la barra de la llegenda amb el mateix interpolador que
    els marcadors del mapa.

    :param total: nombre de mostres a generar; ha de ser com a mínim 2.
    :return: llista de colors hexadecimals ordenats de verd a vermell.
    :raises ValueError: si es demanen menys de dues mostres.
    """
    if total < 2:
        raise ValueError("Calen com a mínim dues mostres per dibuixar l'escala")
    return [hex_per_posicio(index / (total - 1)) for index in range(total)]
