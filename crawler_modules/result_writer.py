"""Módulo de exportación de resultados de auditoría.

Después de rastrear, clasificar, seleccionar y validar, necesitamos
guardar los resultados en archivos. Este módulo genera dos tipos de archivos:

- CSV: un archivo de hoja de cálculo legible con columnas y filas
- JSON: un archivo estructurado con metadatos e información completa

Estos archivos son la evidencia oficial de qué páginas se auditaron y por qué.
Ahora se incluye la columna de Complejidad en los reportes.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class ResultWriter:
    """Exporta la muestra final a CSV y JSON."""

    def __init__(self, output_dir: str = "audit_results"):
        """Prepara el directorio donde se guardarán los archivos.
        
        Args:
            output_dir: ruta de la carpeta de salida (se crea si no existe)
        """
        # Convierte el string a un objeto Path (manejo moderno de rutas en Python)
        self.output_dir = Path(output_dir)
        # Crea la carpeta si no existe. exist_ok=True significa: si ya existe, no error
        self.output_dir.mkdir(exist_ok=True)

    def write_csv(self, pages: List[Dict], filename: str = "muestra_wcag.csv") -> str:
        """Exporta la muestra a un archivo CSV (hoja de cálculo).
        
        Un CSV es un formato simple de columnas y filas que cualquier programa
        puede leer (Excel, Google Sheets, Python, etc). Es perfecto para auditoría
        porque es transparente y fácil de revisar manualmente.
        
        Args:
            pages: lista de páginas a exportar
            filename: nombre del archivo a generar
        
        Returns:
            ruta completa al archivo creado
        """
        filepath = self.output_dir / filename
        # Abre el archivo en modo escritura, con UTF-8 para caracteres especiales
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Primera fila: encabezados de las columnas
            writer.writerow([
                'Página de la muestra',
                'Tipo funcional',
                'Complejidad',  # Añadida columna de complejidad en la primera fila
                'Profundidad',
                'Tipo de selección',
                'Razón de selección'
            ])
            # Filas de datos: una por cada página
            for page in pages:
                writer.writerow([
                    page['url'],  # la URL
                    ', '.join(page.get('categories', ['otro'])),  # categorías separadas por coma
                    page.get('complexity', 'Desconocida'),  # Extraemos el dato de complejidad calculado
                    page['depth'],  # profundidad en el sitio
                    page.get('selection_type', ''),  # 'dirigida' o 'aleatoria'
                    page.get('selection_reason', '')  # por qué se eligió
                ])
        return str(filepath)

    def write_json(self, pages: List[Dict], filename: str = "muestra_wcag.json") -> str:
        """Exporta la muestra a un archivo JSON (formato estructurado).
        
        JSON es útil porque:
        - Preserva toda la información de forma estructurada
        - Puede procesarse fácilmente con programas
        - Incluye metadatos (cuándo se generó, cuántas dirigidas/aleatorias, etc)
        
        Args:
            pages: lista de páginas a exportar
            filename: nombre del archivo a generar
        
        Returns:
            ruta completa al archivo creado
        """
        filepath = self.output_dir / filename
        # Construye la estructura de datos a guardar
        data = {
            'metadata': {  # Información sobre la auditoría
                'generated': datetime.now().isoformat(),  # Hora en que se generó
                'total_pages': len(pages),  # Total de páginas en la muestra
                'directed': sum(1 for p in pages if p.get('selection_type') == 'dirigida'),  # Cuántas dirigidas
                'random': sum(1 for p in pages if p.get('selection_type') == 'aleatoria')  # Cuántas aleatorias
            },
            'pages': pages  # La lista completa de páginas con toda su información
        }
        # Guarda el JSON en archivo
        with open(filepath, 'w', encoding='utf-8') as f:
            # indent=2 hace el JSON legible con indentación
            # ensure_ascii=False permite caracteres especiales sin escape
            json.dump(data, f, indent=2, ensure_ascii=False)
        return str(filepath)