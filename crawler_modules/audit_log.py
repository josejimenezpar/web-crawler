"""Registro de auditoría para el pipeline de rastreo y selección.

Este módulo define una clase ligera que guarda cada mensaje relevante
con marca de tiempo y escribe la misma información en archivo y consola
para que el proceso sea totalmente trazable.
"""

import logging
from datetime import datetime
from typing import Dict, List


class AuditJournal:
    """Registra las decisiones del proceso de selección y rastreo."""

    def __init__(self, log_file: str = "audit_log.txt"):
        self.log_file = log_file
        self._entries: List[Dict[str, str]] = []

        # Configura el sistema de logging para escribir en archivo y en la consola.
        # La codificación utf-8 evita problemas con caracteres especiales.
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def record(self, message: str):
        # Registra el mensaje en el logger configurado y guarda una copia en memoria.
        self.logger.info(message)
        self._entries.append({
            'time': datetime.now().isoformat(),
            'message': message
        })

    def entries(self) -> List[Dict[str, str]]:
        """Devuelve la lista de eventos registrados internamente."""
        # Permite inspeccionar el historial de auditoría desde otras partes del programa.
        return self._entries
