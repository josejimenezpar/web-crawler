# Explicación completa de `crawler.py`

Este script está diseñado para hacer una auditoría de accesibilidad WCAG basada en un rastreo automático de un sitio web. Está dividido en 6 fases:

1. RASTREO
2. CLASIFICACIÓN
3. SELECCIÓN DIRIGIDA
4. SELECCIÓN ALEATORIA
5. VALIDACIÓN
6. EXPORTACIÓN

---

## Encabezado y propósito

El archivo comienza con un bloque de comentarios (`""" ... """`) que explica su objetivo: descubrir páginas de un sitio, clasificarlas, elegir una muestra adecuada y generar CSV/JSON con un registro de decisiones.

### Qué se describe ahí

- **Entrada esperada:** URL raíz, profundidad, número mínimo de páginas, porcentaje aleatorio.
- **Salida:** CSV, JSON y log.
- **Requisitos de auditoría:** mínimo 15 páginas, 90% dirigidas, 10% aleatorias, mismas páginas del dominio, excluir recursos no HTML.

---

## Imports básicos

El script importa módulos estándar y externos:

- `json`, `csv`, `os`, `sys`, `random`, `re`, `logging`, `datetime`, `Path`, `typing`, `urllib.parse`, `defaultdict`
- `requests`
- `BeautifulSoup` de `bs4`

También incluye un arreglo para Windows que fuerza UTF-8 en la salida estándar si el script se ejecuta en Windows.

---

## `AuditLogger`

### Propósito

Registrar en detalle todo lo que hace el crawler para que el proceso sea trazable.

### Métodos

#### `__init__(self, log_file: str = "audit_log.txt")`
- Crea un logger que escribe un archivo `audit_log.txt` y también imprime en consola.
- Guarda los registros en `self.entries`.

#### `log(self, message: str)`
- Registra una línea de log con marca de tiempo.
- Añade esa línea a la lista interna `self.entries`.

#### `get_entries(self) -> List[Dict]`
- Devuelve todas las entradas guardadas en memoria.

---

## `WebCrawler`

### Propósito

Descubrir URLs internas del sitio web sin salirse del dominio y evitando recursos que no sean páginas HTML.

### Métodos

#### `__init__(self, root_url: str, max_depth: int = 3, logger: AuditLogger = None)`
- Recibe la URL raíz y la profundidad máxima de rastreo.
- Calcula el dominio base para comparar si una URL pertenece al mismo sitio.
- Inicializa:
  - `self.to_visit`: cola de URLs por visitar.
  - `self.visited`: conjunto de URLs ya rastreadas.
  - `self.discovered_urls`: lista de URLs encontradas.
- Crea una sesión HTTP con `requests.Session()` y un User-Agent.
- Registra el inicio del rastreo.

#### `_normalize_url(self, url: str) -> str`
- Normaliza una URL para evitar duplicados.
- Elimina fragmentos (`#...`).
- Elimina parámetros de seguimiento como `utm_`, `gclid`, `fbclid`, etc.
- Convierte dominio a minúsculas.
- Quita slash final inconsistente.
- Devuelve la URL normalizada.

#### `_is_valid_html_url(self, url: str) -> bool`
- Comprueba si la URL apunta posiblemente a una página HTML.
- Rechaza rutas que terminan en `.css`, `.js`, `.jpg`, `.png`, `.pdf`, `.zip`, etc.
- También elimina rutas con patrones como `logout`, `/admin/`, `/api/`, `/ws/`.

#### `_is_same_domain(self, url: str) -> bool`
- Verifica que la URL pertenezca al mismo dominio que la raíz inicial.
- Solo acepta enlaces internos.

#### `crawl(self) -> List[Dict]`
- Ejecuta el rastreo real usando BFS (breadth-first search).
- Para cada URL en la cola:
  - Normaliza la URL.
  - Omite si ya se visitó.
  - Omite si la profundidad excede `max_depth`.
  - Hace una petición HTTP a la página.
  - Parsea el HTML con BeautifulSoup.
  - Guarda la URL en `self.discovered_urls`.
  - Extrae todos los enlaces `<a href=...>`.
  - Convierte enlaces relativos a absolutos.
  - Valida cada enlace con `_is_valid_html_url` y `_is_same_domain`.
  - Si es válido y no visitado, lo añade a la cola con profundidad +1.
- Devuelve la lista de URLs descubiertas.

---

## `FunctionalClassifier`

### Propósito

Clasificar cada URL encontrada según su tipo funcional para poder seleccionar una muestra representativa.

### Métodos

#### `__init__(self, session: requests.Session, logger: AuditLogger)`
- Recibe una sesión HTTP y el logger.
- Usará `requests` para descargar cada página y BeautifulSoup para analizarla.

#### `classify(self, url: str) -> List[str]`
- Descarga la URL.
- Identifica categorías a partir de la URL y del contenido HTML.
- **Categorías posibles:** `inicio`, `informativo`, `navegacion`, `formulario`, `servicio`, `dinamico`.
- Si no encaja en ninguna, devuelve `otro`.
- Usa reglas simples:
  - `inicio` si la ruta es `/`, `/index`, etc.
  - `informativo` si hay `/noticias`, `/blog`, o etiqueta `<article>`/`<main>`.
  - `navegacion` si hay rutas tipo `/servicios`, `/tramites` o muchas listas `<ul>`/`<ol>`.
  - `formulario` si aparece un `<form>`.
  - `servicio` si la URL sugiere trámite/servicio.
  - `dinamico` si detecta scripts con `fetch` o `axios`.

