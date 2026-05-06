"""Módulo de validación de la muestra final.

Antes de considerar que hemos terminado, necesitamos verificar que la
muestra que elegimos es sólida y cumple los requisitos del proceso de auditoría.
Este módulo hace 5 comprobaciones clave:

1. ¿Hay suficientes páginas? (mínimo 15)
2. ¿Hay suficientes aleatorias? (mínimo 2)
3. ¿Cubrimos todas las categorías funcionales clave?
4. ¿Tenemos páginas de diferentes profundidades?
5. ¿No hay URLs duplicadas?

Si algo falla, genera advertencias pero el proceso continúa (es informativo).
"""

from typing import Dict, List

from .audit_log import AuditJournal


class SampleValidator:
    """Verifica que la muestra seleccionada cumpla los requisitos del proceso."""

    def __init__(self, logger: AuditJournal):
        self.logger = logger
        self.warnings: List[str] = []

    def validate(self, directed: List[Dict], random_selection: List[Dict], min_pages: int = 15) -> bool:
        """Valida que la muestra cumpla todos los criterios.
        
        Args:
            directed: lista de páginas seleccionadas dirigidamente
            random_selection: lista de páginas seleccionadas al azar
            min_pages: número mínimo esperado de páginas
        
        Returns:
            True si TODO está bien, False si hay advertencias.
        
        Realiza 5 validaciones clave y registra resultados.
        """
        self.logger.record("Fase 5: VALIDACIÓN FINAL")
        total = len(directed) + len(random_selection)  # Total de páginas seleccionadas

        # --- VALIDACIÓN 1: ¿Tenemos suficientes páginas en total? ---
        if total < min_pages:
            # Si hay menos de min_pages, es un problema serio
            self.warnings.append(f"TOTAL INSUFICIENTE: {total} < {min_pages}")
            self.logger.record(f"TOTAL INSUFICIENTE: {total} < {min_pages}")
        else:
            # Todo bien, tenemos suficientes
            self.logger.record(f"Total páginas: {total} ≥ {min_pages}")

        # --- VALIDACIÓN 2: ¿Tenemos suficientes páginas ALEATORIAS? ---
        if len(random_selection) < 2:
            # Si tenemos menos de 2 aleatorias, es insuficiente
            self.warnings.append(f"ALEATORIAS INSUFICIENTES: {len(random_selection)} < 2")
            self.logger.record(f"ALEATORIAS INSUFICIENTES: {len(random_selection)} < 2")
        else:
            # Calcula el porcentaje de aleatorias
            percent = len(random_selection) / total * 100 if total else 0
            self.logger.record(f"Páginas aleatorias: {len(random_selection)} ({percent:.1f}%)")

        # --- VALIDACIÓN 3: ¿Cubrimos todas las categorías funcionales CLAVE? ---
        all_pages = directed + random_selection  # Todas las páginas juntas
        categories = set()  # Conjunto único de categorías
        for page in all_pages:
            # Recoge todas las categorías de todas las páginas
            categories.update(page.get('categories', []))

        # Categorías que obligatoriamente queremos tener
        required = ['inicio', 'formulario', 'servicio', 'navegacion']
        # Busca cuáles faltan
        missing = [cat for cat in required if cat not in categories]
        if missing:
            # Si faltan categorías importantes, lo registra como advertencia
            self.warnings.append(f"CATEGORÍAS FALTANTES: {missing}")
            self.logger.record(f"CATEGORÍAS FALTANTES: {missing}")
        else:
            # Bien, tenemos todas las categorías clave
            self.logger.record(f"Categorías presentes: {sorted(categories)}")

        # --- VALIDACIÓN 4: ¿Cubrimos DIFERENTES PROFUNDIDADES? ---
        # Extrae las profundidades de todas las páginas (qué niveles del sitio cubrimos)
        depths = sorted({page['depth'] for page in all_pages})
        # Simplemente reporta cuáles profundidades tenemos representadas
        self.logger.record(f"Profundidades cubiertas: {depths}")

        # --- VALIDACIÓN 5: ¿No hay URLs DUPLICADAS? ---
        urls = [page['url'] for page in all_pages]
        # Compara cantidad de URLs únicas vs total
        if len(set(urls)) < len(urls):
            # Si hay menos únicas que totales, hay duplicados
            self.warnings.append("DUPLICADOS DETECTADOS")
            self.logger.record("DUPLICADOS DETECTADOS")
        else:
            # Bien, todas son únicas
            self.logger.record(f"URLs únicas: {len(urls)}")

        # Si no hay advertencias, devuelve True (muestra válida)
        # Si hay advertencias, devuelve False (pero sigue funcionando)
        return len(self.warnings) == 0
