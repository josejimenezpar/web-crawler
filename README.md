
## 1. Objetivo del script

Automatizar la **identificación, selección y descarga estructurada** de un conjunto de páginas web de un mismo sitio, de forma que:

*   Se garantice una **muestra mínima de 15 páginas**
*   La muestra sea **representativa funcionalmente**
*   **Al menos el 10 %** de las páginas seleccionadas (mínimo 2) se elijan **aleatoriamente**
*   Se genere una **base preparada para evaluación de accesibilidad** (no el análisis WCAG en sí)

***

## 2. Entradas del sistema

El script debe aceptar como entrada:

1.  **URL raíz del sitio web**  
    Ejemplo: `https://www.ejemplo.gob.es`

2.  **Parámetros configurables**
    *   Profundidad máxima de rastreo (por defecto: 3 niveles)
    *   Número mínimo de páginas a seleccionar (por defecto: 15)
    *   Porcentaje de páginas aleatorias (por defecto: 10 %)
    *   Exclusión de patrones de URL (logout, trackers, parámetros irrelevantes, etc.)

***

## 3. Fases funcionales del script

### 3.1. Rastreo inicial del sitio (crawling)

Función:

*   Descubrir URLs internas accesibles desde la página principal.

Requisitos funcionales:

*   Restringir el rastreo al **mismo dominio**
*   Excluir:
    *   Recursos no HTML (imágenes, CSS, JS, PDFs)
    *   URLs duplicadas por parámetros
*   Registrar:
    *   URL
    *   Profundidad
    *   Página origen

Resultado:

*   Conjunto normalizado de URLs candidatas

***

### 3.2. Clasificación funcional de páginas

Cada URL detectada debe clasificarse automáticamente (heurística básica) en una o varias categorías:

**Categorías mínimas requeridas**

*   Página de inicio (`/`, `/index`)
*   Páginas de contenido informativo
*   Páginas de navegación estructural (categorías, listados)
*   Páginas con formularios (`<form>`)
*   Páginas de servicios o procesos clave
*   Páginas con contenido dinámico significativo

La clasificación puede basarse en:

*   Estructura HTML
*   Presencia de ciertos elementos (`form`, `input`, `button`, `video`)
*   Patrones de URL (`/tramites`, `/servicios`, `/buscar`)

Resultado:

*   Lista de URLs etiquetadas por tipo funcional

***

### 3.3. Selección dirigida (90 % mínimo)

Función:
Garantizar la representatividad exigida por el IRA.

Criterios obligatorios de selección dirigida:

*   1 página de inicio
*   ≥ 1 página con formulario
*   ≥ 1 página de servicio o trámite
*   ≥ 1 página de navegación/listado
*   Páginas a distintos niveles de profundidad
*   Páginas con distinta estructura y complejidad

Regla:

*   **Al menos el 90 %** de las páginas seleccionadas (13 de 15) deben proceder de esta selección dirigida.

Resultado:

*   Conjunto base de páginas justificables ante una auditoría

***

### 3.4. Selección aleatoria (≥ 10 %)

Función:
Cumplir el requisito de aleatoriedad exigido.

Criterios:

*   Seleccionar aleatoriamente URLs **no usadas** en la selección dirigida
*   Deben ser páginas HTML válidas y accesibles
*   No pueden sustituir páginas “obligatorias” (home, formulario, servicio)

Regla:

*   **Mínimo 10 % del total**, redondeando al alza  
    → Con 15 páginas ⇒ **2 páginas aleatorias**

Resultado:

*   Subconjunto marcado explícitamente como `random=true`

***

### 3.5. Validación final de la muestra

Antes de finalizar, el script debe comprobar:

*   Total de páginas ≥ 15
*   Páginas únicas (sin duplicados funcionales evidentes)
*   Cumplimiento del porcentaje aleatorio
*   Presencia de todos los tipos funcionales mínimos

Si no se cumple:

*   Ajustar selección automáticamente
*   Registrar advertencias en el log

***

## 4. Salidas del sistema

El script debe generar como mínimo:

1.  **Listado estructurado de páginas seleccionadas**
    *   URL
    *   Tipo funcional
    *   Nivel de profundidad
    *   Selección: dirigida / aleatoria

2.  **Archivo exportable**
    *   CSV o JSON
    *   Compatible con el IRA (columna “Página de la muestra”)

3.  **Log de ejecución**
    *   Número final de páginas
    *   Porcentaje aleatorio real
    *   Reglas aplicadas

***

## 5. Consideraciones clave de cumplimiento IRA

*   La selección debe ser **defendible**, no solo técnica
*   Las páginas deben representar **uso real del sitio**
*   El componente aleatorio debe estar **claramente identificado**
*   El proceso debe ser **repetible y trazable**

***

## 6. Resultado esperado

Un script que **no decide accesibilidad**, pero que:

*   Produce una **muestra válida para el IRA**
*   Reduce el sesgo humano
*   Facilita revisiones periódicas y auditorías

***

## 7. Implementación MVP (uv + librería para MCP)

Se ha creado un proyecto Python con `uv` y un paquete reutilizable llamado `ira_web_crawler`, diseñado para ser consumido desde un MCP como librería.

### 7.1. Estructura principal

*   `pyproject.toml`: configuración del paquete y entrypoint CLI
*   `src/ira_web_crawler/api.py`: API de librería (`crawl_and_select`) y exportadores JSON/CSV
*   `src/ira_web_crawler/cli.py`: CLI mínima para ejecución con `uv run`
*   `outputs/`: resultados exportados

### 7.2. Uso como librería (MCP)

```python
from ira_web_crawler import crawl_and_select

result = crawl_and_select(
    root_url="https://www.ejemplo.gob.es",
    max_depth=3,
    min_pages=15,
    random_percent=10,
)

print(result.candidate_count)
print(len(result.selected_pages))
print(result.random_percentage_real)
```

### 7.3. Uso por CLI

```bash
uv run ira-web-crawler https://www.ejemplo.gob.es --max-depth 3 --min-pages 15 --random-percent 10
```

Genera:

*   `outputs/muestra_ira.json`
*   `outputs/muestra_ira.csv`

### 7.4. Validaciones incluidas en MVP

*   Restricción al mismo dominio
*   Exclusión de no-HTML
*   Clasificación heurística por categorías funcionales
*   Selección dirigida + aleatoria con trazabilidad
*   Verificación de mínimos funcionales y porcentaje aleatorio

