"""Proves d'integració de la lògica de l'aplicació sobre la base de dades."""

import re
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import aplicacio
from configuracio import CARBURANT_PER_DEFECTE, DIRECTORI_BASE, RUTA_BASE_DADES

from conftest import DIA_MES_RECENT

_RUTA_APLICACIO = str(DIRECTORI_BASE / "aplicacio.py")


def caselles_localitat(prova):
    """Selecciona només les caselles de localitat de la barra lateral.

    La barra lateral també conté la casella d'incloure les estacions sense preu,
    que no forma part del filtre de localitats.

    :param prova: aplicació executada amb AppTest.
    :return: caselles la clau de les quals porta el prefix de localitat.
    """
    return [
        casella
        for casella in prova.sidebar.checkbox
        if casella.key.startswith(aplicacio.PREFIX_LOCALITAT)
    ]


@pytest.fixture(scope="module")
def aplicacio_executada():
    """Executa l'aplicació Streamlit sencera sobre la base de dades real.

    :return: resultat de l'execució, amb els components ja renderitzats.
    :raises pytest.skip: si la base de dades real no és present.
    """
    if not RUTA_BASE_DADES.is_file():
        pytest.skip(f"Cal {RUTA_BASE_DADES.name} per a la prova d'integració")
    return AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()


def carregaEstacions_baseDadesValida_retornaDiaITaula(ruta_base_dades):
    """El carregador cachejat ha de retornar el dia i les estacions."""
    aplicacio.carrega_estacions.clear()
    dia, estacions = aplicacio.carrega_estacions(str(ruta_base_dades))

    assert dia == DIA_MES_RECENT
    assert len(estacions) == 3


def preparaVista_carburantSeleccionat_ordenaDeMesBaratAMesCar(estacions):
    """El llistat ha d'anar de l'estació més barata a la més cara."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)

    preus = vista["preu"].dropna()
    assert list(preus) == sorted(preus)
    assert preus.iloc[0] == 1.45


def preparaVista_estacioSensePreu_laColocaAlFinal(estacions):
    """Una estació sense preu no ha de barrejar-se amb els preus reals."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)

    assert pd.isna(vista["preu"].iloc[-1])
    assert vista["num"].iloc[-1] == 4


def preparaVista_carburantSeleccionat_assignaVerdIVermellAlsExtrems(estacions):
    """Els extrems de l'escala han de recaure en la més barata i la més cara."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)
    amb_preu = vista[vista["preu"].notna()]

    assert amb_preu["color"].iloc[0] == "#00ff00"
    assert amb_preu["color"].iloc[-1] == "#ff0000"


def preparaVista_estacioSensePreu_liAssignaElGris(estacions):
    """Sense preu, el marcador ha de sortir gris i no dins de l'escala."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)
    sense_preu = vista[vista["preu"].isna()].iloc[0]

    assert sense_preu["color"] == "#898781"


def filtraPerLocalitat_unaLocalitatMarcada_descartaLaResta(estacions):
    """El filtre de localitat ha de descartar les localitats no marcades."""
    filtrades = aplicacio.filtra_per_localitat(estacions, ["INCA"])

    assert list(filtrades["num"]) == [2]


def filtraPerLocalitat_variesLocalitatsMarcades_lesRetornaTotes(estacions):
    """Amb diverses localitats marcades han de passar totes les seves estacions."""
    filtrades = aplicacio.filtra_per_localitat(estacions, ["INCA", "PALMA"])

    assert set(filtrades["num"]) == {1, 2}


def filtraPerLocalitat_totesLesLocalitatsMarcades_noDescartaCapEstacio(estacions):
    """Amb totes les caselles marcades no s'ha de perdre cap estació."""
    totes = sorted(estacions["localitat"].unique())

    filtrades = aplicacio.filtra_per_localitat(estacions, totes)

    assert len(filtrades) == len(estacions)


def filtraPerLocalitat_capLocalitatMarcada_retornaTaulaBuida(estacions):
    """Desmarcar-les totes ha de buidar el resultat, no mostrar-ho tot."""
    filtrades = aplicacio.filtra_per_localitat(estacions, [])

    assert filtrades.empty


