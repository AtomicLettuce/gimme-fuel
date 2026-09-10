"""Aplicació Streamlit que situa sobre un mapa les estacions de servei de data.db."""

import logging
from urllib.parse import urlencode

import altair as alt
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import escala
from configuracio import (
    CARBURANT_PER_DEFECTE,
    CARBURANTS,
    CENTRE_PER_DEFECTE,
    RUTA_BASE_DADES,
    ZOOM_PER_DEFECTE,
)
from repositori import RepositoriEstacions

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

MOSTRES_LLEGENDA = 24

# Durada de la memòria cau de les consultes a SQLite, en segons. Passada una
# hora, la primera interacció torna a llegir la font i en recull els canvis.
DURADA_CACHE = 3600

# Alçada del mapa i de la taula, que van de costat i han de quadrar.
ALCADA_PANELL = 520

# Zoom amb què el mapa emmarca l'estació de la fitxa: prou a prop per veure'n
# el carrer, mentre que el zoom per defecte abasta tota l'illa.
ZOOM_DETALL = 15

# Cerca de Google Maps per coordenades, amb la seva precisió recomanada de sis
# decimals (poc més d'un pam de resolució).
BASE_GOOGLE_MAPS = "https://www.google.com/maps/search/"
DECIMALS_COORDENADA = 6

# Prefix de les claus de sessió que guarden l'estat de cada casella de localitat.
PREFIX_LOCALITAT = "localitat__"
ALCADA_LLISTA_LOCALITATS = 260

# Clau del contenidor del filtre de preu: Streamlit hi afegeix la classe CSS
# `st-key-<clau>`, que és el punt d'ancoratge per acolorir la barra.
CLAU_FILTRE_PREU = "filtre_preu"
PAS_PREU = 0.001

# Marge per absorbir l'error de coma flotant en comparar preus amb els extrems
# que retorna el control lliscant.
TOLERANCIA_PREU = 1e-9

# Mida en píxels del marcador, amb la posició a dins o sense preu a mostrar.
MIDA_MARCADOR = 24
MIDA_MARCADOR_SENSE_PREU = 14

# Cos de lletra de la posició; les de tres xifres o més necessiten lletra petita
# per cabre dins del cercle.
COS_POSICIO = 11
COS_POSICIO_LLARGA = 9
XIFRES_POSICIO_LLARGA = 3

# Claus de sessió i del mapa que sostenen la vista de detall d'una estació.
CLAU_MAPA = "mapa"
CLAU_TAULA = "taula_estacions"
CLAU_ESTACIO = "estacio_seleccionada"
CLAU_ULTIM_CLIC = "ultim_clic"
CLAU_PERIODE = "periode_historic"

# Marge en graus per aparellar el marcador clicat amb la seva estació. Les
# coordenades tornen del mapa tal com s'han enviat, així que només ha d'absorbir
# l'error de coma flotant del viatge d'anada i tornada.
TOLERANCIA_COORDENADA = 1e-6

# Períodes que ofereix el selector de l'històric, en dies (None vol dir tot).
PERIODES_HISTORIC = {"30 dies": 30, "90 dies": 90, "Tot": None}
PERIODE_PER_DEFECTE = "90 dies"
ALCADA_GRAFIC = 260

# Color de la línia de l'històric, un to per cada tema de Streamlit perquè
# mantingui el contrast tant sobre fons clar com sobre fons fosc.
COLOR_HISTORIC = {"light": "#2a78d6", "dark": "#3987e5"}


@st.cache_data(show_spinner="Carregant estacions…", ttl=DURADA_CACHE)
def carrega_estacions(ruta_base_dades: str) -> tuple[str, pd.DataFrame]:
    """Llegeix les estacions del dia més recent i en cacheja el resultat.

    El resultat es reaprofita durant una hora: passat aquest temps, la primera
    interacció torna a consultar SQLite i recull els canvis de la font.

    :param ruta_base_dades: ruta al fitxer SQLite, com a text per poder cachejar.
    :return: parell (dia en format DD-MM-YYYY, taula d'estacions).
    """
    return RepositoriEstacions(ruta_base_dades).obte_estacions()


@st.cache_data(show_spinner="Carregant l'històric…", ttl=DURADA_CACHE)
def carrega_historic(ruta_base_dades: str, num: int) -> pd.DataFrame:
    """Llegeix la sèrie diària de preus d'una estació i en cacheja el resultat.

    Caduca al mateix ritme que `carrega_estacions`, així que la fitxa i el mapa
    no poden acabar mostrant lectures de dies diferents.

    :param ruta_base_dades: ruta al fitxer SQLite, com a text per poder cachejar.
    :param num: identificador de l'estació a la font.
    :return: taula amb la columna `dia` i una columna per carburant.
    """
    return RepositoriEstacions(ruta_base_dades).obte_historic(num)