---

## `PageSelector`

### Propósito

Seleccionar la muestra final de páginas asegurando que haya:

- 90% de selección dirigida
- 10% de selección aleatoria
- Al menos 15 páginas
- Tipos funcionales mínimos

### Métodos

#### `__init__(self, urls: List[Dict], classifier: FunctionalClassifier, logger: AuditLogger)`
- Recibe todas las URLs descubiertas y el clasificador.
- Clasifica cada URL y añade el resultado en `url_info['categories']`.
- Registra cada URL y sus categorías.

#### `select(self, min_pages: int = 15, random_percent: float = 0.10) -> Tuple[List[Dict], List[Dict]]`
- Selecciona primero un conjunto dirigido.
- **Criterios directos:**
  - Una página de inicio
  - Una página con formulario
  - Una página de servicio/trámite
  - Una página de navegación/listado
  - También intenta distribuir páginas por profundidad.
- Luego recorta la lista dirigida al 90% de `min_pages`.
- Marca esas páginas con:
  - `selection_type = 'dirigida'`
  - `selection_reason = 'Criterio de representatividad'`
- Para la **selección aleatoria:**
  - Elige al menos 2 páginas o el 10% de `min_pages`, lo que sea mayor.
  - Toma páginas no usadas por la selección dirigida.
  - Marca `selection_type = 'aleatoria'`.
- Devuelve dos listas: `directed` y `random_selection`.

---

## `SampleValidator`

### Propósito

Verificar que la muestra final cumpla con los requisitos del proceso.

### Métodos

#### `__init__(self, logger: AuditLogger)`
- Recibe el logger y prepara `self.warnings`.

#### `validate(self, directed: List[Dict], random_selection: List[Dict], min_pages: int = 15) -> bool`
- Verifica:
  - Total de páginas ≥ `min_pages`
  - Al menos 2 páginas aleatorias
  - Los tipos funcionales mínimos están presentes (`inicio`, `formulario`, `servicio`, `navegacion`)
  - Se cubren varias profundidades
  - No hay URLs duplicadas
- Registra advertencias si algo falta.
- Devuelve `True` si no hay advertencias, `False` si hay problemas.

---

## `SampleExporter`

### Propósito

Guardar la muestra seleccionada en archivos auditables.

### Métodos

#### `__init__(self, output_dir: str = "audit_results")`
- Crea la carpeta `audit_results` si no existe.

#### `export_csv(self, pages: List[Dict], filename: str = "muestra_wcag.csv")`
- Genera un CSV con: URL, categorías, profundidad, tipo de selección, motivo de selección.
- Devuelve la ruta del archivo generado.

#### `export_json(self, pages: List[Dict], filename: str = "muestra_wcag.json")`
- Genera un JSON con metadatos y la lista completa de páginas.
- Devuelve la ruta del archivo generado.

---

## `main(...)`

### Propósito

Coordinador general que ejecuta todo el proceso.

### Flujo

1. Crea el logger.
2. Inicia el `WebCrawler` y ejecuta `crawl()`.
3. Si no hay URLs, termina.
4. Crea el `FunctionalClassifier`.
5. Crea el `PageSelector` y llama a `select()`.
6. Crea el `SampleValidator` y llama a `validate()`.
7. Exporta los resultados con `SampleExporter`.
8. Muestra un resumen final en consola.

### Parámetros

| Parámetro | Descripción |
|---|---|
| `root_url` | La página inicial a rastrear |
| `max_depth` | Profundidad máxima de rastreo |
| `min_pages` | Cuántas páginas seleccionar como mínimo |
| `random_percent` | Porcentaje de selección aleatoria |
| `output_dir` | Carpeta de salida |

---

## Bloque final `if __name__ == "__main__":`

### Qué hace

- Pide al usuario una URL raíz por consola.
- Si no empieza con `http://` o `https://`, añade `https://`.
- Ejecuta `main(...)` con parámetros por defecto:
  - `max_depth=3`
  - `min_pages=15`
  - `random_percent=0.10`
  - `output_dir="audit_results"`
- Sale con código `0` si todo bien, `1` si falla.

---

## Resumen de cómo funciona

1. El crawler parte de una URL inicial.
2. Va siguiendo enlaces internos hasta 3 niveles de profundidad.
3. Rechaza enlaces de archivos, recursos estáticos y fuera de dominio.
4. Clasifica cada página por su función.
5. Elige una muestra equilibrada con criterios obligatorios y un componente aleatorio.
6. Valida que la muestra sea sólida.
7. Guarda CSV, JSON y log.

---

## Ideas clave

| Clase | Responsabilidad |
|---|---|
| `AuditLogger` | Maneja los registros |
| `WebCrawler` | Encuentra las páginas del sitio |
| `FunctionalClassifier` | Decide el tipo de cada página |
| `PageSelector` | Selecciona las páginas a auditar |
| `SampleValidator` | Comprueba que la selección sea válida |
| `SampleExporter` | Guarda los resultados en disco |
| `main()` | Es el orden natural del proceso |
