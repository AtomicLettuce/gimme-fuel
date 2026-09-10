"""Proves unitàries de la resolució de rutes de la configuració."""

from pathlib import Path

import configuracio
from configuracio import DIRECTORI_BASE


def rutaBaseDades_senseVariableDEntorn_apuntaAlCostatDelCodi(monkeypatch):
    """Sense configurar res, la base de dades és la que acompanya el projecte."""
    monkeypatch.delenv("RUTA_BASE_DADES", raising=False)

    assert configuracio.ruta_base_dades() == DIRECTORI_BASE / "data.db"


def rutaBaseDades_variableAmbTitlla_lExpandeixAlDirectoriPersonal(monkeypatch):
    """`systemd` no expandeix la titlla: ho ha de fer l'aplicació."""
    monkeypatch.setenv("RUTA_BASE_DADES", "~/gimme-fuel/data.db")

    resolta = configuracio.ruta_base_dades()

    assert "~" not in str(resolta)
    assert resolta == Path.home() / "gimme-fuel" / "data.db"


def rutaBaseDades_variableAmbRutaAbsoluta_laRespecta(monkeypatch):
    """Una ruta absoluta ha d'arribar intacta al repositori."""
    monkeypatch.setenv("RUTA_BASE_DADES", "/srv/dades/estacions.db")

    assert configuracio.ruta_base_dades() == Path("/srv/dades/estacions.db")


def rutaBaseDades_variableBuida_tornaAlValorPerDefecte(monkeypatch):
    """Una variable buida no pot deixar l'aplicació apuntant enlloc."""
    monkeypatch.setenv("RUTA_BASE_DADES", "")

    assert configuracio.ruta_base_dades() == DIRECTORI_BASE / "data.db"