def filtra_per_localitat(estacions: pd.DataFrame, localitats: list[str]) -> pd.DataFrame:
    """Filtra les estacions per les localitats marcades al filtre.

    Una llista buida vol dir que l'usuari ha desmarcat totes les localitats i,
    per tant, el resultat és buit: no és un sinònim de «no filtrar».

    :param estacions: taula completa d'estacions.
    :param localitats: localitats marcades.
    :return: subconjunt d'estacions de les localitats marcades.
    """
    return estacions[estacions["localitat"].isin(localitats)]


def clau_localitat(localitat: str) -> str:
    """Construeix la clau de sessió de la casella d'una localitat.

    :param localitat: nom de la localitat.
    :return: clau amb què es desa l'estat de la casella.
    """
    return f"{PREFIX_LOCALITAT}{localitat}"


def inicialitza_localitats(localitats: list[str]) -> None:
    """Marca totes les localitats el primer cop que es dibuixa el filtre.

    Les localitats ja presents a la sessió conserven el seu estat, de manera que
    els reruns no desfan la selecció de l'usuari.

    :param localitats: totes les localitats disponibles.
    """
    for localitat in localitats:
        st.session_state.setdefault(clau_localitat(localitat), True)


def marca_localitats(localitats: list[str], marcades: bool) -> None:
    """Marca o desmarca totes les caselles de localitat de cop.

    S'executa com a callback dels botons, abans que es torni a dibuixar la
    pàgina: així es pot escriure a les claus de les caselles sense que Streamlit
    es queixi de modificar un widget ja instanciat.

    :param localitats: totes les localitats disponibles.
    :param marcades: cert per marcar-les totes, fals per desmarcar-les totes.
    """
    for localitat in localitats:
        st.session_state[clau_localitat(localitat)] = marcades


def localitats_marcades(localitats: list[str]) -> list[str]:
    """Recull les localitats amb la casella marcada.

    :param localitats: totes les localitats disponibles.
    :return: localitats marcades, en el mateix ordre que s'han rebut.
    """
    return [
        localitat
        for localitat in localitats
        if st.session_state.get(clau_localitat(localitat), True)
    ]


def selecciona_localitats(localitats: list[str]) -> list[str]:
    """Dibuixa el desplegable de localitats amb una casella per localitat.

    Per defecte totes les localitats surten marcades i el desplegable inclou els
    botons de marcar-les i desmarcar-les totes.

    :param localitats: totes les localitats disponibles, ja ordenades.
    :return: localitats marcades després de dibuixar el filtre.
    """
    inicialitza_localitats(localitats)
    marcades = localitats_marcades(localitats)

    with st.popover(
        f"Localitats ({len(marcades)} de {len(localitats)})", width="stretch"
    ):
        botons = st.columns(2)
        botons[0].button(
            "Marca-les totes",
            on_click=marca_localitats,
            args=(localitats, True),
            width="stretch",
        )
        botons[1].button(
            "Desmarca-les totes",
            on_click=marca_localitats,
            args=(localitats, False),
            width="stretch",
        )
        with st.container(height=ALCADA_LLISTA_LOCALITATS, border=False):
            for localitat in localitats:
                st.checkbox(localitat, key=clau_localitat(localitat))

    return localitats_marcades(localitats)


def filtra_per_preu(
    estacions: pd.DataFrame,
    carburant: str,
    interval: tuple[float, float] | None,
    inclou_sense_preu: bool,
) -> pd.DataFrame:
    """Filtra les estacions pel preu del carburant seleccionat.

    :param estacions: taula d'estacions, ja filtrada per localitat.
    :param carburant: codi de la columna de carburant seleccionada.
    :param interval: preu mínim i màxim admesos; `None` quan no hi ha prou preus
        per oferir un interval i, per tant, no es filtra per preu.
    :param inclou_sense_preu: cert per mantenir les estacions que no publiquen
        aquest carburant, que no tenen preu amb què comparar-se.
    :return: subconjunt d'estacions dins de l'interval de preus.
    """
    preus = estacions[carburant]
    if interval is None:
        return estacions if inclou_sense_preu else estacions[preus.notna()]

    minim, maxim = interval
    dins = preus.between(minim - TOLERANCIA_PREU, maxim + TOLERANCIA_PREU)
    if inclou_sense_preu:
        dins = dins | preus.isna()
    return estacions[dins]


def selecciona_interval_preus(
    preus: pd.Series, carburant: str
) -> tuple[float, float] | None:
    """Dibuixa el control lliscant de preus, acolorit amb l'escala del mapa.

    El recorregut del control es calcula sobre **tots** els preus del carburant,
    no sobre els visibles, perquè els extrems no es moguin en filtrar.

    :param preus: preus del carburant seleccionat a tota la font de dades.
    :param carburant: codi del carburant, que forma part de la clau del widget
        perquè el rang es reinicialitzi en canviar de carburant.
    :return: preu mínim i màxim triats, o `None` si no hi ha prou preus per
        oferir un interval.
    """
    disponibles = preus.dropna()
    if disponibles.empty:
        st.caption("Cap estació publica aquest carburant: no hi ha res a filtrar.")
        return None

    minim = round(float(disponibles.min()), 3)
    maxim = round(float(disponibles.max()), 3)
    if minim >= maxim:
        st.caption(f"Només hi ha un preu publicat: {formata_preu(minim)}.")
        return None

    with st.container(key=CLAU_FILTRE_PREU, border=False):
        pinta_barra_lliscant()
        return st.slider(
            "Interval de preu",
            min_value=minim,
            max_value=maxim,
            value=(minim, maxim),
            step=PAS_PREU,
            format="%.3f €",
            key=f"preu__{carburant}",
        )


