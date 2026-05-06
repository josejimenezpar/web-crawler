#!/usr/bin/env python3
"""
CRAWLER WCAG - ORQUESTADOR DE AUDITORÍA IRA

Este script es el punto de entrada del pipeline de auditoría.
Importa los componentes del paquete `crawler_modules` y ejecuta las fases
principales en orden:
- escaneo del sitio
- clasificación funcional
- selección de muestra
- validación
- exportación
"""

import sys
import requests

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from crawler_modules import (
    AuditJournal,
    FunctionalClassifier,
    ResultWriter,
    SampleSelector,
    SampleValidator,
    SiteScanner,
)


def main(root_url: str, max_depth: int = 3, min_pages: int = 15,
         random_percent: float = 0.10, output_dir: str = "audit_results"):
    """Ejecuta el pipeline completo de auditoría WCAG para una URL raíz.

    Args:
        root_url: URL inicial del sitio a auditar.
        max_depth: profundidad máxima para el rastreo.
        min_pages: mínimo de páginas que deben seleccionarse.
        random_percent: porcentaje de la muestra que debe ser aleatorio.
        output_dir: carpeta de salida para CSV y JSON.

    Returns:
        True si el proceso se ejecutó, False si no se encontraron URLs.
    """

    # Imprime encabezado informativo de ejecución.
    print("=" * 80)
    print("CRAWLER WCAG - ORQUESTADOR DE AUDITORÍA IRA")
    print("=" * 80)

    # Inicializa el logger de auditoría para registrar cada decisión.
    logger = AuditJournal("audit_log.txt")

    # Fase 1: escanear el sitio y recopilar URLs candidatas.
    scanner = SiteScanner(root_url, max_depth=max_depth, logger=logger)
    discovered_urls = scanner.scan()

    if not discovered_urls:
        print("No se encontraron URLs")
        return False

    # Fase 2: crear el clasificador funcional que etiquetará las páginas.
    session = requests.Session()
    classifier = FunctionalClassifier(session)

    # Fase 3 y 4: seleccionar páginas dirigidas y páginas aleatorias.
    selector = SampleSelector(discovered_urls, classifier, logger)
    directed, random_selection = selector.select(min_pages, random_percent)

    # Fase 5: validar la muestra final.
    validator = SampleValidator(logger)
    is_valid = validator.validate(directed, random_selection, min_pages)

    if not is_valid:
        print("Validación con advertencias (revisar audit_log.txt)")
    else:
        print("Validación exitosa")

    # Fase 6: exportar la muestra final a CSV y JSON.
    all_pages = directed + random_selection
    writer = ResultWriter(output_dir)

    csv_file = writer.write_csv(all_pages)
    json_file = writer.write_json(all_pages)

    # Mostrar un resumen de resultados y rutas de salida.
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"URLs descubiertas: {len(discovered_urls)}")
    print(f"Páginas seleccionadas: {len(all_pages)}")
    print(f"  - Dirigidas (90%): {len(directed)}")
    print(f"  - Aleatorias (10%): {len(random_selection)}")
    print(f"\nArchivos generados:")
    print(f"  CSV: {csv_file}")
    print(f"  JSON: {json_file}")
    print(f"  LOG: audit_log.txt")
    print("=" * 80 + "\n")

    return True


if __name__ == "__main__":
    # Mensaje inicial de uso interactivo al ejecutar el script.
    print("\nCRAWLER WCAG - Ingrese la URL raíz del sitio a auditar:")
    print("   Ejemplo: https://www.ejemplo.gob.es\n")

    root_url = input("URL raíz: ").strip()
    if not root_url.startswith(('http://', 'https://')):
        root_url = 'https://' + root_url

    success = main(
        root_url=root_url,
        max_depth=3,
        min_pages=15,
        random_percent=0.10,
        output_dir="audit_results"
    )
    exit(0 if success else 1)
