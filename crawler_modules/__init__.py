"""Paquete de módulos para el crawler WCAG.

Este paquete expone las clases principales que componen el pipeline:
- escaneo del sitio,
- clasificación funcional,
- selección de muestra,
- validación,
- exportación de resultados,
- registro de auditoría.
"""

from .audit_log import AuditJournal
from .function_classifier import FunctionalClassifier
from .result_writer import ResultWriter
from .sample_selection import SampleSelector
from .sample_validation import SampleValidator
from .site_scanner import SiteScanner

__all__ = [
    'AuditJournal',
    'FunctionalClassifier',
    'ResultWriter',
    'SampleSelector',
    'SampleValidator',
    'SiteScanner'
]