def genera_parades_degradat() -> str:
    """Genera les parades CSS del degradat de l'escala verd → vermell.

    :return: llista de parades llesta per a `linear-gradient`.
    """
    return ", ".join(
        f"{color} {index / (MOSTRES_LLEGENDA - 1):.0%}"
        for index, color in enumerate(escala.genera_mostres(MOSTRES_LLEGENDA))
    )


def pinta_barra_lliscant() -> None:
    """Acoloreix la barra del control lliscant amb l'escala verd → vermell.

    Streamlit no exposa cap paràmetre per acolorir la barra, així que s'injecta
    CSS acotat a la classe `st-key-<clau>` del contenidor del filtre: d'aquesta
    manera no pot afectar cap altre control de la pàgina.

    Els selectors s'ancoren als `data-testid` públics del control i no a les
    classes generades per Emotion, que canvien a cada compilació de Streamlit.
    L'arbre del control i els detalls que fan que el CSS s'apliqui són al
    README, a l'apartat «Escala de color».
    """
    arrel = f".st-key-{CLAU_FILTRE_PREU} [data-testid=\"stSlider\"]"
    barra = f'{arrel} div:has(> [data-testid="stSliderTickBar"]) > div:first-child'
    polze = f'{arrel} div:has(> [data-testid="stSliderThumbValue"])'

    # Sense indentació: Markdown convertiria en bloc de codi qualsevol línia
    # sagnada quatre espais o més, i el <style> no s'aplicaria.
    st.markdown(
        "<style>\n"
        f"{barra} {{background: linear-gradient(90deg, {genera_parades_degradat()})"
        " !important;}\n"
        f"{polze} {{background: #fcfcfb !important;"
        " border: 2px solid #0b0b0b !important; box-shadow: none !important;}\n"
        "</style>",
        unsafe_allow_html=True,
    )


def calcula_classificacio(preus: pd.Series) -> pd.Series:
    """Classifica les estacions per preu, de la més barata a la més cara.

    Les estacions amb el mateix preu comparteixen posició i la següent és la
    posició immediata, sense saltar-ne cap (1, 1, 2, 2, 2, 3): la posició
    numera els **preus** diferents, no les estacions.

    :param preus: preus del carburant seleccionat, amb absents com a NaN.
    :return: posició de cada estació, buida on no hi ha preu a classificar.
    """
    return preus.rank(method="dense").astype("Int64")


def prepara_vista(estacions: pd.DataFrame, carburant: str) -> pd.DataFrame:
    """Ordena les estacions per preu i hi afegeix el color i la classificació.

    Les estacions sense preu del carburant seleccionat es col·loquen al final,
    ordenades per localitat, per no barrejar-les amb els preus reals.

    :param estacions: estacions ja filtrades.
    :param carburant: codi de la columna de carburant seleccionada.
    :return: còpia amb les columnes `preu`, `posicio`, `color` i
        `classificacio` afegides.
    """
    vista = estacions.copy()
    vista["preu"] = vista[carburant]
    vista["posicio"] = escala.calcula_posicions(vista["preu"])
    vista["color"] = vista["posicio"].map(escala.hex_per_posicio)
    vista["classificacio"] = calcula_classificacio(vista["preu"])
    return vista.sort_values(
        ["preu", "localitat"], na_position="last", ignore_index=True
    )


def construeix_mapa(vista: pd.DataFrame) -> folium.Map:
    """Construeix el mapa amb un marcador per cada estació.

    El marcador no porta cap globus: clicar-lo obre la fitxa de l'estació al
    costat del mapa, que és on es mostra tot el detall.

    :param vista: estacions preparades per `prepara_vista`.
    :return: mapa Folium enquadrat sobre les estacions rebudes.
    """
    mapa = folium.Map(location=list(CENTRE_PER_DEFECTE), zoom_start=ZOOM_PER_DEFECTE)
    if vista.empty:
        return mapa

    for estacio in vista.itertuples():
        folium.Marker(
            location=[estacio.lat, estacio.lng],
            icon=_crea_icona(estacio),
            tooltip=_crea_etiqueta(estacio),
        ).add_to(mapa)

    mapa.fit_bounds(
        [
            [vista["lat"].min(), vista["lng"].min()],
            [vista["lat"].max(), vista["lng"].max()],
        ],
        padding=(20, 20),
    )
    return mapa