def clauLocalitat_nomDeLocalitat_afegeixElPrefixDeSessio():
    """Les claus de sessió de les caselles han d'anar amb el prefix reservat."""
    assert aplicacio.clau_localitat("INCA") == f"{aplicacio.PREFIX_LOCALITAT}INCA"


def filtraPerPreu_intervalEstret_descartaElsPreusDeFora(estacions):
    """L'interval de preu ha de deixar fora les estacions més cares i barates."""
    filtrades = aplicacio.filtra_per_preu(
        estacions, CARBURANT_PER_DEFECTE, (1.50, 1.60), inclou_sense_preu=False
    )

    assert list(filtrades["num"]) == [1]


def filtraPerPreu_intervalComplet_mantéTotesLesQueTenenPreu(estacions):
    """Amb l'interval sencer no s'ha de perdre cap estació amb preu."""
    filtrades = aplicacio.filtra_per_preu(
        estacions, CARBURANT_PER_DEFECTE, (1.45, 1.55), inclou_sense_preu=False
    )

    assert set(filtrades["num"]) == {1, 2}


def filtraPerPreu_extremsExactes_elsIncloustotsDos(estacions):
    """Els extrems de l'interval han de ser inclusius tot i la coma flotant."""
    filtrades = aplicacio.filtra_per_preu(
        estacions, CARBURANT_PER_DEFECTE, (1.45, 1.45), inclou_sense_preu=False
    )

    assert list(filtrades["num"]) == [2]


def filtraPerPreu_inclouSensePreu_mantéLesEstacionsSenseDada(estacions):
    """Les estacions sense preu no es poden comparar amb l'interval."""
    filtrades = aplicacio.filtra_per_preu(
        estacions, CARBURANT_PER_DEFECTE, (1.50, 1.60), inclou_sense_preu=True
    )

    assert set(filtrades["num"]) == {1, 4}


def filtraPerPreu_senseIntervalIExclouSensePreu_nomesDeixaLesQueTenenPreu(estacions):
    """Sense interval, la casella encara ha de poder amagar les estacions grises."""
    filtrades = aplicacio.filtra_per_preu(
        estacions, CARBURANT_PER_DEFECTE, None, inclou_sense_preu=False
    )

    assert set(filtrades["num"]) == {1, 2}


def filtraPerPreu_senseIntervalIInclouSensePreu_noDescartaRes(estacions):
    """Sense interval ni exclusions, el filtre de preu ha de ser transparent."""
    filtrades = aplicacio.filtra_per_preu(
        estacions, CARBURANT_PER_DEFECTE, None, inclou_sense_preu=True
    )

    assert len(filtrades) == len(estacions)


def cssBarraLliscant() -> str:
    """Renderitza el CSS de la barra del control per poder-lo inspeccionar.

    :return: contingut del bloc <style> que injecta `pinta_barra_lliscant`.
    """
    prova = AppTest.from_string(
        "import aplicacio\n"
        "import streamlit as st\n"
        f"with st.container(key='{aplicacio.CLAU_FILTRE_PREU}'):\n"
        "    aplicacio.pinta_barra_lliscant()\n",
        default_timeout=60,
    ).run()
    return prova.markdown[0].value


def pintaBarraLliscant_escalaCompleta_generaElDegradatAcotat():
    """El CSS de la barra ha d'anar acotat a la classe del contenidor."""
    css = cssBarraLliscant()

    assert f".st-key-{aplicacio.CLAU_FILTRE_PREU}" in css
    assert "#00ff00 0%" in css
    assert "#ff0000 100%" in css


def pintaBarraLliscant_selectors_usaElsTestidPublicsDelControl():
    """Els selectors s'han d'ancorar als data-testid, no a classes d'Emotion."""
    css = cssBarraLliscant()

    assert '[data-testid="stSlider"]' in css
    assert '[data-testid="stSliderTickBar"]' in css
    assert '[data-testid="stSliderThumbValue"]' in css
    assert not re.search(r"efbyxod\d", css), "no s'han de fixar classes d'Emotion"


def pintaBarraLliscant_cssInjectat_noPortaLiniesIndentades():
    """Markdown convertiria en bloc de codi una línia sagnada: el CSS moriria."""
    css = cssBarraLliscant()

    indentades = [linia for linia in css.splitlines() if linia.startswith("    ")]
    assert indentades == []
    assert css.startswith("<style>")
    assert css.rstrip().endswith("</style>")


