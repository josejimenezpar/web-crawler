"""
modules/classify.py
===================
Fase 3.2 — Clasificación funcional de páginas.

Responsabilidades
-----------------
Para cada ``PageRecord`` rastreado, analiza el DOM renderizado (``html_snapshot``)
y asigna uno o varios tipos funcionales a ``functional_types``.

La clasificación es NO excluyente: una misma página puede pertenecer a
varios tipos simultáneamente (p. ej., una página de trámite que tiene
formulario Y es un listado de pasos será ``form`` + ``navigation``).

Tipos funcionales disponibles
------------------------------
- ``home``          — Página raíz del sitio.
- ``form``          — Contiene un formulario sustantivo (≥2 campos + submit).
- ``navigation``    — Su contenido principal es un listado navegable
                      (lista de enlaces, tarjetas, tabla de filas con links).
- ``dynamic``       — Usa un framework JS moderno (React, Angular, Vue, etc.)
                      o contiene elementos multimedia interactivos.
- ``informational`` — Fallback para páginas de contenido textual que no
                      encajan en ninguna categoría anterior.

Criterio de diseño
------------------
Las heurísticas se basan exclusivamente en la estructura del DOM renderizado,
no en patrones de URL. Esto es más robusto frente a sitios con rutas no
semánticas y portales institucionales con URLs generadas por CMS.
"""

import copy
import re
from typing import List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from modules.crawl import PageRecord


# ---------------------------------------------------------------------------
# Constantes de clasificación
# ---------------------------------------------------------------------------

# Regex para identificar la página raíz por su path.
# Cubre los patrones habituales de webs institucionales españolas.
_HOME_PATH = re.compile(r"^/?$|^/index(\.\w+)?$|^/inicio$|^/home$", re.IGNORECASE)

# Tipos de <input> que NO cuentan como campos interactivos para la detección
# de formularios sustantivos. Excluimos también "search" para que una barra
# de búsqueda simple (1 campo) no clasifique la página como "form".
_EXCLUDED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image", "search"}

# Cadenas que identifican frameworks JS modernos en el HTML raw.
# Se buscan en minúsculas sobre el HTML completo en lugar de en el DOM
# parseado porque algunos atributos (p. ej. data-reactroot) y variables
# globales de JS (p. ej. __NEXT_DATA__) pueden aparecer en <script> inline
# o en atributos que BeautifulSoup normaliza de formas distintas.
_FRAMEWORK_SIGNATURES = [
    # React (CRA) y Next.js
    "data-reactroot", "__next_data__", "_next/static",
    # Angular (2+): ng-version en el elemento raíz; ng-app para AngularJS
    "ng-version", "ng-app", "ng-controller",
    # Vue.js y Nuxt.js
    "data-v-", "__vue_app__", "__nuxt__",
    # Patrones genéricos de hidratación de estado en SPAs
    "window.__initial_state__", "window.__state__",
]

# Umbral mínimo de ítems enlazados para considerar una estructura como
# "contenido de navegación". Valor liberal (3) para capturar listados
# pequeños sin dejar de excluir listas decorativas de 1-2 elementos.
_NAV_MIN_ITEMS = 3


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def classify_pages(pages: List[PageRecord]) -> List[PageRecord]:
    """
    Clasifica todas las páginas rastreadas in-place.

    Itera sobre cada ``PageRecord`` y llama a ``_classify`` para rellenar
    el campo ``functional_types``. Devuelve la misma lista por conveniencia
    de encadenamiento en el pipeline principal.

    Parameters
    ----------
    pages : list[PageRecord]
        Registros producidos por ``crawl.crawl()``.

    Returns
    -------
    list[PageRecord]
        Los mismos registros con ``functional_types`` rellenado.
    """
    for record in pages:
        record.functional_types = _classify(record)
    return pages


# ---------------------------------------------------------------------------
# Orquestador interno
# ---------------------------------------------------------------------------

def _classify(record: PageRecord) -> List[str]:
    """
    Determina los tipos funcionales de una sola página.

    Parsea el HTML del snapshot una sola vez y aplica cada clasificador
    en secuencia. El resultado puede contener múltiples tipos.

    El tipo ``informational`` se asigna como fallback solo si no se ha
    detectado ningún otro tipo (o el único detectado es ``home``), ya que
    toda página que no sea clasificable específicamente es contenido informativo.

    Parameters
    ----------
    record : PageRecord
        Registro de la página a clasificar.

    Returns
    -------
    list[str]
        Lista de tipos funcionales asignados. Nunca vacía.
    """
    soup = BeautifulSoup(record.html_snapshot, "lxml")
    types: List[str] = []

    if _is_home(record):
        types.append("home")

    if _has_substantive_form(soup):
        types.append("form")

    if _is_navigation(soup):
        types.append("navigation")

    if _is_dynamic(soup, record.html_snapshot):
        types.append("dynamic")

    # Fallback: si la página no tiene ninguna categoría específica (o solo
    # es "home" sin estructura adicional), se clasifica como informacional.
    if not types or types == ["home"]:
        types.append("informational")

    return types


