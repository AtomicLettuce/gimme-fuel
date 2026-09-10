"""Configuració de l'aplicació d'estacions de servei."""

import os
from pathlib import Path

DIRECTORI_BASE = Path(__file__).resolve().parent

# Ruta de la base de dades SQLite. Sobreescrivible amb la variable d'entorn
# RUTA_BASE_DADES per no acoblar el codi a una ubicació concreta.
RUTA_BASE_DADES = Path(os.environ.get("RUTA_BASE_DADES", DIRECTORI_BASE / "data.db"))

# Centre i zoom del mapa (Mallorca) quan no es pot enquadrar cap estació.
CENTRE_PER_DEFECTE = (39.62, 2.95)
ZOOM_PER_DEFECTE = 10

# Columnes de carburant de la taula `prices` amb la seva etiqueta visible.
CARBURANTS = {
    "gasolina_95": "Gasolina 95",
    "gasolina_95_especial": "Gasolina 95 especial",
    "gasolina_95_e10": "Gasolina 95 E10",
    "gasolina_98": "Gasolina 98",
    "gasolina_98_especial": "Gasolina 98 especial",
    "gasoleo_A_normal": "Gasoil A",
    "gasoleo_A_especial": "Gasoil A especial",
    "gasoleo_B": "Gasoil B",
    "gasoleo_C": "Gasoil C",
    "biodiesel": "Biodièsel",
    "bioetanol": "Bioetanol",
    "gas_licuado_petroleo": "GLP",
    "gas_natural_comprimido": "GNC",
}

CARBURANT_PER_DEFECTE = "gasolina_95"

# Columnes descriptives que acompanyen cada estació.
COLUMNES_DESCRIPTIVES = [
    "num",
    "data",
    "lat",
    "lng",
    "rotul",
    "provincia",
    "localitat",
    "adreca",
    "horari",
    "telefon",
]