def pintaBarraLliscant_selectors_noUsaSelectorsInexistents():
    """Streamlit 1.63 no renderitza BaseWeb ni role=slider: seria CSS mort."""
    css = cssBarraLliscant()

    assert "data-baseweb" not in css
    assert 'role="slider"' not in css


def pintaBarraLliscant_estructuraDelControl_coincideixAmbElDomDeStreamlit():
    """Comprova contra el paquet instal·lat que els testid del CSS existeixen.

    Si una versió nova de Streamlit els reanomena, el degradat deixaria de
    aplicar-se sense cap error visible: aquesta prova ho detecta abans.
    """
    arrel = Path(st.__file__).parent / "static" / "static" / "js"
    fonts = "\n".join(
        fitxer.read_text(encoding="utf-8", errors="replace")
        for fitxer in arrel.glob("Slider.*.js")
    )

    assert fonts, "no s'ha trobat el mòdul del control lliscant de Streamlit"
    for testid in ("stSlider", "stSliderTickBar", "stSliderThumbValue"):
        assert testid in fonts, f"Streamlit ja no renderitza {testid}"


def marcadorsDelMapa(mapa) -> list:
    """Recull els marcadors d'estació que s'han afegit al mapa.

    :param mapa: mapa construït per `construeix_mapa`.
    :return: marcadors, en l'ordre en què s'han afegit.
    """
    return [
        fill for fill in mapa._children.values() if fill.__class__.__name__ == "Marker"
    ]


def htmlDelMarcador(marcador) -> str:
    """Extreu l'HTML del cercle que dibuixa un marcador.

    :param marcador: marcador obtingut de `marcadorsDelMapa`.
    :return: contingut HTML de la seva icona.
    """
    icona = next(iter(marcador._children.values()))
    return icona.options["html"]


def construeixMapa_estacionsAmbPreu_afegeixUnMarcadorPerEstacio(estacions):
    """Cada estació geolocalitzada ha de tenir el seu marcador al mapa."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)

    mapa = aplicacio.construeix_mapa(vista)

    assert len(marcadorsDelMapa(mapa)) == len(vista)


def construeixMapa_vistaBuida_retornaMapaSenseMarcadors(estacions):
    """Un filtre sense resultats no ha de trencar la construcció del mapa."""
    buida = aplicacio.prepara_vista(estacions.iloc[0:0], CARBURANT_PER_DEFECTE)

    mapa = aplicacio.construeix_mapa(buida)

    assert marcadorsDelMapa(mapa) == []


def construeixMapa_estacionsAmbPreu_escriuLaPosicioDinsDelMarcador(estacions):
    """El marcador ha de dur escrita la posició de l'estació a la classificació."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)

    mapa = aplicacio.construeix_mapa(vista)

    marcadors = marcadorsDelMapa(mapa)
    assert htmlDelMarcador(marcadors[0]).endswith(">1</div>")
    assert htmlDelMarcador(marcadors[1]).endswith(">2</div>")


def construeixMapa_estacioSensePreu_noLiEscriuCapPosicio(estacions):
    """Sense preu no hi ha posició: el cercle gris va buit."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)

    mapa = aplicacio.construeix_mapa(vista)

    sense_preu = marcadorsDelMapa(mapa)[-1]
    assert htmlDelMarcador(sense_preu).endswith("></div>")
    assert f"{aplicacio.MIDA_MARCADOR_SENSE_PREU}px" in htmlDelMarcador(sense_preu)


def calculaClassificacio_preusDiferents_numeraDeLaMesBarataALaMesCara():
    """La posició 1 ha de ser la de l'estació més barata."""
    preus = pd.Series([1.60, 1.45, 1.50])

    assert list(aplicacio.calcula_classificacio(preus)) == [3, 1, 2]


def calculaClassificacio_preusEmpatats_compartenPosicioSenseSaltarLaSeguent():
    """Els empats no han de buidar posicions: després del 2 empatat ve el 3."""
    preus = pd.Series([1.45, 1.50, 1.50, 1.50, 1.60])

    assert list(aplicacio.calcula_classificacio(preus)) == [1, 2, 2, 2, 3]


