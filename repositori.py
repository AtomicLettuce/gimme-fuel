"""Accés de només lectura a la base de dades SQLite d'estacions de servei."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from configuracio import CARBURANTS, COLUMNES_DESCRIPTIVES

_logger = logging.getLogger(__name__)

# `fecha` es guarda com a text 'DD-MM-YYYY HH:MM', que no és ordenable
# lexicogràficament: es reconstrueix a 'YYYYMMDD' i 'YYYYMMDDHH:MM'.
_DIA_ORDENABLE = "substr(fecha, 7, 4) || substr(fecha, 4, 2) || substr(fecha, 1, 2)"
_DATA_ORDENABLE = f"{_DIA_ORDENABLE} || substr(fecha, 12, 5)"

_COLUMNES_CARBURANT = ", ".join(f"p.{columna}" for columna in CARBURANTS)
_NOMS_CARBURANT = ", ".join(CARBURANTS)

_CONSULTA_DIA_MES_RECENT = f"SELECT MAX({_DIA_ORDENABLE}) FROM prices"

# Només es consideren les lectures del dia més recent de la font: una estació
# que ha deixat de publicar preus no ha d'aparèixer amb dades caducades.
_CONSULTA_LECTURES_DEL_DIA = f"""
    WITH lectures AS (
        SELECT
            p.num, p.fecha, p.lat, p.lng, p.rotulo, p.provincia, p.localidad,
            p.direcc, p.horario, p.gasolinera_telefo, {_COLUMNES_CARBURANT},
            ROW_NUMBER() OVER (
                PARTITION BY p.num ORDER BY {_DATA_ORDENABLE} DESC
            ) AS posicio
        FROM prices AS p
        WHERE {_DIA_ORDENABLE} = ?
          AND p.lat IS NOT NULL AND p.lng IS NOT NULL
          AND p.lat BETWEEN -90 AND 90
          AND p.lng BETWEEN -180 AND 180
    )
    SELECT * FROM lectures WHERE posicio = 1
"""

# Sèrie diària d'una estació: una fila per dia, amb la lectura més tardana de
# cada dia, de la més antiga a la més recent.
_CONSULTA_HISTORIC = f"""
    WITH lectures AS (
        SELECT
            {_DIA_ORDENABLE} AS dia,
            {_COLUMNES_CARBURANT},
            ROW_NUMBER() OVER (
                PARTITION BY {_DIA_ORDENABLE} ORDER BY {_DATA_ORDENABLE} DESC
            ) AS posicio
        FROM prices AS p
        WHERE p.num = ?
    )
    SELECT dia, {_NOMS_CARBURANT} FROM lectures WHERE posicio = 1 ORDER BY dia