def _crea_icona(estacio) -> folium.DivIcon:
    """Crea el cercle acolorit del marcador, amb la posició escrita a dins.

    Les estacions que no publiquen el carburant no tenen posició: es dibuixen
    amb un cercle gris més petit i sense número.

    :param estacio: fila d'estació obtinguda per iteració de la vista.
    :return: icona HTML centrada sobre les coordenades de l'estació.
    """
    if pd.isna(estacio.classificacio):
        return _crea_cercle(MIDA_MARCADOR_SENSE_PREU, estacio.color, "", COS_POSICIO)

    posicio = str(int(estacio.classificacio))
    cos = COS_POSICIO_LLARGA if len(posicio) >= XIFRES_POSICIO_LLARGA else COS_POSICIO
    return _crea_cercle(MIDA_MARCADOR, estacio.color, posicio, cos)


def _crea_cercle(mida: int, color: str, text: str, cos_lletra: int) -> folium.DivIcon:
    """Construeix el cercle HTML d'un marcador.

    La tinta és fosca sobre qualsevol color de l'escala: verds, grocs i vermells
    purs són tons mitjans i el text negre hi manté prou contrast.

    :param mida: diàmetre del cercle en píxels.
    :param color: color de farciment, ja calculat per l'escala.
    :param text: posició a escriure a dins, buida si no n'hi ha.
    :param cos_lletra: cos de lletra del text en píxels.
    :return: icona HTML ancorada pel seu centre.
    """
    estil = (
        f"width:{mida}px;height:{mida}px;box-sizing:border-box;border-radius:50%;"
        f"background:{color};"
        # Contorn fosc: l'escala passa per grocs i verds saturats que sobre les
        # tessel·les clares es perdrien amb un contorn blanc.
        "border:1.25px solid rgba(11,11,11,0.65);"
        "display:flex;align-items:center;justify-content:center;"
        f"color:#0b0b0b;font-family:sans-serif;font-size:{cos_lletra}px;"
        "font-weight:700;line-height:1;"
    )
    return folium.DivIcon(
        html=f'<div style="{estil}">{text}</div>',
        icon_size=(mida, mida),
        icon_anchor=(mida // 2, mida // 2),
    )


def crea_ressaltat(estacio: pd.Series | None) -> folium.FeatureGroup:
    """Crea la capa que envolta amb un anell l'estació seleccionada.

    Va en una capa a part i no dins del mapa perquè `st_folium` afegeix els
    grups de components sense refer el mapa: així la selecció no desfà
    l'enquadrament ni el zoom que hagi triat l'usuari.

    :param estacio: fila de l'estació seleccionada, o `None` si no n'hi ha cap.
    :return: capa amb l'anell de selecció, buida si no hi ha selecció.
    """
    capa = folium.FeatureGroup(name="seleccio")
    if estacio is None:
        return capa

    folium.CircleMarker(
        location=[estacio["lat"], estacio["lng"]],
        radius=17,
        color="#0b0b0b",
        weight=3,
        opacity=0.9,
        fill=False,
        # L'anell no és clicable: Leaflet només retorna les coordenades exactes
        # del centre en cercles de radi petit, i un clic damunt seu enviaria les
        # del cursor, que no aparellarien amb cap estació.
        interactive=False,
    ).add_to(capa)
    return capa


def url_google_maps(lat: float, lng: float) -> str:
    """Construeix l'enllaç que situa unes coordenades a Google Maps.

    :param lat: latitud de l'estació, entre -90 i 90.
    :param lng: longitud de l'estació, entre -180 i 180.
    :return: URL de Google Maps amb el punt marcat.
    :raises ValueError: si les coordenades no són números dins de rang.
    """
    try:
        latitud, longitud = float(lat), float(lng)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Coordenades no vàlides: {lat!r}, {lng!r}") from error

    if not (-90 <= latitud <= 90 and -180 <= longitud <= 180):
        raise ValueError(f"Coordenades fora de rang: {latitud}, {longitud}")

    punt = f"{latitud:.{DECIMALS_COORDENADA}f},{longitud:.{DECIMALS_COORDENADA}f}"
    return f"{BASE_GOOGLE_MAPS}?{urlencode({'api': 1, 'query': punt})}"


def enquadra_estacio(
    estacio: pd.Series | None,
) -> tuple[tuple[float, float] | None, int | None]:
    """Calcula el centre i el zoom amb què el mapa ha d'emmarcar la selecció.

    `st_folium` mou el mapa sense refer-lo i només quan el valor canvia: sense
    estació oberta es retorna `None` i el mapa es queda tal com el tingui
    l'usuari.

    :param estacio: fila de l'estació seleccionada, o `None` si no n'hi ha cap.
    :return: parell (centre, zoom), tots dos `None` si no hi ha selecció.
    """
    if estacio is None:
        return None, None
    return (float(estacio["lat"]), float(estacio["lng"])), ZOOM_DETALL


def cerca_estacio_al_punt(vista: pd.DataFrame, lat: float, lng: float) -> int | None:
    """Cerca l'estació de la vista situada en unes coordenades.

    :param vista: estacions preparades per `prepara_vista`.
    :param lat: latitud del marcador clicat.
    :param lng: longitud del marcador clicat.
    :return: identificador de l'estació, o `None` si cap no hi coincideix.
    """
    if vista.empty:
        return None

    distancies = (vista["lat"] - lat).abs() + (vista["lng"] - lng).abs()
    if distancies.min() > TOLERANCIA_COORDENADA:
        return None
    return int(vista.loc[distancies.idxmin(), "num"])


def selecciona_estacio(num: int | None) -> None:
    """Desa l'estació de la qual s'ha de mostrar el detall.

    :param num: identificador de l'estació, o `None` per tornar al llistat.
    """
    st.session_state[CLAU_ESTACIO] = num


def canvia_seleccio(num: int | None) -> bool:
    """Obre la fitxa d'una estació i diu si això canvia el que es mostra.

    :param num: identificador de l'estació, o `None` per tornar al llistat.
    :return: cert si abans hi havia oberta una altra estació.
    """
    if num == st.session_state.get(CLAU_ESTACIO):
        return False
    selecciona_estacio(num)
    return True


def aplica_clic(estat: dict, vista: pd.DataFrame) -> bool:
    """Selecciona l'estació del marcador que s'acaba de clicar.

    El mapa retorna sempre l'últim marcador clicat, també als reruns que no
    venen de cap clic. Per no tornar a seleccionar-lo després de tancar la
    fitxa, es desa l'empremta del clic ja atès —coordenades i comptador— i
    només es reacciona quan canvia.

    :param estat: estat que retorna `st_folium`.
    :param vista: estacions preparades per `prepara_vista`.
    :return: cert si el clic ha canviat la selecció i cal redibuixar la pàgina.
    """
    clic = estat.get("last_object_clicked")
    if not clic:
        return False

    empremta = (clic["lat"], clic["lng"], estat.get("last_object_clicked_count"))
    if st.session_state.get(CLAU_ULTIM_CLIC) == empremta:
        return False

    st.session_state[CLAU_ULTIM_CLIC] = empremta
    return canvia_seleccio(cerca_estacio_al_punt(vista, clic["lat"], clic["lng"]))


def estacio_seleccionada(vista: pd.DataFrame) -> pd.Series | None:
    """Recupera l'estació seleccionada, sempre que segueixi essent visible.

    Si els filtres l'han deixada fora, la selecció s'oblida: la fitxa no ha de
    sobreviure a l'estació que la va obrir.

    :param vista: estacions preparades per `prepara_vista`.
    :return: fila de l'estació seleccionada, o `None` si no n'hi ha cap.
    """
    num = st.session_state.get(CLAU_ESTACIO)
    if num is None:
        return None

    files = vista[vista["num"] == num]
    if files.empty:
        selecciona_estacio(None)
        return None
    return files.iloc[0]


def nom_estacio(rotul: str, num: int) -> str:
    """Retorna la retolació de l'estació o un nom de recanvi amb el seu número.

    :param rotul: retolació publicada, que pot ser buida.
    :param num: identificador de l'estació a la font.
    :return: nom amb què es presenta l'estació a l'usuari.
    """
    return rotul or f"Estació {num}"


def _crea_etiqueta(estacio) -> str:
    """Crea el text que apareix en passar el ratolí per un marcador.

    :param estacio: fila d'estació obtinguda per iteració de la vista.
    :return: retolació i preu, o la marca de dada absent.
    """
    nom = nom_estacio(estacio.rotul, estacio.num)
    if pd.isna(estacio.preu):
        return f"{nom} · sense dada"
    return f"{nom} · {formata_preu(estacio.preu)}"


def formata_preu(preu: float) -> str:
    """Formata un preu amb tres decimals i coma decimal catalana.

    :param preu: preu en euros per litre o quilogram.
    :return: preu formatat, o un guió si el preu és absent.
    """
    if pd.isna(preu):
        return "—"
    return f"{preu:.3f}".replace(".", ",") + " €"


def mostra_llegenda(vista: pd.DataFrame) -> None:
    """Dibuixa la barra de l'escala de color amb els seus extrems de preu.

    :param vista: estacions preparades per `prepara_vista`.
    """
    preus = vista["preu"].dropna()
    if preus.empty:
        st.info("Cap estació publica aquest carburant.")
        return

    st.markdown(
        f'<div style="height:10px;border-radius:5px;'
        f'background:linear-gradient(90deg,{genera_parades_degradat()})"></div>',
        unsafe_allow_html=True,
    )
    extrems = st.columns(2)
    extrems[0].caption(f"**{formata_preu(preus.min())}** · més barat")
    extrems[1].caption(f"**{formata_preu(preus.max())}** · més car")

    sense_dada = int(vista["preu"].isna().sum())
    if sense_dada:
        st.caption(f"{sense_dada} estacions sense dada es pinten en gris.")


def acoloreix_fila(fila: pd.Series) -> list[str]:
    """Aplica a la fila el mateix color que el marcador de l'estació.

    :param fila: fila de la taula que es mostra a l'usuari.
    :return: estils CSS, un per columna de la fila.
    """
    color = escala.hex_per_posicio(fila["posicio"])
    estils = [""] * len(fila)
    estils[fila.index.get_loc("Preu")] = f"background-color: {color}; color: #0b0b0b"
    return estils


def mostra_taula(vista: pd.DataFrame):
    """Mostra totes les estacions ordenades de la més barata a la més cara.

    La taula té alçada fixa i barra de desplaçament pròpia, així que hi caben
    totes les estacions sense allargar la pàgina.

    :param vista: estacions preparades per `prepara_vista`.
    :return: estat de la taula, amb la cel·la que hagi clicat l'usuari.
    """
    taula = pd.DataFrame(
        {
            # La mateixa posició que duu el marcador: les estacions empatades
            # comparteixen número i la casella queda buida si no hi ha preu.
            "#": vista["classificacio"],
            "Estació": [
                nom_estacio(rotul, num)
                for rotul, num in zip(vista["rotul"], vista["num"])
            ],
            "Localitat": vista["localitat"],
            "Adreça": vista["adreca"],
            "Preu": vista["preu"].map(formata_preu),
            "posicio": vista["posicio"],
        }
    )
    return st.dataframe(
        taula.style.apply(acoloreix_fila, axis=1),
        hide_index=True,
        width="stretch",
        height=ALCADA_PANELL,
        column_config={"posicio": None},
        key=CLAU_TAULA,
        on_select="rerun",
        # Selecció de cel·la i no de fila: qualsevol cel·la que es cliqui
        # identifica igualment la seva estació, i així la taula no guanya la
        # columna de caselles que Streamlit hi afegeix en seleccionar files.
        selection_mode="single-cell",
    )


def aplica_seleccio_taula(seleccio, vista: pd.DataFrame) -> bool:
    """Selecciona l'estació de la cel·la que s'acaba de clicar a la taula.

    La cel·la arriba com a parell (posició de la fila, nom de la columna). La
    posició no depèn de com hagi reordenat la taula l'usuari al navegador.

    :param seleccio: estat que retorna `mostra_taula`.
    :param vista: estacions preparades per `prepara_vista`.
    :return: cert si la cel·la clicada ha canviat la selecció.
    """
    cel·les = seleccio["selection"].get("cells", []) if seleccio else []
    if not cel·les:
        return False

    fila, _ = cel·les[0]
    return canvia_seleccio(int(vista["num"].iloc[fila]))


def color_historic() -> str:
    """Tria el color de la línia de l'històric segons el tema del navegador.

    :return: color hexadecimal amb prou contrast sobre el fons actual.
    """
    tema = getattr(st.context, "theme", None)
    return COLOR_HISTORIC.get(getattr(tema, "type", None) or "light")


def retalla_periode(serie: pd.DataFrame, dies: int | None) -> pd.DataFrame:
    """Retalla la sèrie als darrers dies publicats per l'estació.

    El període es compta des de l'última lectura de l'estació, no des d'avui:
    una estació que ha deixat de publicar ha de seguir mostrant la seva sèrie.

    :param serie: sèrie diària amb la columna `dia`.
    :param dies: nombre de dies a conservar, o `None` per no retallar.
    :return: subconjunt de la sèrie dins del període.
    """
    if dies is None or serie.empty:
        return serie
    limit = serie["dia"].max() - pd.Timedelta(days=dies - 1)
    return serie[serie["dia"] >= limit]


def prepara_serie(historic: pd.DataFrame, carburant: str) -> pd.DataFrame:
    """Extreu de l'històric la sèrie d'un sol carburant, sense forats.

    Els dies en què l'estació no va publicar el carburant no són preu zero i,
    per tant, no formen part de la línia.

    :param historic: històric complet de l'estació.
    :param carburant: codi de la columna de carburant seleccionada.
    :return: taula amb les columnes `dia`, `preu` i `preu_text`.
    """
    serie = historic[["dia", carburant]].rename(columns={carburant: "preu"})
    serie = serie.dropna(subset=["preu"]).reset_index(drop=True)
    serie["preu_text"] = serie["preu"].map(formata_preu)
    return serie


def crea_grafic_historic(serie: pd.DataFrame, etiqueta: str) -> alt.LayerChart:
    """Crea el gràfic de l'evolució del preu d'un carburant.

    L'eix vertical no arrenca a zero: el recorregut dels preus és molt més
    estret que el seu valor absolut i, amb el zero, la línia quedaria plana.
    En passar el ratolí, una línia vertical i un punt marquen el dia més proper
    i en mostren el preu.

    :param serie: sèrie preparada per `prepara_serie`.
    :param etiqueta: nom visible del carburant, que titula l'eix vertical.
    :return: gràfic d'una sola sèrie llest per dibuixar.
    """
    color = color_historic()
    base = alt.Chart(serie).encode(
        x=alt.X("dia:T", title=None, axis=alt.Axis(grid=False, format="%d %b")),
        y=alt.Y(
            "preu:Q",
            title=f"{etiqueta} (€)",
            scale=alt.Scale(zero=False, nice=True),
            axis=alt.Axis(format=".3f"),
        ),
        tooltip=[
            alt.Tooltip("dia:T", title="Dia", format="%d-%m-%Y"),
            alt.Tooltip("preu_text:N", title=etiqueta),
        ],
    )
    proximitat = alt.selection_point(
        nearest=True, on="pointerover", fields=["dia"], empty=False, clear="mouseleave"
    )
    linia = base.mark_line(color=color, strokeWidth=2)
    detectors = base.mark_point(opacity=0, size=120).add_params(proximitat)
    guia = base.mark_rule(color=color, opacity=0.35).transform_filter(proximitat)
    punt = base.mark_point(color=color, filled=True, size=80).transform_filter(
        proximitat
    )
    return alt.layer(guia, linia, detectors, punt).properties(height=ALCADA_GRAFIC)


def mostra_indicadors_historic(serie: pd.DataFrame) -> None:
    """Mostra el preu més recent del període i els seus extrems.

    :param serie: sèrie preparada per `prepara_serie`, amb almenys una fila.
    """
    preus = serie["preu"]
    darrer = float(preus.iloc[-1])
    variacio = darrer - float(preus.iloc[0])

    indicadors = st.columns(3)
    indicadors[0].metric(
        "Darrer preu",
        formata_preu(darrer),
        delta=f"{variacio:+.3f} €".replace(".", ","),
        delta_color="inverse",
        help="Variació respecte del primer dia del període.",
    )
    indicadors[1].metric("Mínim del període", formata_preu(preus.min()))
    indicadors[2].metric("Màxim del període", formata_preu(preus.max()))


def mostra_historic(estacio: pd.Series, carburant: str) -> None:
    """Dibuixa l'evolució del preu del carburant seleccionat a l'estació.

    :param estacio: fila de l'estació seleccionada.
    :param carburant: codi de la columna de carburant seleccionada.
    """
    etiqueta = CARBURANTS[carburant]
    historic = carrega_historic(str(RUTA_BASE_DADES), int(estacio["num"]))
    serie = prepara_serie(historic, carburant)
    if serie.empty:
        st.info(f"Aquesta estació no ha publicat mai el preu de {etiqueta}.")
        return

    periode = st.segmented_control(
        "Període",
        list(PERIODES_HISTORIC),
        default=PERIODE_PER_DEFECTE,
        required=True,
        key=CLAU_PERIODE,
        label_visibility="collapsed",
    )
    retallada = retalla_periode(serie, PERIODES_HISTORIC.get(periode))
    if retallada.empty:
        st.caption("Cap lectura dins d'aquest període.")
        return

    mostra_indicadors_historic(retallada)
    st.altair_chart(crea_grafic_historic(retallada, etiqueta), width="stretch")
    st.caption(
        f"{len(retallada)} lectures diàries, de {retallada['dia'].min():%d-%m-%Y} "
        f"a {retallada['dia'].max():%d-%m-%Y}."
    )


def mostra_preus_publicats(estacio: pd.Series, carburant: str) -> None:
    """Llista tots els carburants que serveix l'estació amb el seu preu.

    :param estacio: fila de l'estació seleccionada.
    :param carburant: codi del carburant seleccionat, que va marcat.
    """
    publicats = {
        etiqueta: estacio[codi]
        for codi, etiqueta in CARBURANTS.items()
        if not pd.isna(estacio[codi])
    }
    if not publicats:
        st.caption("L'estació no publica cap preu.")
        return

    taula = pd.DataFrame(
        {
            "Carburant": list(publicats),
            "Preu": [formata_preu(preu) for preu in publicats.values()],
        }
    )
    seleccionat = taula["Carburant"] == CARBURANTS[carburant]
    taula.loc[seleccionat, "Carburant"] += " ●"
    st.dataframe(taula, hide_index=True, width="stretch")
    if seleccionat.any():
        st.caption("● carburant del mapa.")


def mostra_fitxa(estacio: pd.Series) -> None:
    """Mostra les dades de contacte i situació de l'estació.

    :param estacio: fila de l'estació seleccionada.
    """
    camps = {
        "Adreça": estacio["adreca"],
        "Localitat": estacio["localitat"],
        "Horari": estacio["horari"],
        "Telèfon": estacio["telefon"],
        "Lectura": estacio["data"],
    }
    linies = [f"- **{nom}:** {valor}" for nom, valor in camps.items() if valor]
    st.markdown("\n".join(linies))


def mostra_detall(estacio: pd.Series, carburant: str, nivells: int) -> None:
    """Mostra tot el que se sap de l'estació seleccionada al mapa.

    :param estacio: fila de l'estació seleccionada.
    :param carburant: codi de la columna de carburant seleccionada.
    :param nivells: preus diferents que hi ha entre les estacions visibles, que
        és l'última posició de la classificació.
    """
    accions = st.columns(2)
    accions[0].button(
        "← Torna al llistat",
        on_click=selecciona_estacio,
        args=(None,),
        key="tanca_detall",
        width="stretch",
    )
    accions[1].link_button(
        "Obre a Google Maps",
        url_google_maps(estacio["lat"], estacio["lng"]),
        icon=":material/open_in_new:",
        width="stretch",
    )
    st.subheader(nom_estacio(estacio["rotul"], estacio["num"]))
    if not pd.isna(estacio["classificacio"]):
        st.caption(
            f"Posició {int(estacio['classificacio'])} de {nivells} "
            f"preus diferents de {CARBURANTS[carburant]}."
        )
    mostra_fitxa(estacio)
    st.markdown(f"**Evolució del preu · {CARBURANTS[carburant]}**")
    mostra_historic(estacio, carburant)
    st.markdown("**Preus publicats avui**")
    mostra_preus_publicats(estacio, carburant)


def executa() -> None:
    """Dibuixa la interfície completa de l'aplicació."""
    st.set_page_config(page_title="Estacions de servei", page_icon="⛽", layout="wide")
    st.title("⛽ Estacions de servei")

    dia, estacions = carrega_estacions(str(RUTA_BASE_DADES))
    if estacions.empty:
        st.error("La base de dades no conté cap lectura de preus geolocalitzada.")
        return

    codis = list(CARBURANTS)
    with st.sidebar:
        st.header("Filtres")
        carburant = st.selectbox(
            "Carburant",
            codis,
            index=codis.index(CARBURANT_PER_DEFECTE),
            format_func=lambda codi: CARBURANTS[codi],
        )
        st.markdown("Localitat")
        localitats = sorted(estacions["localitat"].unique())
        seleccionades = selecciona_localitats(localitats)
        interval = selecciona_interval_preus(estacions[carburant], carburant)
        inclou_sense_preu = st.checkbox(
            "Inclou les que no publiquen preu",
            value=True,
            key="inclou_sense_preu",
            help="Aquestes estacions no tenen preu amb què comparar-se amb "
            "l'interval, i es pinten en gris.",
        )

    filtrades = filtra_per_localitat(estacions, seleccionades)
    filtrades = filtra_per_preu(filtrades, carburant, interval, inclou_sense_preu)
    vista = prepara_vista(filtrades, carburant)
    amb_preu = int(vista["preu"].notna().sum())
    # L'última posició de la classificació: hi ha tantes posicions com preus
    # diferents, no com estacions.
    nivells_preu = int(vista["classificacio"].max()) if amb_preu else 0

    indicadors = st.columns(4)
    indicadors[0].metric("Dia de les lectures", dia)
    indicadors[1].metric("Estacions", f"{len(vista)} de {len(estacions)}")
    indicadors[2].metric(f"Amb preu de {CARBURANTS[carburant]}", amb_preu)
    indicadors[3].metric(
        "Preu més barat", formata_preu(vista["preu"].min()) if amb_preu else "—"
    )

    if not seleccionades:
        st.warning(
            "No hi ha cap localitat marcada. Obre el filtre «Localitat» i marca "
            "les localitats que vulguis veure."
        )
        return

    if vista.empty:
        st.warning(
            "Cap estació de les localitats marcades entra dins de l'interval de "
            "preu. Amplia l'interval o marca més localitats."
        )
        return

    estacio = estacio_seleccionada(vista)
    centre, zoom = enquadra_estacio(estacio)
    mapa, llistat = st.columns([3, 2], gap="medium")
    with mapa:
        st.subheader("Mapa")
        mostra_llegenda(vista)
        estat = st_folium(
            construeix_mapa(vista),
            key=CLAU_MAPA,
            height=ALCADA_PANELL,
            width=None,
            # L'anell de la selecció va en una capa a part: així el mapa no es
            # refà en canviar d'estació i es conserva la vista de l'usuari.
            feature_group_to_add=crea_ressaltat(estacio),
            # Obrir una fitxa acosta el mapa a la seva estació; sense fitxa
            # oberta no s'hi toca.
            center=centre,
            zoom=zoom,
            returned_objects=["last_object_clicked", "last_object_clicked_count"],
        )
        # Es torna a dibuixar la pàgina perquè el mapa rebi l'anell de la nova
        # selecció, que s'ha resolt just després d'enviar-li la capa.
        if aplica_clic(estat, vista):
            st.rerun()
        st.caption("Clica un marcador per veure el detall de l'estació.")

    with llistat:
        if estacio is not None:
            mostra_detall(estacio, carburant, nivells_preu)
            return
        st.subheader("Totes les estacions")
        st.caption(
            f"{CARBURANTS[carburant]}, de més barat a més car. Clica una fila "
            "per veure'n el detall."
        )
        # Es torna a dibuixar la pàgina perquè el detall substitueixi la taula
        # i el mapa rebi l'anell de la nova selecció.
        if aplica_seleccio_taula(mostra_taula(vista), vista):
            st.rerun()


if __name__ == "__main__":
    executa()