def calculaClassificacio_estacioSensePreu_deixaLaPosicioBuida():
    """Qui no publica el carburant no entra a la classificació."""
    classificacio = aplicacio.calcula_classificacio(pd.Series([1.45, float("nan")]))

    assert classificacio[0] == 1
    assert pd.isna(classificacio[1])


def preparaVista_estacionsFiltrades_classificaNomesLesVisibles(estacions):
    """La classificació és la del conjunt visible, com el color de l'escala."""
    vista = aplicacio.prepara_vista(estacions[estacions["num"] == 1], CARBURANT_PER_DEFECTE)

    assert list(vista["classificacio"].dropna()) == [1]


def formataPreu_preuValid_usaComaDecimalIEuros():
    """Els preus s'han de mostrar amb tres decimals i coma decimal catalana."""
    assert aplicacio.formata_preu(1.799) == "1,799 €"


def formataPreu_preuAbsent_retornaGuio():
    """Un preu absent no s'ha de mostrar com a zero."""
    assert aplicacio.formata_preu(float("nan")) == "—"


def executa_aplicacioSencera_noLlancaCapExcepcio(aplicacio_executada):
    """L'aplicació sencera s'ha de renderitzar sense errors sobre la BD real."""
    assert list(aplicacio_executada.exception) == []


def executa_aplicacioSencera_mostraIndicadorsIFiltres(aplicacio_executada):
    """La interfície ha de portar els quatre indicadors i els dos filtres."""
    assert len(aplicacio_executada.metric) == 4
    etiquetes = [filtre.label for filtre in aplicacio_executada.sidebar.selectbox]
    assert etiquetes == ["Carburant"]
    assert len(caselles_localitat(aplicacio_executada)) > 1


def executa_aplicacioSencera_mostraTotesLesEstacionsOrdenades(aplicacio_executada):
    """La taula ha de portar totes les estacions, de més barata a més cara."""
    taula = aplicacio_executada.dataframe[0].value
    posicions = taula["posicio"].dropna()

    assert len(taula) > 0
    assert list(posicions) == sorted(posicions)
    assert posicions.iloc[0] == 0.0
    assert posicions.iloc[-1] == 1.0


def executa_canviDeCarburant_recalculaLEscalaSenseErrors(aplicacio_executada):
    """Canviar de carburant ha de refer l'escala sobre el nou conjunt de preus."""
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()
    prova.sidebar.selectbox[0].set_value("gas_licuado_petroleo").run()

    assert list(prova.exception) == []
    assert prova.metric[2].label == "Amb preu de GLP"


def executa_primeraCarrega_marcaTotesLesLocalitats(aplicacio_executada):
    """Per defecte totes les caselles de localitat han de sortir marcades."""
    caselles = caselles_localitat(aplicacio_executada)

    assert len(caselles) > 1
    assert all(casella.value for casella in caselles)


def executa_primeraCarrega_mostraElsBotonsDeMarcarIDesmarcar(aplicacio_executada):
    """El desplegable ha de portar els dos botons de selecció massiva."""
    etiquetes = [boto.label for boto in aplicacio_executada.sidebar.button]

    assert etiquetes == ["Marca-les totes", "Desmarca-les totes"]


def executa_botoDesmarcarLesTotes_deixaTotesLesCasellesSenseMarcar():
    """El botó de desmarcar ha de buidar la selecció d'un sol clic."""
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()

    prova.sidebar.button[1].click().run()

    assert list(prova.exception) == []
    assert not any(casella.value for casella in caselles_localitat(prova))
    assert prova.metric[1].value.startswith("0 de ")
    assert len(prova.warning) == 1


def executa_botoMarcarLesTotes_recuperaTotesLesEstacions():
    """Després de desmarcar-les, el botó de marcar ho ha de restituir tot."""
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()
    total = prova.metric[1].value

    prova.sidebar.button[1].click().run()
    prova.sidebar.button[0].click().run()

    assert list(prova.exception) == []
    assert all(casella.value for casella in caselles_localitat(prova))
    assert prova.metric[1].value == total
    assert list(prova.warning) == []


def executa_primeraCarrega_mostraElControlLliscantAlRangComplet(aplicacio_executada):
    """El control de preu ha d'arrencar cobrint tot el recorregut de preus."""
    control = aplicacio_executada.sidebar.slider[0]

    assert control.label == "Interval de preu"
    assert control.value == (control.min, control.max)