# ---------------------------------------------------------------------------
# Clasificadores individuales
# ---------------------------------------------------------------------------

def _is_home(record: PageRecord) -> bool:
    """
    Identifica la página raíz del sitio.

    Criterios (se cumple con cualquiera):
    - ``depth == 0``: la página fue la primera en rastrearse (URL raíz).
    - El path de la URL coincide con los patrones de inicio habituales:
      ``/``, ``/index.*``, ``/inicio``, ``/home``.

    Nota: usar ``depth == 0`` como criterio principal evita falsos negativos
    cuando el servidor redirige la raíz a una URL con path distinto.

    Parameters
    ----------
    record : PageRecord
        Registro de la página a evaluar.

    Returns
    -------
    bool
    """
    path = urlparse(record.url).path
    return record.depth == 0 or bool(_HOME_PATH.match(path))


def _has_substantive_form(soup: BeautifulSoup) -> bool:
    """
    Detecta si la página contiene al menos un formulario sustantivo.

    Un formulario se considera sustantivo cuando:
    1. Tiene **≥2 campos interactivos** (inputs reales, no ocultos ni decorativos).
    2. Tiene un **mecanismo de envío** explícito (botón submit o input submit).

    Campos excluidos del conteo (``_EXCLUDED_INPUT_TYPES``):
    - ``hidden``  : no los ve el usuario, no representan interacción.
    - ``submit``  : es el botón de envío, no un campo de datos.
    - ``button``  : botones genéricos, no campos de datos.
    - ``reset``   : botón de reseteo, no un campo de datos.
    - ``image``   : botón de imagen, variante de submit.
    - ``search``  : campo de búsqueda simple; una barra de búsqueda con un
                    solo campo no justifica clasificar la página como "form".

    Esto hace que un formulario de contacto con nombre + email + mensaje
    cuente como sustantivo, pero no una barra de búsqueda con un único campo.

    Parameters
    ----------
    soup : BeautifulSoup
        DOM completo de la página.

    Returns
    -------
    bool
        ``True`` si existe al menos un formulario que cumpla los criterios.
    """
    for form in soup.find_all("form"):
        # Recopilar todos los campos de entrada interactivos del formulario.
        interactive_fields = [
            el for el in form.find_all(["input", "select", "textarea"])
            if not (
                # Filtrar <input> por tipo; <select> y <textarea> siempre cuentan.
                el.name == "input"
                and el.get("type", "text").lower() in _EXCLUDED_INPUT_TYPES
            )
        ]

        # Un <button> sin atributo type es de tipo submit por defecto en HTML5.
        has_submit = bool(
            form.find("input", attrs={"type": "submit"})
            or form.find("button", attrs={"type": "submit"})
            or form.find("button", attrs=lambda a: a is None or "type" not in a)
        )

        if len(interactive_fields) >= 2 and has_submit:
            return True

    return False


def _is_navigation(soup: BeautifulSoup) -> bool:
    """
    Detecta si el contenido principal de la página es un listado navegable.

    El análisis se realiza dentro del **ámbito de contenido** (ver
    ``_get_content_scope``), que excluye ``<header>`` y ``<footer>`` para
    evitar que el menú de navegación global —presente en todas las páginas—
    provoque falsos positivos.

    Se comprueban tres patrones estructurales típicos de páginas de índice:

    **Patrón 1 — Lista de enlaces** (``<ul>`` / ``<ol>``)
        Una lista no ordenada u ordenada cuya mayoría de ítems directos
        (``<li>``) contienen un enlace ``<a>``. Típico de índices de trámites,
        menús de sección, directorios de contactos.
        Umbral: ≥ ``_NAV_MIN_ITEMS`` ítems con enlace.

    **Patrón 2 — Bloques de contenido** (``<article>`` / ``<section>``)
        Varios bloques semánticos que contienen enlace. Típico de listados de
        noticias, catálogos de servicios con tarjetas, portales de trámites.
        Umbral: ≥ ``_NAV_MIN_ITEMS`` elementos con enlace.

    **Patrón 3 — Tabla con filas enlazadas** (``<table>``)
        Una tabla cuyas filas contienen enlaces. Típico de directorios,
        registros, catálogos con columnas de datos y enlace a detalle.
        Umbral: ≥ ``_NAV_MIN_ITEMS`` filas con enlace en el ``<tbody>``.

    Parameters
    ----------
    soup : BeautifulSoup
        DOM completo de la página.

    Returns
    -------
    bool
        ``True`` si se detecta alguno de los tres patrones con el umbral mínimo.
    """
    scope = _get_content_scope(soup)
    if scope is None:
        return False

    # -- Patrón 1: lista de enlaces en el cuerpo del documento --
    for list_tag in scope.find_all(["ul", "ol"]):
        # ``recursive=False`` para no contar sub-ítems de listas anidadas
        # como ítems independientes, evitando contar menús desplegables.
        linked_items = [
            li for li in list_tag.find_all("li", recursive=False)
            if li.find("a")
        ]
        if len(linked_items) >= _NAV_MIN_ITEMS:
            return True

    # -- Patrón 2: bloques de contenido tipo "card" o "artículo" --
    blocks_with_links = [
        el for el in scope.find_all(["article", "section"])
        if el.find("a")
    ]
    if len(blocks_with_links) >= _NAV_MIN_ITEMS:
        return True

    # -- Patrón 3: tabla con filas que contienen enlaces --
    for table in scope.find_all("table"):
        # Preferir <tbody> para ignorar la fila de cabecera del <thead>.
        tbody = table.find("tbody") or table
        linked_rows = [tr for tr in tbody.find_all("tr") if tr.find("a")]
        if len(linked_rows) >= _NAV_MIN_ITEMS:
            return True

    return False


