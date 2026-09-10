# Mapa d'estacions de servei

Aplicació **Streamlit** que llegeix `data.db` (SQLite, taula `prices`) i situa
sobre un mapa Folium un marcador per cada estació geolocalitzada, acolorit segons
el preu del carburant seleccionat.

Tot el codi és Python: no hi ha plantilles HTML, ni CSS, ni JavaScript.

## Execució

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run aplicacio.py
```

S'obre al navegador (per defecte <http://localhost:8501>). Per emprar una altra
base de dades:

```powershell
$env:RUTA_BASE_DADES = "C:\ruta\a\altra.db"
```

## Proves

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Les proves d'integració executen l'aplicació sencera amb `AppTest` de Streamlit
sobre `data.db`, sense navegador.

## Estructura

| Fitxer | Responsabilitat |
|---|---|
| `aplicacio.py` | Interfície Streamlit: filtres, indicadors, mapa i taula. |
| `repositori.py` | Accés SQLite de només lectura: lectures del dia i històric. |
| `escala.py` | Escala de color verd → vermell i posicions relatives de preu. |
| `configuracio.py` | Ruta de la BD, centre del mapa i catàleg de carburants. |
| `tests/` | Proves unitàries i d'integració (`*_it.py`). |

## Decisions

- La columna `fecha` es guarda com a `DD-MM-YYYY HH:MM`, que **no** és ordenable
  com a text: la consulta la reconstrueix a `YYYYMMDD` / `YYYYMMDDHH:MM`.
- Només es consideren les lectures del **dia més recent** de la font. Una estació
  que ha deixat de publicar preus no apareix amb dades caducades. Si aquell dia hi
  hagués més d'un snapshot, un `ROW_NUMBER() OVER (PARTITION BY num)` es queda amb
  l'hora més tardana de cada estació.
- Un preu `0,0` o `NULL` significa «carburant no servit», no preu zero: arriba com
  a `NaN` i l'estació es pinta de gris.
- La connexió s'obre amb `mode=ro` (URI SQLite): l'aplicació no pot escriure.
- La lectura de la BD va dins `@st.cache_data`, així que els filtres no tornen a
  consultar SQLite. La memòria cau caduca al cap d'una hora (`DURADA_CACHE`): per
  defecte `st.cache_data` no caduca mai i les dades quedarien fixades a la
  primera consulta durant tota la vida del servidor, de manera que un `data.db`
  reescrit no arribaria mai a l'aplicació. Les dues consultes —estacions i
  històric— comparteixen durada perquè el mapa i la fitxa no acabin mostrant
  lectures de dies diferents. Per veure els canvis a l'instant, «Clear cache» al
  menú de l'aplicació.
- La taula mostra **totes** les estacions del dia, de més barata a més cara; les
  que no serveixen el carburant seleccionat van al final amb un guió. Té alçada
  fixa, la mateixa que el mapa, i barra de desplaçament pròpia: hi caben totes
  les estacions sense allargar la pàgina.
- Cada marcador duu escrita a dins la seva **posició a la classificació** de
  preus, i la columna «#» de la taula duu la mateixa. La classificació es calcula
  amb `rank(method="dense")`: les estacions amb el mateix preu comparteixen
  posició i la següent és la immediata, sense saltar-ne cap (1, 1, 2, 2, 2, 3).
  La posició numera, doncs, els **preus** diferents i no les estacions: la 3 vol
  dir «el tercer preu més barat». Es calcula sobre el conjunt **visible**, igual
  que el color, així que es refà amb els filtres.
- Les estacions sense preu no entren a la classificació: cercle gris més petit,
  sense número, i casella «#» buida a la taula.
- El marcador és un `folium.Marker` amb `DivIcon` —un cercle HTML— i no un
  `CircleMarker`, que no pot portar text a dins. La tinta és fosca sobre
  qualsevol color de l'escala: verds, grocs i vermells purs són tons mitjans i el
  negre hi manté prou contrast.
- El filtre de localitat és un desplegable (`st.popover`) amb una casella per
  localitat, totes marcades per defecte, i els botons «Marca-les totes» i
  «Desmarca-les totes». L'estat de cada casella viu a `st.session_state` amb el
  prefix `localitat__`, així que sobreviu als reruns.
- Els botons de selecció massiva actuen com a **callback** (`on_click`) i no dins
  del cos de l'script: escriure a la clau d'un widget ja instanciat és un error a
  Streamlit, i el callback s'executa abans de redibuixar la pàgina.
- Desmarcar totes les localitats dona **zero estacions**, no totes: amb un botó
  explícit de desmarcar, tractar la llista buida com a «no filtrar» seria
  contradictori. L'aplicació avisa amb un missatge en aquest cas.
- El filtre de preu és un `st.slider` de rang acolorit amb la mateixa escala del
  mapa. El seu recorregut es calcula sobre **tots** els preus del carburant, no
  sobre els visibles, perquè els extrems no ballin en filtrar per localitat; la
  clau del widget inclou el carburant, així que el rang es reinicialitza en
  canviar-lo.
- Les estacions que no publiquen el carburant seleccionat no tenen preu amb què
  comparar-se amb l'interval. En comptes de descartar-les en silenci, hi ha una
  casella («Inclou les que no publiquen preu», marcada per defecte) que decideix
  si es mantenen.
- Els preus es comparen amb un marge de `1e-9` (`TOLERANCIA_PREU`): els extrems
  del control són `float` i sense marge un preu igual al límit podria quedar fora.

## Fitxa de l'estació

En clicar un marcador —o una fila de la taula—, la columna de la dreta canvia el
llistat per la fitxa de
l'estació: la seva posició a la classificació, dades de contacte, gràfic de
l'evolució del seu preu i llista de tots els carburants que serveix. El botó
«Torna al llistat» desfà la selecció i «Obre a Google Maps» duu a l'estació en
una pestanya nova.

- El marcador ja **no obre cap globus**: tot el detall va a la fitxa, que no tapa
  el mapa i té espai per al gràfic. El tooltip del ratolí es manté.
- `st_folium` només retorna `last_object_clicked` i `last_object_clicked_count`,
  els dos únics objectes que interessen: qualsevol altra interacció amb el mapa
  (moure'l, fer zoom) no torna a executar el guió.
- El clic torna les **coordenades** del marcador, no cap identificador. L'estació
  es retroba per coincidència de latitud i longitud amb un marge de `1e-6` graus
  (`TOLERANCIA_COORDENADA`), que només ha d'absorbir l'error de coma flotant del
  viatge d'anada i tornada; a la font no hi ha dues estacions al mateix punt.
  Leaflet només retorna el centre exacte en marcadors i en cercles de radi petit;
  per això l'anell de selecció es dibuixa amb `interactive=False`, perquè un clic
  damunt seu no enviï les coordenades del cursor.
- El mapa retorna l'últim marcador clicat **a cada rerun**, també als que no venen
  de cap clic. Sense memòria, tancar la fitxa la tornaria a obrir tot seguit: es
  desa l'empremta del clic ja atès (coordenades i comptador) i només es reacciona
  quan canvia.
- L'anell que marca l'estació oberta va en un `FeatureGroup` a part
  (`feature_group_to_add`), no dins del mapa: `st_folium` hi afegeix les capes
  sense refer el mapa, de manera que la selecció no desfà l'enquadrament ni el
  zoom de l'usuari. Com que la capa s'envia abans de resoldre el clic, en canviar
  de selecció es força un `st.rerun()` perquè l'anell no vagi un clic endarrerit.
- Si els filtres deixen fora l'estació oberta, la selecció s'oblida: la fitxa no
  pot sobreviure a l'estació que la va obrir.
- La taula obre la mateixa fitxa: va amb `on_select="rerun"` i selecció de
  **cel·la** (`single-cell`), no de fila. Amb selecció de fila, Streamlit hi
  afegeix una columna de caselles de verificació que no es pot amagar —la
  dibuixa dins del `canvas` de la graella, fora de l'abast del CSS—, mentre que
  amb selecció de cel·la no n'hi ha cap i clicar qualsevol cel·la identifica
  igualment la seva estació.
- La cel·la arriba com a parell (posició de la fila, nom de la columna). La
  posició la tradueix el frontend amb el mateix mapatge que fa servir per a les
  files, així que no depèn de com hagi reordenat la taula l'usuari.
- Com que la fitxa substitueix la taula, Streamlit descarta l'estat del widget
  mentre no es dibuixa i en tornar al llistat la selecció surt neta.
- L'enllaç a Google Maps es construeix amb les **coordenades**, no amb l'adreça:
  a la font hi ha adreces abreujades i repetides, i el punt no és ambigu. Les
  coordenades es validen dins de rang abans d'entrar a l'URL i es formaten amb
  sis decimals, la precisió que recomana Google.
- En obrir la fitxa, el mapa se centra sobre l'estació i s'hi acosta
  (`ZOOM_DETALL`). Es fa amb els paràmetres `center` i `zoom` de `st_folium`,
  que mouen el mapa **sense refer-lo** i només quan el valor canvia: sense fitxa
  oberta s'hi passa `None` i el mapa es queda tal com el tingui l'usuari, que
  pot moure'l lliurement sense que la pàgina l'hi torni a col·locar. Canviar un
  filtre amb la fitxa oberta sí que refà el mapa i el torna a enquadrar sobre
  totes les estacions visibles.

## Gràfic de l'evolució del preu

`RepositoriEstacions.obte_historic()` retorna una fila per dia amb la lectura més
tardana de cada dia, el mateix criteri que fa servir el mapa.

- L'eix vertical **no arrenca a zero** (`Scale(zero=False)`): el recorregut dels
  preus és molt més estret que el seu valor absolut i, amb el zero, la línia
  quedaria plana. Per això el gràfic es construeix amb Altair i no amb
  `st.line_chart`, que no deixa tocar l'escala.
- Els dies sense preu publicat no són preu zero: queden fora de la línia.
- El període (30 dies, 90 dies o tot) es compta des de l'**última lectura de
  l'estació**, no des d'avui, perquè una estació que ha deixat de publicar
  segueixi mostrant la seva sèrie.
- És una sèrie única, així que no duu llegenda: el títol de l'eix ja diu quin
  carburant és. En passar el ratolí, una guia vertical i un punt marquen el dia
  més proper i en mostren el preu.
- El color de la línia (`COLOR_HISTORIC`) té un to per al tema clar i un altre per
  al fosc, triats amb `st.context.theme`.

## Escala de color

Escala **contínua** verd pur (`#00ff00`, més barat) → vermell pur (`#ff0000`, més
car), interpolant el to HSL de 120° a 0°, amb groc pur al punt mitjà. El color de
cada estació surt de la seva posició relativa entre el preu mínim i el màxim del
**conjunt visible**, així que es recalcula amb els filtres. La barra de la llegenda
es genera amb el mateix interpolador que els marcadors (`escala.genera_mostres`).

