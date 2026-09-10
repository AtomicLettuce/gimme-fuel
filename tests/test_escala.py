"""Proves unitàries de l'escala de color verd → vermell."""

import pandas as pd
import pytest

import escala


def colorPerPosicio_posicioZero_retornaVerdPur():
    """L'estació més barata ha de rebre verd pur."""
    assert escala.hex_per_posicio(0.0) == "#00ff00"


def colorPerPosicio_posicioU_retornaVermellPur():
    """L'estació més cara ha de rebre vermell pur."""
    assert escala.hex_per_posicio(1.0) == "#ff0000"


def colorPerPosicio_posicioMitjana_retornaGrocPur():
    """El punt mitjà de la interpolació HSL és el groc pur."""
    assert escala.hex_per_posicio(0.5) == "#ffff00"


def colorPerPosicio_posicioAbsent_retornaGrisDeSenseDada():
    """Sense preu no hi ha posició a l'escala i cal el gris reservat."""
    assert escala.color_per_posicio(float("nan")) == escala.COLOR_SENSE_DADA


def colorPerPosicio_posicioForaDeRang_lAcota():
    """Una posició fora de [0, 1] s'ha d'acotar als extrems de l'escala."""
    assert escala.hex_per_posicio(-0.5) == "#00ff00"
    assert escala.hex_per_posicio(1.5) == "#ff0000"


def colorPerPosicio_posicionsCreixents_faDecreixerElVerd():
    """En encarir-se el preu, el component verd ha de baixar de forma monòtona."""
    verds = [escala.color_per_posicio(index / 20)[1] for index in range(21)]

    assert all(anterior >= seguent for anterior, seguent in zip(verds, verds[1:]))
    assert verds[0] == 255
    assert verds[-1] == 0


def calculaPosicions_preusDiversos_situaExtremsAZeroIU():
    """El preu mínim ha d'anar a 0 i el màxim a 1."""
    posicions = escala.calcula_posicions(pd.Series([1.5, 1.75, 2.0]))

    assert list(posicions) == [0.0, 0.5, 1.0]


def calculaPosicions_ambPreusAbsents_elsDeixaComNaN():
    """Les estacions sense preu no participen en l'escala."""
    posicions = escala.calcula_posicions(pd.Series([1.5, None, 2.0]))

    assert posicions.iloc[0] == 0.0
    assert pd.isna(posicions.iloc[1])
    assert posicions.iloc[2] == 1.0


def calculaPosicions_totsElsPreusIguals_retornaZero():
    """Sense recorregut de preus no es pot dividir: tot és el més barat."""
    posicions = escala.calcula_posicions(pd.Series([1.6, 1.6]))

    assert list(posicions) == [0.0, 0.0]


def calculaPosicions_serieBuida_retornaSerieBuida():
    """Un filtre sense resultats no ha de trencar el càlcul de l'escala."""
    assert escala.calcula_posicions(pd.Series([], dtype=float)).empty


def generaMostres_totalValid_retornaEscalaDeVerdAVermell():
    """La barra de la llegenda ha de començar en verd i acabar en vermell."""
    mostres = escala.genera_mostres(5)

    assert len(mostres) == 5
    assert mostres[0] == "#00ff00"
    assert mostres[-1] == "#ff0000"


def generaMostres_totalInsuficient_llancaValueError():
    """Amb menys de dues mostres no hi ha degradat possible."""
    with pytest.raises(ValueError):
        escala.genera_mostres(1)