def _is_dynamic(soup: BeautifulSoup, raw_html: str) -> bool:
    """
    Detecta si la página usa tecnologías de renderizado dinámico significativo.

    Se aplica un criterio combinado: basta con que se cumpla cualquiera de
    los dos grupos de señales.

    **Grupo A — Firmas de frameworks JS** (``_FRAMEWORK_SIGNATURES``)
        Se buscan en el HTML en bruto (no en el DOM parseado) porque:
        - Algunos atributos como ``data-reactroot`` están en el HTML fuente
          pero BeautifulSoup puede normalizarlos.
        - Variables JS como ``__NEXT_DATA__`` aparecen en bloques ``<script>``
          inline que se buscan más fácilmente como texto plano.
        La búsqueda es case-insensitive para mayor cobertura.

    **Grupo B — Elementos multimedia/interactivos**
        - ``<video>``: reproductores de vídeo embebido.
        - ``<canvas>``: gráficos, mapas, visualizaciones generadas por JS.
        Estos elementos por definición requieren JS para ser funcionales y
        representan contenido dinámico que un auditor de accesibilidad debe
        evaluar con herramientas específicas.

    Parameters
    ----------
    soup : BeautifulSoup
        DOM completo de la página.
    raw_html : str
        HTML en bruto tal como lo devuelve Playwright, usado para la
        búsqueda de firmas de frameworks.

    Returns
    -------
    bool
    """
    # Grupo A: buscar firmas de frameworks en el HTML fuente
    raw_lower = raw_html.lower()
    if any(sig in raw_lower for sig in _FRAMEWORK_SIGNATURES):
        return True

    # Grupo B: elementos multimedia que requieren JS
    if soup.find(["video", "canvas"]):
        return True

    return False


# ---------------------------------------------------------------------------
# Helper: ámbito de contenido principal
# ---------------------------------------------------------------------------

def _get_content_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Devuelve el subárbol DOM que representa el contenido principal de la
    página, excluyendo las zonas de navegación global (cabecera y pie).

    Esto es esencial para la detección de ``navigation``: el menú principal
    del sitio (habitualmente en ``<header>``) contiene listas de enlaces
    presentes en TODAS las páginas, lo que provocaría falsos positivos si
    no se excluye del análisis.

    Estrategia
    ----------
    1. Si existe un elemento ``<main>`` o ``<div role="main">``, se devuelve
       directamente. Es la señal semántica más fiable de contenido principal.
    2. Si no, se clona el ``<body>`` completo y se eliminan del clon todos
       los elementos ``<header>`` y ``<footer>`` que contiene. El clon
       resultante se usa como ámbito de búsqueda.
    3. Si no existe ``<body>`` (HTML malformado), se devuelve ``None`` y el
       clasificador de navegación retorna ``False`` de forma segura.

    Nota: se usa ``copy.copy`` (copia superficial de la referencia BeautifulSoup)
    en lugar de ``copy.deepcopy`` por rendimiento. La llamada a ``decompose()``
    opera sobre el clon y no modifica el árbol original.

    Parameters
    ----------
    soup : BeautifulSoup
        DOM completo de la página.

    Returns
    -------
    Tag or None
        Subárbol de contenido principal, o ``None`` si el HTML no tiene body.
    """
    # Prioridad 1: elemento semántico <main>
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main:
        return main

    # Prioridad 2: body clonado sin header/footer
    body = soup.find("body")
    if not body:
        return None

    body_clone = copy.copy(body)
    for tag in body_clone.find_all(["header", "footer"]):
        tag.decompose()

    return body_clone
