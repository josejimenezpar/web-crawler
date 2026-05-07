"""Módulo de selección de muestra para auditoría.

Después de descubrir y clasificar páginas, necesitamos elegir cuáles auditar.
Este módulo hace dos cosas:

1. SELECCIÓN DIRIGIDA (90% de la muestra):
   Elige páginas representativas de cada categoría funcional.
   Así garantizamos que auditamos: inicio, formularios, servicios, navegación, etc.

2. SELECCIÓN ALEATORIA (10% de la muestra):
   Elige páginas al azar para cubrir variabilidad y evitar sesgos.

El resultado es una muestra equilibrada y estadisticamente sólida.
"""

import random
from collections import defaultdict
from typing import Dict, List, Tuple

from .audit_log import AuditJournal
from .function_classifier import FunctionalClassifier


class SampleSelector:
    """Elige las páginas que formarán la muestra final."""

    def __init__(self, urls: List[Dict], classifier: FunctionalClassifier, logger: AuditJournal):
        """Clasifica todas las URLs descubiertas para preparar la selección."""
        self.urls = urls
        self.classifier = classifier
        self.logger = logger

        # Clasifica cada URL y guarda las categorías y la complejidad que se usarán en la selección.
        self.logger.record("Fase 2: CLASIFICACIÓN FUNCIONAL Y CÁLCULO DE COMPLEJIDAD")
        for url_info in self.urls:
            # Llamamos al método analyze que ahora devuelve un diccionario con categorías y complejidad
            analysis = self.classifier.analyze(url_info['url'])
            url_info['categories'] = analysis['categories']
            url_info['complexity'] = analysis['complexity']  # Guardamos la complejidad
            self.logger.record(f"{url_info['url']} → {url_info['categories']} | Complejidad: {url_info['complexity']}")

    def select(self, min_pages: int = 15, random_percent: float = 0.10) -> Tuple[List[Dict], List[Dict]]:
        """Selecciona las páginas que auditar: dirigidas + aleatorias.
        
        Args:
            min_pages: mínimo de páginas que debemos seleccionar (por defecto 15)
            random_percent: porcentaje que debe ser aleatorio (por defecto 0.10 = 10%)
        
        Returns:
            Tupla con (lista de páginas dirigidas, lista de páginas aleatorias)
        
        Lógica:
        - Primero elige páginas dirigidas representativas
        - Luego completa con páginas aleatorias
        - Asegura que hay al menos min_pages en total
        """
        self.logger.record("Fase 3 + 4: SELECCIÓN DIRIGIDA Y ALEATORIA")

        directed: List[Dict] = []  # Aquí irán las páginas dirigidas (90%)
        random_selection: List[Dict] = []  # Aquí irán las aleatorias (10%)

        # === SELECCIÓN DIRIGIDA ===
        # Elegimos una página de cada categoría clave para garantizar cobertura
        
        # 1. Busca una página de INICIO
        home_pages = [u for u in self.urls if 'inicio' in u.get('categories', [])]
        if home_pages:
            # Toma la primera que encuentre
            directed.append(home_pages[0])
            self.logger.record(f"  Inicio: {home_pages[0]['url']}")

        # 2. Busca una página con FORMULARIO (que no haya sido ya seleccionada)
        form_pages = [u for u in self.urls if 'formulario' in u.get('categories', []) and u not in directed]
        if form_pages:
            directed.append(form_pages[0])
            self.logger.record(f"  Formulario: {form_pages[0]['url']}")

        # 3. Busca una página de SERVICIO
        service_pages = [u for u in self.urls if 'servicio' in u.get('categories', []) and u not in directed]
        if service_pages:
            directed.append(service_pages[0])
            self.logger.record(f"  Servicio: {service_pages[0]['url']}")

        # 4. Busca una página de NAVEGACIÓN
        nav_pages = [u for u in self.urls if 'navegacion' in u.get('categories', []) and u not in directed]
        if nav_pages:
            directed.append(nav_pages[0])
            self.logger.record(f"  Navegación: {nav_pages[0]['url']}")

        # 5. Si aún necesitamos más páginas dirigidas, las añadimos distribuyéndolas por profundidad
        # Esto asegura que auditamos páginas a diferentes niveles del sitio
        depths: defaultdict[int, List[Dict]] = defaultdict(list)
        for url in self.urls:
            if url not in directed:  # Solo URLs que no hemos seleccionado ya
                # Agrupa URLs por profundidad
                depths[url['depth']].append(url)

        # Cuántas páginas dirigidas nos faltan para llegar al 90% de min_pages?
        # Si min_pages es 15, necesitamos 90% de 15 = 13.5 → 13 páginas dirigidas
        needed = int(min_pages * 0.9) - len(directed)
        # Procesa profundidades en orden (primero las más cercanas)
        for depth in sorted(depths.keys()):
            if needed <= 0:
                break  # Ya tenemos suficientes
            candidates = depths[depth]  # Páginas a esta profundidad
            take = min(len(candidates), needed)  # Cuántas tomamos de esta profundidad
            directed.extend(candidates[:take])  # Añade esas páginas
            needed -= take  # Reduce lo que falta
            if take > 0:
                self.logger.record(f"  Profundidad {depth}: {take} páginas añadidas")

        # Limita a exactamente el 90% de min_pages
        directed = directed[:int(min_pages * 0.9)]
        # Marca todas como 'dirigidas'
        for page in directed:
            page['selection_type'] = 'dirigida'
            page['selection_reason'] = 'Criterio de representatividad'

        self.logger.record(f"Selección dirigida: {len(directed)} páginas")

        # === SELECCIÓN ALEATORIA ===
        # Ahora tomamos páginas al azar de las que no usamos
        available_for_random = [u for u in self.urls if u not in directed]
        random_count = max(2, int(min_pages * random_percent))  # Mínimo 2, o el 10% de min_pages
        if available_for_random:
            # Elige random_count páginas al azar (sin repetición)
            chosen = random.sample(available_for_random, min(random_count, len(available_for_random)))
            # Marca todas como 'aleatorias'
            for page in chosen:
                page['selection_type'] = 'aleatoria'
                page['selection_reason'] = 'Selección aleatoria del 10%'
            random_selection = chosen
            self.logger.record(f"Selección aleatoria: {len(random_selection)} páginas")

        return directed, random_selection