def executa_estretaElRangDePreus_nomesDeixaLesEstacionsDeDins():
    """Moure el control de preu ha de reduir les estacions visibles."""
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()
    prova.sidebar.checkbox(key='inclou_sense_preu').set_value(False).run()
    files_inicials = len(prova.dataframe[0].value)
    control = prova.sidebar.slider[0]
    minim, maxim = control.min, control.max
    tall = round(minim + (maxim - minim) / 4, 3)

    prova.sidebar.slider[0].set_range(minim, tall).run()

    assert list(prova.exception) == []
    taula = prova.dataframe[0].value
    assert 0 < len(taula) < files_inicials
    preus = [float(preu.replace(" €", "").replace(",", ".")) for preu in taula["Preu"]]
    assert max(preus) <= tall


def executa_rangDePreusSenseCoincidencies_avisaEnComptesDeFallar():
    """Un interval que no encaixa amb cap estació ha d'avisar, no petar."""
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()
    prova.sidebar.checkbox(key='inclou_sense_preu').set_value(False).run()
    prova.sidebar.button[1].click().run()

    assert list(prova.exception) == []
    assert len(prova.warning) == 1


def executa_desmarcaUnaLocalitat_reduexElNombreDEstacions():
    """Desmarcar una localitat concreta n'ha de treure les seves estacions."""
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()
    visibles_inicials = len(prova.dataframe[0].value)

    caselles_localitat(prova)[0].set_value(False).run()

    assert list(prova.exception) == []
    assert len(prova.dataframe[0].value) < visibles_inicials
    assert not caselles_localitat(prova)[0].value


_GUIO_SELECCIO = """
import pandas as pd
import streamlit as st

import aplicacio

VISTA = pd.DataFrame({"num": [1, 2], "lat": [39.60, 39.71], "lng": [2.65, 2.90]})
CLIC = {
    "last_object_clicked": {"lat": 39.71, "lng": 2.90},
    "last_object_clicked_count": 1,
}
"""


def executaGuioSeleccio(cos: str):
    """Executa un guió que exercita la selecció d'estació amb sessió activa.

    Les funcions de selecció escriuen a `st.session_state`, que només funciona
    dins d'una execució de Streamlit.

    :param cos: línies del guió que van després de la preparació comuna.
    :return: aplicació executada, amb els `st.text` ja renderitzats.
    """
    prova = AppTest.from_string(_GUIO_SELECCIO + cos, default_timeout=60).run()
    assert list(prova.exception) == []
    return prova


def cercaEstacioAlPunt_coordenadesDunMarcador_retornaLaSevaEstacio():
    """El clic torna les coordenades del marcador, no l'estació que representa."""
    vista = pd.DataFrame({"num": [1, 2], "lat": [39.60, 39.71], "lng": [2.65, 2.90]})

    assert aplicacio.cerca_estacio_al_punt(vista, 39.71, 2.90) == 2


def cercaEstacioAlPunt_puntSenseMarcador_retornaNone():
    """Un punt del mapa que no és cap marcador no ha de seleccionar res."""
    vista = pd.DataFrame({"num": [1, 2], "lat": [39.60, 39.71], "lng": [2.65, 2.90]})

    assert aplicacio.cerca_estacio_al_punt(vista, 40.0, 3.5) is None


def cercaEstacioAlPunt_vistaBuida_retornaNone():
    """Sense estacions visibles no hi ha res a seleccionar."""
    buida = pd.DataFrame({"num": [], "lat": [], "lng": []})

    assert aplicacio.cerca_estacio_al_punt(buida, 39.71, 2.90) is None


def aplicaClic_marcadorNou_seleccionaLaSevaEstacio():
    """Clicar un marcador ha d'obrir la fitxa de la seva estació."""
    prova = executaGuioSeleccio(
        "st.text(repr(aplicacio.aplica_clic(CLIC, VISTA)))\n"
        "st.text(repr(st.session_state.get(aplicacio.CLAU_ESTACIO)))\n"
    )

    assert [text.value for text in prova.text] == ["True", "2"]


