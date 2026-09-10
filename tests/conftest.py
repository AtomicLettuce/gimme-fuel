"""Fixtures compartides: base de dades temporal amb dades d'estacions."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repositori import RepositoriEstacions  # noqa: E402

_ESQUEMA = """
CREATE TABLE prices (
    num INTEGER,
    fecha TEXT,
    lat REAL,
    lng REAL,
    tipo TEXT,
    icono TEXT,
    provincia TEXT,
    localidad TEXT,
    direcc TEXT,
    rotulo TEXT,
    horario TEXT,
    gasolina_95 REAL,
    gasolina_95_especial REAL,
    gasolina_95_e10 REAL,
    gasolina_98 REAL,
    gasolina_98_especial REAL,
    gasoleo_A_normal REAL,
    gasoleo_A_especial REAL,
    gasoleo_B REAL,
    gasoleo_C REAL,
    biodiesel REAL,
    bioetanol REAL,
    gas_licuado_petroleo REAL,
    gas_natural_comprimido REAL,
    gasolinera_telefo TEXT,
    PRIMARY KEY (num, fecha)
)
"""

# num, fecha, lat, lng, localidad, direcc, rotulo, gasolina_95, gasoleo_A_normal
#
# El dia més recent del joc de proves és 02-09-2026. L'estació 5 només publica
# el dia anterior i, per tant, ha de quedar exclosa; l'estació 3 no té
# coordenades i l'estació 4 no publica cap preu.
_FILES = [
    (1, "01-09-2026 10:00", 39.60, 2.65, "PALMA", " CARRER A, 1 ", "REPSOL", 1.50, 1.40),
    (1, "02-09-2026 08:00", 39.60, 2.65, "PALMA", " CARRER A, 1 ", "REPSOL", 1.52, 1.42),
    (1, "02-09-2026 16:00", 39.60, 2.65, "PALMA", " CARRER A, 1 ", "REPSOL", 1.55, 1.45),
    (2, "02-09-2026 16:00", 39.71, 2.90, "INCA", "CARRER B, 2", "CEPSA", 1.45, 0.0),
    (3, "02-09-2026 16:00", None, 2.80, "CAMPOS", "CARRER C, 3", "BP", 1.70, 1.60),
    (4, "02-09-2026 16:00", 39.44, 3.01, "CAMPOS", "CARRER D, 4", "SET-GO", None, None),
    (5, "01-09-2026 10:00", 39.55, 2.73, "MANACOR", "CARRER E, 5", "BP", 1.30, 1.20),
]

DIA_MES_RECENT = "02-09-2026"


@pytest.fixture
def ruta_base_dades(tmp_path) -> Path:
    """Crea una base de dades SQLite temporal amb lectures conegudes.

    :param tmp_path: directori temporal proporcionat per pytest.
    :return: ruta al fitxer SQLite creat.
    """
    ruta = tmp_path / "proves.db"
    connexio = sqlite3.connect(ruta)
    with connexio:
        connexio.execute(_ESQUEMA)
        connexio.executemany(
            """
            INSERT INTO prices (
                num, fecha, lat, lng, localidad, direcc, rotulo,
                gasolina_95, gasoleo_A_normal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _FILES,
        )
    connexio.close()
    return ruta


@pytest.fixture
def repositori(ruta_base_dades) -> RepositoriEstacions:
    """Retorna un repositori connectat a la base de dades temporal."""
    return RepositoriEstacions(ruta_base_dades)


@pytest.fixture
def estacions(repositori):
    """Retorna la taula d'estacions del dia més recent de la BD temporal."""
    _, taula = repositori.obte_estacions()
    return taula
