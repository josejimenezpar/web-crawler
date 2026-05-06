"""Módulo de exportación de resultados de auditoría.

Convierte la muestra final en archivos CSV y JSON que pueden revisarse
como evidencia para auditoría o para análisis posterior.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class ResultWriter:
    """Exporta la muestra final a CSV y JSON."""

    def __init__(self, output_dir: str = "audit_results"):
        # Asegura que el directorio de salida exista antes de escribir archivos.
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def write_csv(self, pages: List[Dict], filename: str = "muestra_wcag.csv") -> str:
        """Genera un archivo CSV con los datos estructurados de la muestra."""
        filepath = self.output_dir / filename
        # Escribe un CSV con columnas claras para la revisión manual.
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Página de la muestra',
                'Tipo funcional',
                'Profundidad',
                'Tipo de selección',
                'Razón de selección'
            ])
            for page in pages:
                writer.writerow([
                    page['url'],
                    ', '.join(page.get('categories', ['otro'])),
                    page['depth'],
                    page.get('selection_type', ''),
                    page.get('selection_reason', '')
                ])
        return str(filepath)

    def write_json(self, pages: List[Dict], filename: str = "muestra_wcag.json") -> str:
        """Genera un archivo JSON con metadatos y la lista completa de páginas."""
        filepath = self.output_dir / filename
        # Construye el JSON con metadatos y la lista completa de páginas.
        data = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'total_pages': len(pages),
                'directed': sum(1 for p in pages if p.get('selection_type') == 'dirigida'),
                'random': sum(1 for p in pages if p.get('selection_type') == 'aleatoria')
            },
            'pages': pages
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return str(filepath)