def aplicaClic_mateixClicDosCops_noTornaASeleccionar():
    """El mapa repeteix l'últim clic a cada rerun: només compta el primer cop."""
    prova = executaGuioSeleccio(
        "aplicacio.aplica_clic(CLIC, VISTA)\n"
        "aplicacio.selecciona_estacio(None)\n"
        "st.text(repr(aplicacio.aplica_clic(CLIC, VISTA)))\n"
        "st.text(repr(st.session_state.get(aplicacio.CLAU_ESTACIO)))\n"
    )

    assert [text.value for text in prova.text] == ["False", "None"]


def aplicaClic_capMarcadorClicat_noSeleccionaRes():
    """Abans del primer clic el mapa no retorna cap marcador."""
    prova = executaGuioSeleccio(
        "st.text(repr(aplicacio.aplica_clic({}, VISTA)))\n"
        "st.text(repr(st.session_state.get(aplicacio.CLAU_ESTACIO)))\n"
    )

    assert [text.value for text in prova.text] == ["False", "None"]


def estacioSeleccionada_estacioVisible_retornaLaSevaFila():
    """Amb una estació seleccionada, la fitxa ha de rebre les seves dades."""
    prova = executaGuioSeleccio(
        "aplicacio.selecciona_estacio(2)\n"
        "st.text(repr(int(aplicacio.estacio_seleccionada(VISTA)['num'])))\n"
    )

    assert [text.value for text in prova.text] == ["2"]


def estacioSeleccionada_estacioFiltradaFora_oblidaLaSeleccio():
    """La fitxa no pot sobreviure als filtres que amaguen la seva estació."""
    prova = executaGuioSeleccio(
        "aplicacio.selecciona_estacio(2)\n"
        "st.text(repr(aplicacio.estacio_seleccionada(VISTA[VISTA['num'] == 1])))\n"
        "st.text(repr(st.session_state.get(aplicacio.CLAU_ESTACIO)))\n"
    )

    assert [text.value for text in prova.text] == ["None", "None"]


def creaRessaltat_estacioSeleccionada_afegeixLAnellDeSeleccio(estacions):
    """L'estació oberta s'ha de distingir de la resta sobre el mapa."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)

    capa = aplicacio.crea_ressaltat(vista.iloc[0])

    assert len(capa._children) == 1


def creaRessaltat_senseSeleccio_retornaCapaBuida():
    """Sense estació oberta el mapa no ha de portar cap anell."""
    assert aplicacio.crea_ressaltat(None)._children == {}


def preparaSerie_diesSensePreu_elsDeixaForaDeLaLinia():
    """Un dia sense preu publicat no és preu zero i no forma part de la línia."""
    historic = pd.DataFrame(
        {
            "dia": pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03"]),
            CARBURANT_PER_DEFECTE: [1.50, float("nan"), 1.55],
        }
    )

    serie = aplicacio.prepara_serie(historic, CARBURANT_PER_DEFECTE)

    assert list(serie["preu"]) == [1.50, 1.55]
    assert list(serie["preu_text"]) == ["1,500 €", "1,550 €"]


def retallaPeriode_periodeDeTrentaDies_nomesDeixaElsDarrersDies():
    """El període es compta des de l'última lectura publicada per l'estació."""
    serie = pd.DataFrame({"dia": pd.date_range("2026-01-01", periods=100, freq="D")})

    retallada = aplicacio.retalla_periode(serie, 30)

    assert len(retallada) == 30
    assert retallada["dia"].max() == serie["dia"].max()


def retallaPeriode_senseLimit_retornaLaSerieSencera():
    """L'opció «Tot» no ha de retallar res."""
    serie = pd.DataFrame({"dia": pd.date_range("2026-01-01", periods=100, freq="D")})

    assert len(aplicacio.retalla_periode(serie, None)) == 100


def creaGraficHistoric_serieValida_noArrencaLEixAZero():
    """Amb el zero a l'eix, el recorregut real dels preus quedaria pla."""
    serie = pd.DataFrame(
        {
            "dia": pd.to_datetime(["2026-09-01", "2026-09-02"]),
            "preu": [1.50, 1.55],
            "preu_text": ["1,500 €", "1,550 €"],
        }
    )

    especificacio = aplicacio.crea_grafic_historic(serie, "Gasolina 95").to_dict()

    linia = especificacio["layer"][1]
    assert linia["mark"]["type"] == "line"
    assert linia["encoding"]["y"]["scale"]["zero"] is False


