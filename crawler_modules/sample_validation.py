"""Módulo de validación de la muestra final.

Contiene las reglas que garantizan que la selección de páginas cumpla
los requisitos mínimos de cantidad, aleatoriedad, categorías y unicidad.
"""

from typing import Dict, List

from .audit_log import AuditJournal


class SampleValidator:
    """Verifica que la muestra seleccionada cumpla los requisitos del proceso."""

    def __init__(self, logger: AuditJournal):
        self.logger = logger
        self.warnings: List[str] = []

    def validate(self, directed: List[Dict], random_selection: List[Dict], min_pages: int = 15) -> bool:
        """Valida la muestra completa y registra advertencias si algo no cumple."""
        self.logger.record("Fase 5: VALIDACIÓN FINAL")
        total = len(directed) + len(random_selection)

        # Validación 1: el total de páginas debe ser al menos el mínimo.
        if total < min_pages:
            self.warnings.append(f"TOTAL INSUFICIENTE: {total} < {min_pages}")
            self.logger.record(f"TOTAL INSUFICIENTE: {total} < {min_pages}")
        else:
            self.logger.record(f"Total páginas: {total} ≥ {min_pages}")

        # Validación 2: debe haber al menos dos páginas seleccionadas aleatoriamente.
        if len(random_selection) < 2:
            self.warnings.append(f"ALEATORIAS INSUFICIENTES: {len(random_selection)} < 2")
            self.logger.record(f"ALEATORIAS INSUFICIENTES: {len(random_selection)} < 2")
        else:
            percent = len(random_selection) / total * 100 if total else 0
            self.logger.record(f"Páginas aleatorias: {len(random_selection)} ({percent:.1f}%)")

        # Validación 3: se deben cubrir las categorías funcionales clave.
        all_pages = directed + random_selection
        categories = set()
        for page in all_pages:
            categories.update(page.get('categories', []))

        required = ['inicio', 'formulario', 'servicio', 'navegacion']
        missing = [cat for cat in required if cat not in categories]
        if missing:
            self.warnings.append(f"CATEGORÍAS FALTANTES: {missing}")
            self.logger.record(f"CATEGORÍAS FALTANTES: {missing}")
        else:
            self.logger.record(f"Categorías presentes: {sorted(categories)}")

        # Validación 4: comprobar cobertura de profundidad en la muestra.
        depths = sorted({page['depth'] for page in all_pages})
        self.logger.record(f"Profundidades cubiertas: {depths}")

        # Validación 5: verificar que no haya URLs duplicadas en la selección final.
        urls = [page['url'] for page in all_pages]
        if len(set(urls)) < len(urls):
            self.warnings.append("DUPLICADOS DETECTADOS")
            self.logger.record("DUPLICADOS DETECTADOS")
        else:
            self.logger.record(f"URLs únicas: {len(urls)}")

        # Si hay advertencias, el método devuelve False para indicar revisión.
        return len(self.warnings) == 0
