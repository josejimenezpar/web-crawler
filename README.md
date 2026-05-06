# PoC A-Cube - Crawler WCAG

Este proyecto contiene un crawler para auditoría de accesibilidad WCAG. El archivo principal es `crawler.py`, que actúa como orquestador y usa un paquete de módulos en `crawler_modules/` para separar responsabilidades.

## Estructura actual

- `crawler.py`: punto de entrada y coordinador del proceso.
- `crawler_modules/`: paquete con módulos independientes.
  - `audit_log.py`: registra el proceso de auditoría.
  - `site_scanner.py`: rastrea el sitio y descubre páginas internas.
  - `function_classifier.py`: clasifica cada página según su función.
  - `sample_selection.py`: selecciona la muestra dirigida y aleatoria.
  - `sample_validation.py`: valida que la muestra cumpla los criterios.
  - `result_writer.py`: exporta los resultados a CSV y JSON.

## Flujo de `crawler.py`

`crawler.py` ejecuta el proceso en seis fases:

1. **RASTREO**
   - Usa `SiteScanner` para recorrer el sitio desde la URL raíz.
   - Encuentra URLs internas válidas hasta una profundidad máxima.
   - Filtra recursos no HTML y enlaces fuera del dominio.

2. **CLASIFICACIÓN**
   - Crea un `FunctionalClassifier` que descarga cada página y detecta su tipo funcional.
   - Identifica categorías como `inicio`, `informativo`, `navegacion`, `formulario`, `servicio`, `dinamico`.

3. **SELECCIÓN DIRIGIDA**
   - Usa `SampleSelector` para elegir páginas representativas según sus categorías.
   - Asegura cobertura de roles clave y distintos niveles de profundidad.

4. **SELECCIÓN ALEATORIA**
   - Completa la muestra con páginas aleatorias no usadas en la selección dirigida.
   - Selecciona al menos 2 páginas aleatorias o el 10% del total mínimo.

5. **VALIDACIÓN**
   - `SampleValidator` revisa la muestra final.
   - Comprueba que haya al menos 15 páginas, cobertura de categorías, profundidad y URLs únicas.

6. **EXPORTACIÓN**
   - `ResultWriter` genera un CSV (`muestra_wcag.csv`) y un JSON (`muestra_wcag.json`).
   - Guarda los resultados en el directorio `audit_results`.

## Descripción de módulos

### `crawler_modules/audit_log.py`

Registra los eventos del proceso de auditoría. Cada mensaje se guarda en un archivo de log y también se imprime en consola. Sirve para trazabilidad y para revisar cómo se tomaron las decisiones en cada fase.

### `crawler_modules/site_scanner.py`

Explora el sitio web usando BFS. Normaliza URLs, elimina parámetros de seguimiento y descarta enlaces no relevantes. Solo sigue enlaces internos que apunten a páginas HTML.

### `crawler_modules/function_classifier.py`

Clasifica cada página según su función. Analiza la URL y el contenido HTML, buscando patrones y etiquetas que indiquen si la página es de inicio, informativa, de navegación, formulario, servicio o dinámica.

### `crawler_modules/sample_selection.py`

Construye la muestra de auditoría. Primero elige páginas dirigidas que abarquen categorías funcionales clave. Luego agrega una selección aleatoria para cubrir variabilidad y evitar sesgos.

### `crawler_modules/sample_validation.py`

Verifica que la muestra seleccionada cumpla las reglas del proceso. Controla cantidad mínima, cantidad de aleatorias, categorías presentes, cobertura de profundidad y unicidad de URLs.

### `crawler_modules/result_writer.py`

Exporta la muestra final a disco. Genera un archivo CSV con columnas legibles y un archivo JSON con metadatos y la lista completa de páginas.

## Uso

Ejecuta `crawler.py` y proporciona la URL raíz cuando se te pregunte:

```powershell
python crawler.py
```

El programa pedirá la URL raíz y generará los archivos de salida en `audit_results/`.

## Parámetros principales

En `crawler.py`, el `main` recibe:

- `root_url`: URL inicial para el rastreo.
- `max_depth`: profundidad máxima del rastreo (por defecto 3).
- `min_pages`: número mínimo de páginas en la muestra (por defecto 15).
- `random_percent`: proporción de páginas aleatorias (por defecto 0.10).
- `output_dir`: carpeta de salida para los archivos.

## Resultado esperado

Después de ejecutarlo, se generan:

- `audit_results/muestra_wcag.csv`
- `audit_results/muestra_wcag.json`
- `audit_log.txt`

Si la validación falla con advertencias, el proceso sigue, pero se mantiene un registro para revisión.