def aplicacioAmbFitxaOberta():
    """Executa l'aplicació amb la fitxa d'una estació ja oberta.

    S'obre la primera estació que publica el carburant per defecte, que és
    l'única que té classificació, històric i indicadors a la fitxa.

    :return: parell (aplicació executada, fila de l'estació oberta).
    :raises pytest.skip: si la base de dades real no és present.
    """
    if not RUTA_BASE_DADES.is_file():
        pytest.skip(f"Cal {RUTA_BASE_DADES.name} per a la prova d'integració")
    aplicacio.carrega_estacions.clear()
    _, totes = aplicacio.carrega_estacions(str(RUTA_BASE_DADES))
    estacio = totes[totes[CARBURANT_PER_DEFECTE].notna()].iloc[0]
    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120)
    prova.session_state[aplicacio.CLAU_ESTACIO] = int(estacio["num"])
    return prova.run(), estacio


def executa_estacioSeleccionada_canviaElLlistatPerLaFitxa():
    """Seleccionar una estació ha de substituir el llistat per la seva fitxa."""
    prova, _ = aplicacioAmbFitxaOberta()

    assert list(prova.exception) == []
    assert "← Torna al llistat" in [boto.label for boto in prova.button]
    assert list(prova.dataframe[0].value.columns) == ["Carburant", "Preu"]


def executa_estacioSeleccionada_afegeixElsIndicadorsDeLHistoric():
    """La fitxa ha de portar el darrer preu i els extrems del període."""
    prova, _ = aplicacioAmbFitxaOberta()

    etiquetes = [indicador.label for indicador in prova.metric]
    assert etiquetes[-3:] == ["Darrer preu", "Mínim del període", "Màxim del període"]


def executa_botoDeTornar_recuperaElLlistatComplet():
    """Tancar la fitxa ha de tornar a mostrar totes les estacions."""
    prova, _ = aplicacioAmbFitxaOberta()

    prova.button(key="tanca_detall").click().run()

    assert list(prova.exception) == []
    assert prova.session_state[aplicacio.CLAU_ESTACIO] is None
    assert "Preu" in prova.dataframe[0].value.columns


def executa_aplicacioSencera_numeraLaTaulaComLaClassificacio(aplicacio_executada):
    """La columna «#» ha de dur la mateixa posició que escriu el marcador."""
    taula = aplicacio_executada.dataframe[0].value
    files = list(zip(taula["#"], taula["Preu"]))

    assert files[0][0] == 1
    for (posicio, preu), (seguent, preu_seguent) in zip(files, files[1:]):
        if pd.isna(seguent):
            continue
        assert (posicio == seguent) == (preu == preu_seguent)


def executa_aplicacioSencera_deixaSensePosicioLesQueNoPubliquenPreu(
    aplicacio_executada,
):
    """Les estacions sense preu van al final i sense número de classificació."""
    taula = aplicacio_executada.dataframe[0].value
    sense_preu = taula[taula["Preu"] == "—"]

    assert sense_preu["#"].isna().all()


def executa_aplicacioSencera_noSaltaCapPosicioDeLaClassificacio(aplicacio_executada):
    """Les posicions han d'anar d'una en una, encara que hi hagi empats."""
    posicions = aplicacio_executada.dataframe[0].value["#"].dropna()

    assert list(posicions) == sorted(posicions)
    assert posicions.min() == 1
    assert set(posicions) == set(range(1, int(posicions.max()) + 1))


def aplicaSeleccioTaula_celulaClicada_seleccionaLEstacioDeLaFila():
    """Clicar qualsevol cel·la ha d'obrir la fitxa de l'estació de la fila."""
    prova = executaGuioSeleccio(
        "seleccio = {'selection': {'cells': [(1, 'Preu')]}}\n"
        "st.text(repr(aplicacio.aplica_seleccio_taula(seleccio, VISTA)))\n"
        "st.text(repr(st.session_state.get(aplicacio.CLAU_ESTACIO)))\n"
    )

    assert [text.value for text in prova.text] == ["True", "2"]


