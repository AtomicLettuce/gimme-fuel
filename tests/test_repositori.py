"""Proves unitàries del repositori d'estacions."""

import sqlite3

import pandas as pd
import pytest

from configuracio import CARBURANTS, COLUMNES_DESCRIPTIVES
from repositori import RepositoriEstacions

from conftest import DIA_MES_RECENT


def obteEstacions_lecturesDeVarisDies_retornaNomesLesDelDiaMesRecent(repositori):
    """Una estació que no publica el dia més recent no ha d'aparèixer."""
    dia, estacions = repositori.obte_estacions()

    assert dia == DIA_MES_RECENT
    assert set(estacions["num"]) == {1, 2, 4}


def obteEstacions_estacioSenseCoordenades_lExclou(estacions):
    """Les files sense coordenades no es poden situar al mapa."""
    assert 3 not in set(estacions["num"])


def obteEstacions_variesLecturesElMateixDia_retornaLaMesTardana(estacions):
    """Dins del dia més recent cal quedar-se amb l'última hora publicada."""
    palma = estacions[estacions["num"] == 1].iloc[0]

    assert palma["data"] == "02-09-2026 16:00"
    assert palma["gasolina_95"] == 1.55


def obteEstacions_preusZeroONuls_elsRetornaComNaN(estacions):
    """Un preu 0,0 o nul significa carburant no servit, no preu zero."""
    inca = estacions[estacions["num"] == 2].iloc[0]
    sense_preus = estacions[estacions["num"] == 4].iloc[0]

    assert pd.isna(inca["gasoleo_A_normal"])
    assert sense_preus[list(CARBURANTS)].isna().all()


def obteEstacions_qualsevolDia_retornaColumnesEnCatala(estacions):
    """L'aplicació consumeix noms en català, no els de la font en castellà."""
    assert list(estacions.columns) == COLUMNES_DESCRIPTIVES + list(CARBURANTS)


def obteEstacions_totesLesFiles_retornaCoordenadesValides(estacions):
    """Cada estació retornada ha de tenir latitud i longitud dins de rang."""
    assert estacions["lat"].between(-90, 90).all()
    assert estacions["lng"].between(-180, 180).all()


def obteEstacions_textAmbEspais_retornaTextNormalitzat(estacions):
    """Els camps de text de la font arriben amb espais sobrants o nuls."""
    palma = estacions[estacions["num"] == 1].iloc[0]

    assert palma["adreca"] == "CARRER A, 1"
    assert palma["telefon"] == ""


def obteEstacions_taulaSenseLectures_retornaDiaBuitITaulaBuida(tmp_path):
    """Sense dades no hi ha dia de referència i el mapa queda buit."""
    ruta = tmp_path / "buida.db"
    connexio = sqlite3.connect(ruta)
    with connexio:
        connexio.execute("CREATE TABLE prices (num INTEGER, fecha TEXT, lat REAL)")
    connexio.close()

    dia, estacions = RepositoriEstacions(ruta).obte_estacions()

    assert dia == ""
    assert estacions.empty
    assert list(estacions.columns) == COLUMNES_DESCRIPTIVES + list(CARBURANTS)


def constructor_rutaInexistent_llancaFileNotFoundError(tmp_path):
    """El repositori ha de fallar aviat si la font de dades no existeix."""
    with pytest.raises(FileNotFoundError):
        RepositoriEstacions(tmp_path / "inexistent.db")


def obreConnexio_baseDadesValida_esNomesLectura(repositori):
    """La connexió no ha de permetre escriptures sobre la font de dades."""
    connexio = repositori.obre_connexio()
    try:
        with pytest.raises(sqlite3.OperationalError):
            connexio.execute("DELETE FROM prices")
    finally:
        connexio.close()


def obteHistoric_estacioAmbLecturesDeVarisDies_retornaUnaFilaPerDia(repositori):
    """L'històric ha de portar un sol preu per dia, el de l'hora més tardana."""
    historic = repositori.obte_historic(1)

    assert len(historic) == 2
    assert list(historic["gasolina_95"]) == [1.50, 1.55]


def obteHistoric_qualsevolEstacio_ordenaDelDiaMesAnticAlMesRecent(repositori):
    """La sèrie ha d'anar en ordre cronològic per poder-la dibuixar."""
    historic = repositori.obte_historic(1)

    assert list(historic["dia"]) == sorted(historic["dia"])
    assert historic["dia"].iloc[0] == pd.Timestamp("2026-09-01")


def obteHistoric_preusZeroONuls_elsRetornaComNaN(repositori):
    """Un preu 0,0 a l'històric és carburant no servit, no preu zero."""
    historic = repositori.obte_historic(2)

    assert historic["gasoleo_A_normal"].isna().all()


def obteHistoric_estacioSenseLectures_retornaTaulaBuidaAmbLesColumnes(repositori):
    """Una estació desconeguda no ha de trencar el gràfic d'evolució."""
    historic = repositori.obte_historic(999)

    assert historic.empty
    assert list(historic.columns) == ["dia"] + list(CARBURANTS)


def obteHistoric_identificadorNoValid_llancaValueError(repositori):
    """L'identificador arriba de la interfície i s'ha de validar."""
    with pytest.raises(ValueError):
        repositori.obte_historic("1; DROP TABLE prices")