Els marcadors porten contorn fosc, no blanc: l'escala passa per grocs i verds
saturats que sobre les tessel·les clares es perdrien amb un contorn clar.

La barra del control de preu duu el mateix degradat. Streamlit no té cap paràmetre
per acolorir-la, així que `pinta_barra_lliscant()` injecta CSS **acotat a la classe
`st-key-filtre_preu`** que Streamlit posa al contenidor del filtre: així no pot
afectar cap altre control.

L'arbre que renderitza `st.slider` a la 1.63 és:

```
[data-testid="stSlider"]        arrel
└── wrapper
    └── pista
        ├── barra               <- rep el degradat
        ├── polze × n           <- cada un amb [data-testid="stSliderThumbValue"]
        └── [data-testid="stSliderTickBar"]
```

La barra és, doncs, el primer fill del contenidor que també porta la barra de
fites, i els selectors s'ancoren a aquests `data-testid` en lloc de les classes
que genera Emotion (`efbyxod*`), que canvien a cada compilació de Streamlit. Dues
proves ho vigilen: una comprova que el CSS no fixi cap classe d'Emotion, i l'altra
que els `data-testid` encara existeixin al paquet instal·lat — si una versió nova
els reanomena, el degradat deixaria d'aplicar-se sense cap error visible.

Dos detalls que fan que el CSS funcioni i que són fàcils de trencar:

- El bloc `<style>` s'injecta **sense indentació**. Markdown converteix en bloc de
  codi qualsevol línia sagnada amb quatre espais o més, i el CSS no s'aplicaria.
- Els selectors fan servir `:has()`, que necessita un navegador actual (Chrome i
  Edge 105+, Safari 15.4+, Firefox 121+).

En pintar tota la barra amb el degradat es perd l'ombrejat gris que Streamlit fa
servir per marcar el tram seleccionat. Els polzes van blancs amb contorn fosc i
mantenen la seva etiqueta de valor, que és el que ara indica el tram triat.

> **Accessibilitat.** L'escala verd–vermell no és segura per a daltonisme
> (protanòpia i deuteranòpia afecten ~8% dels homes). Com que el color no pot ser
> l'únic canal, el preu numèric és sempre visible: al tooltip del marcador, a la
> fitxa emergent i a la taula ordenada. Per a una escala equivalent que sí es
> distingeix, n'hi ha prou amb `escala.TO_MES_BARAT = 240.0` (blau → vermell).