def aplicaSeleccioTaula_capCelulaClicada_noSeleccionaRes():
    """Sense cap cel·la clicada, la taula no ha de canviar la vista."""
    prova = executaGuioSeleccio(
        "seleccio = {'selection': {'cells': []}}\n"
        "st.text(repr(aplicacio.aplica_seleccio_taula(seleccio, VISTA)))\n"
        "st.text(repr(st.session_state.get(aplicacio.CLAU_ESTACIO)))\n"
    )

    assert [text.value for text in prova.text] == ["False", "None"]


def aplicaSeleccioTaula_filaJaOberta_noTornaADibuixarLaPagina():
    """Si la fila clicada ja és la de la fitxa oberta, no cal refer res."""
    prova = executaGuioSeleccio(
        "aplicacio.selecciona_estacio(2)\n"
        "seleccio = {'selection': {'cells': [(1, 'Estació')]}}\n"
        "st.text(repr(aplicacio.aplica_seleccio_taula(seleccio, VISTA)))\n"
    )

    assert [text.value for text in prova.text] == ["False"]


def executa_aplicacioSencera_mostraTotesLesEstacionsSenseRetallarLaTaula():
    """La taula ha de portar una fila per cada estació visible al mapa."""
    if not RUTA_BASE_DADES.is_file():
        pytest.skip(f"Cal {RUTA_BASE_DADES.name} per a la prova d'integració")
    aplicacio.carrega_estacions.clear()
    _, totes = aplicacio.carrega_estacions(str(RUTA_BASE_DADES))

    prova = AppTest.from_file(_RUTA_APLICACIO, default_timeout=120).run()

    assert list(prova.exception) == []
    assert len(prova.dataframe[0].value) == len(totes)


def enquadraEstacio_estacioSeleccionada_centraElMapaSobreSeu(estacions):
    """Obrir una fitxa ha d'acostar el mapa a la seva estació."""
    vista = aplicacio.prepara_vista(estacions, CARBURANT_PER_DEFECTE)
    seleccionada = vista.iloc[0]

    centre, zoom = aplicacio.enquadra_estacio(seleccionada)

    assert centre == (seleccionada["lat"], seleccionada["lng"])
    assert zoom == aplicacio.ZOOM_DETALL


def enquadraEstacio_senseSeleccio_deixaElMapaComEstava():
    """Sense fitxa oberta, el mapa ha de mantenir la vista de l'usuari."""
    assert aplicacio.enquadra_estacio(None) == (None, None)


def urlGoogleMaps_coordenadesValides_apuntaAlPuntDeLEstacio():
    """L'enllaç ha de dur Google Maps a les coordenades de l'estació."""
    url = aplicacio.url_google_maps(39.6053, 2.65847)

    assert url.startswith(aplicacio.BASE_GOOGLE_MAPS)
    assert "query=39.605300%2C2.658470" in url


def urlGoogleMaps_coordenadesForaDeRang_llancaValueError():
    """Una coordenada impossible no pot arribar a l'enllaç."""
    with pytest.raises(ValueError):
        aplicacio.url_google_maps(91.0, 2.65)


def urlGoogleMaps_coordenadesNoNumeriques_llancaValueError():
    """El que s'insereix a l'URL s'ha de validar abans de construir-lo."""
    with pytest.raises(ValueError):
        aplicacio.url_google_maps("39.6; DROP", 2.65)


def executa_estacioSeleccionada_ofereixLEnllacAGoogleMaps():
    """La fitxa ha de portar el botó que obre l'estació a Google Maps."""
    prova, estacio = aplicacioAmbFitxaOberta()

    enllacos = prova.get("link_button")
    assert [enllac.proto.label for enllac in enllacos] == ["Obre a Google Maps"]
    assert enllacos[0].proto.url == aplicacio.url_google_maps(
        estacio["lat"], estacio["lng"]
    )


def carregaEstacions_qualsevolConsulta_caducaAlCapDUnaHora():
    """Les dades cachejades no poden quedar-se fixades tota la vida del servidor."""
    assert aplicacio.carrega_estacions._info.ttl == 3600


def carregaHistoric_qualsevolConsulta_caducaAlMateixRitmeQueLesEstacions():
    """La fitxa i el mapa no poden mostrar lectures de dies diferents."""
    assert aplicacio.carrega_historic._info.ttl == aplicacio.carrega_estacions._info.ttl