"""

_NOMS_COLUMNES = {
    "fecha": "data",
    "rotulo": "rotul",
    "localidad": "localitat",
    "direcc": "adreca",
    "horario": "horari",
    "gasolinera_telefo": "telefon",
}

_COLUMNES_TEXT = ["rotul", "provincia", "localitat", "adreca", "horari", "telefon"]


class RepositoriEstacions:
    """Repositori de lectura de les estacions de servei i els seus preus."""

    def __init__(self, ruta_base_dades: Path):
        """Crea el repositori.

        :param ruta_base_dades: ruta al fitxer SQLite amb la taula `prices`.
        :raises FileNotFoundError: si el fitxer no existeix.
        """
        self._ruta_base_dades = Path(ruta_base_dades)
        if not self._ruta_base_dades.is_file():
            raise FileNotFoundError(
                f"No s'ha trobat la base de dades: {self._ruta_base_dades}"
            )

    def obre_connexio(self) -> sqlite3.Connection:
        """Obre una connexió SQLite en mode només lectura.

        :return: connexió sobre la qual no es poden fer escriptures.
        """
        uri = f"file:{self._ruta_base_dades.as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def obte_estacions(self) -> tuple[str, pd.DataFrame]:
        """Obté les lectures del dia més recent de cada estació geolocalitzada.

        Les estacions que no han publicat preus aquell dia queden excloses. Els
        preus absents (`NULL` o `0,0` a la font) arriben com a `NaN`.

        :return: parell (dia en format DD-MM-YYYY, taula d'estacions); el dia és
            una cadena buida i la taula queda buida si la font no té lectures.
        """
        with closing(self.obre_connexio()) as connexio:
            dia_ordenable = connexio.execute(_CONSULTA_DIA_MES_RECENT).fetchone()[0]
            if dia_ordenable is None:
                _logger.warning("La font de dades no conté cap lectura de preus")
                return "", _taula_buida()
            estacions = pd.read_sql_query(
                _CONSULTA_LECTURES_DEL_DIA, connexio, params=(dia_ordenable,)
            )

        dia = _a_dia_llegible(dia_ordenable)
        _logger.info("Recuperades %d estacions del dia %s", len(estacions), dia)
        return dia, _normalitza(estacions)

    def obte_historic(self, num: int) -> pd.DataFrame:
        """Obté la sèrie diària de preus d'una estació, de la més antiga ençà.

        Si un dia té més d'una lectura, es queda amb la més tardana, igual que
        fa `obte_estacions`. Els preus absents arriben com a `NaN`.

        :param num: identificador de l'estació a la font (columna `num`).
        :return: taula amb la columna `dia` (data) i una columna per carburant;
            buida si l'estació no té cap lectura.
        :raises ValueError: si l'identificador no és un enter.
        """
        identificador = _a_identificador(num)
        with closing(self.obre_connexio()) as connexio:
            historic = pd.read_sql_query(
                _CONSULTA_HISTORIC, connexio, params=(identificador,)
            )

        if historic.empty:
            _logger.warning("L'estació %d no té cap lectura de preus", identificador)
            return _historic_buit()

        historic["dia"] = pd.to_datetime(historic["dia"], format="%Y%m%d")
        return _neteja_preus(historic)


def _taula_buida() -> pd.DataFrame:
    """Crea una taula d'estacions sense files però amb totes les columnes.

    :return: taula buida amb l'esquema que espera l'aplicació.
    """
    return pd.DataFrame(columns=COLUMNES_DESCRIPTIVES + list(CARBURANTS))


def _historic_buit() -> pd.DataFrame:
    """Crea una sèrie històrica sense files però amb totes les columnes.

    :return: taula buida amb l'esquema que espera el gràfic d'evolució.
    """
    buit = pd.DataFrame(columns=["dia"] + list(CARBURANTS))
    return buit.astype({"dia": "datetime64[ns]"})


def _neteja_preus(taula: pd.DataFrame) -> pd.DataFrame:
    """Converteix les columnes de carburant a preus numèrics arrodonits.

    A la font, l'absència de carburant es codifica com a NULL o 0,0: tots dos
    casos han d'arribar a l'aplicació com a `NaN`, no com a preu zero.

    :param taula: taula amb una columna per carburant.
    :return: la mateixa taula amb els preus com a nombres i els absents a NaN.
    """
    for columna in CARBURANTS:
        preus = pd.to_numeric(taula[columna], errors="coerce")
        taula[columna] = preus.where(preus > 0).round(3)
    return taula


def _a_identificador(num: int) -> int:
    """Valida que l'identificador d'estació rebut sigui un enter.

    :param num: identificador tal com arriba de la interfície.
    :return: identificador com a enter de Python.
    :raises ValueError: si el valor no es pot interpretar com a enter.
    """
    try:
        return int(num)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Identificador d'estació no vàlid: {num!r}") from error


def _normalitza(estacions: pd.DataFrame) -> pd.DataFrame:
    """Adapta el resultat cru de SQLite al model que consumeix l'aplicació.

    :param estacions: taula tal com la retorna la consulta.
    :return: taula amb noms en català, textos nets i preus absents com a NaN.
    """
    estacions = estacions.drop(columns=["posicio"]).rename(columns=_NOMS_COLUMNES)

    for columna in _COLUMNES_TEXT:
        estacions[columna] = estacions[columna].fillna("").astype(str).str.strip()

    estacions = _neteja_preus(estacions)

    ordenades = estacions.sort_values(["localitat", "adreca"], ignore_index=True)
    return ordenades[COLUMNES_DESCRIPTIVES + list(CARBURANTS)]


def _a_dia_llegible(dia_ordenable: str) -> str:
    """Converteix un dia 'YYYYMMDD' al format de la font 'DD-MM-YYYY'.

    :param dia_ordenable: dia en format ordenable de vuit dígits.
    :return: dia en format DD-MM-YYYY.
    """
    any_, mes, dia = dia_ordenable[:4], dia_ordenable[4:6], dia_ordenable[6:8]
    return f"{dia}-{mes}-{any_}"
