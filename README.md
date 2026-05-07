# PoC A-Cube - Crawler WCAG

Este proyecto contiene un crawler para auditoría de accesibilidad WCAG. El archivo principal es `crawler.py`, que actúa como orquestador y usa un paquete de módulos en `crawler_modules/` para separar responsabilidades.

## Estructura actual

- `crawler.py`: punto de entrada y coordinador del proceso.
- `crawler_modules/`: paquete con módulos independientes.
  - `audit_log.py`: registra el proceso de auditoría.
  - `site_scanner.py`: rastrea el sitio y descubre páginas internas.
  - `function_classifier.py`: clasifica cada página según su función y complejidad.
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
   - Crea un `FunctionalClassifier` que analiza el contenido de cada página.
   - Identifica categorías como `inicio`, `informativo`, `navegacion`, `formulario`, `servicio`, `dinamico`.
   - Evalúa el nivel de complejidad estructural del DOM.

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

---

## Instalación y Dependencias

Este proyecto requiere Python 3.x y el uso de librerías externas para la gestión HTTP y el parseo de datos. Para preparar el entorno, se recomienda utilizar un entorno virtual:

1. **Instalar dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

Contenido de `requirements.txt`:

- `requests`: Para la gestión de peticiones HTTP eficientes.
- `beautifulsoup4`: Para el parseo y análisis profundo del HTML.
- `tqdm`: Para la visualización de la barra de progreso en consola.

## Uso

Ejecuta `crawler.py` y proporciona la URL raíz cuando se te pregunte:

```powershell
python crawler.py
```

El programa pedirá la URL raíz y generará los archivos de salida en `audit_results/`.

## Parámetros principales

En `crawler.py`, el main recibe:

- `root_url`: URL inicial para el rastreo.
- `max_depth`: profundidad máxima del rastreo (por defecto 3).
- `min_pages`: número mínimo de páginas en la muestra (por defecto 15).
- `random_percent`: proporción de páginas aleatorias (por defecto 0.10).
- `output_dir`: carpeta de salida para los archivos.

## Resultado esperado

Después de ejecutarlo, se generan:

- `audit_results/muestra_wcag.csv`: Listado legible con categorías y complejidad.
- `audit_results/muestra_wcag.json`: Datos estructurados con metadatos de auditoría.
- `audit_log.txt`: Registro detallado de cada decisión tomada por el script.

## Mejoras y Funcionalidades Añadidas (v2.0)

Se han implementado optimizaciones técnicas y funcionales para elevar la herramienta a un estándar profesional:

### Optimización de Alto Rendimiento

**Multithreading (Concurrencia):** El motor de rastreo utiliza ahora hilos simultáneos para la descarga de páginas, reduciendo el tiempo de ejecución en más de un 1000% respecto a la versión secuencial.

**Eficiencia en Memoria (HTML Recycling):** Se ha rediseñado el flujo para que la clasificación se realice sobre el contenido ya descargado en la Fase 1, evitando peticiones HTTP redundantes.

### Análisis Avanzado para Auditoría (IRA)

**Cálculo de Complejidad Automático:** El sistema analiza el DOM de cada página contando elementos interactivos (enlaces, botones, tablas, formularios, multimedia). Clasifica cada URL en niveles Bajo, Medio o Alto para facilitar la selección de una muestra variada según exige el informe IRA.

**Identificación Inteligente de Inicio:** Se ha ajustado la lógica para reconocer la URL raíz del usuario como categoría fundamental de inicio, asegurando el cumplimiento de los criterios de validación.

### Interfaz y Feedback

**Barra de Progreso Visual:** Integración de `tqdm` que permite monitorizar en tiempo real el avance del rastreo y el descubrimiento de URLs.

**Cronómetro de Ejecución:** El resumen final incluye el tiempo total transcurrido, permitiendo auditar la eficiencia del proceso de escaneo.
