"""Registro de auditoría para el pipeline de rastreo y selección.

Este módulo define una clase que actúa como el 'cuaderno de bitácora' del crawler.
Guarda cada mensaje relevante con marca de tiempo en un archivo y en la consola,
de modo que el proceso sea completamente trazable: se puede saber qué hizo el
crawler, cuándo lo hizo, y por qué llegó a cada decisión.
"""

import logging
from datetime import datetime
from typing import Dict, List


class AuditJournal:
    """Registra las decisiones del proceso de selección y rastreo.
    
    Esta clase es como un cuaderno de notas que guarda todo lo que hace el crawler.
    Sirve para que después se pueda revisar: qué URLs se encontraron, por qué se
    eligieron ciertas páginas, si hubo errores, etc. Mantiene un registro en archivo
    (audit_log.txt) y también imprime en consola para que veas en tiempo real.
    """

    def __init__(self, log_file: str = "audit_log.txt"):
        # Guardamos el nombre del archivo donde se escribirán los logs.
        self.log_file = log_file
        # Lista interna que guarda cada evento con timestamp para acceso posterior.
        self._entries: List[Dict[str, str]] = []

        # Configura el sistema de logging de Python para escribir en dos lugares simultáneamente:
        # 1. En archivo (FileHandler) - para tener un registro permanente
        # 2. En consola (StreamHandler) - para ver el progreso en tiempo real
        # La codificación utf-8 evita problemas con caracteres especiales (ñ, acentos, etc).
        logging.basicConfig(
            level=logging.INFO,  # INFO significa que solo guarda mensajes normales (no DEBUG)
            format='%(asctime)s | %(levelname)s | %(message)s',  # Formato: hora | tipo | mensaje
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),  # Escribe en archivo
                logging.StreamHandler()  # Escribe en consola
            ]
        )
        self.logger = logging.getLogger(__name__)  # Crea el logger que usaremos

    def record(self, message: str):
        """Registra un mensaje en el log.
        
        Ejemplo: si el crawler encuentra una URL, llama a record('URL encontrada: ...')
        Este método hace dos cosas:
        1. Escribe el mensaje en el archivo de log
        2. Lo guarda también en memoria para poder acceder después
        """
        # Registra el mensaje a través del logger (va al archivo y consola)
        self.logger.info(message)
        # Guarda una copia en memoria con la hora actual en formato ISO
        self._entries.append({
            'time': datetime.now().isoformat(),  # Hora en formato: 2026-05-06T14:30:45.123456
            'message': message  # El mensaje que queremos guardar
        })

    def entries(self) -> List[Dict[str, str]]:
        """Devuelve la lista de eventos registrados internamente.
        
        Si en algún momento quieres revisar todo lo que pasó, llama a este método
        y obtendrás una lista con todos los eventos en orden.
        """
        # Retorna la lista completa de eventos guardados en memoria
        return self._entries
