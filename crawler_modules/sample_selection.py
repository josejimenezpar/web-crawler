"""Módulo de selección de muestra para auditoría.

Este módulo separa la selección dirigida y la selección aleatoria,
con el objetivo de cubrir la representatividad funcional y cumplir los
requisitos de muestra mínima.
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

        # Clasifica cada URL y guarda las categorías que se usarán en la selección.
        self.logger.record("Fase 2: CLASIFICACIÓN FUNCIONAL")
        for url_info in self.urls:
            url_info['categories'] = self.classifier.classify(url_info['url'])
            self.logger.record(f"{url_info['url']} → {url_info['categories']}")

    def select(self, min_pages: int = 15, random_percent: float = 0.10) -> Tuple[List[Dict], List[Dict]]:
        """Realiza la selección dirigida y la selección aleatoria de páginas."""
        self.logger.record("Fase 3 + 4: SELECCIÓN DIRIGIDA Y ALEATORIA")

        directed: List[Dict] = []
        random_selection: List[Dict] = []

        # Selección dirigida: asegurar cobertura de roles funcionales clave.
        home_pages = [u for u in self.urls if 'inicio' in u.get('categories', [])]
        if home_pages:
            directed.append(home_pages[0])
            self.logger.record(f"  Inicio: {home_pages[0]['url']}")

        form_pages = [u for u in self.urls if 'formulario' in u.get('categories', []) and u not in directed]
        if form_pages:
            directed.append(form_pages[0])
            self.logger.record(f"  Formulario: {form_pages[0]['url']}")

        service_pages = [u for u in self.urls if 'servicio' in u.get('categories', []) and u not in directed]
        if service_pages:
            directed.append(service_pages[0])
            self.logger.record(f"  Servicio: {service_pages[0]['url']}")

        nav_pages = [u for u in self.urls if 'navegacion' in u.get('categories', []) and u not in directed]
        if nav_pages:
            directed.append(nav_pages[0])
            self.logger.record(f"  Navegación: {nav_pages[0]['url']}")

        # Si aún falta cantidad, completar la muestra dirigida con páginas de diferentes profundidades.
        depths: defaultdict[int, List[Dict]] = defaultdict(list)
        for url in self.urls:
            if url not in directed:
                depths[url['depth']].append(url)

        needed = int(min_pages * 0.9) - len(directed)
        for depth in sorted(depths.keys()):
            if needed <= 0:
                break
            candidates = depths[depth]
            take = min(len(candidates), needed)
            directed.extend(candidates[:take])
            needed -= take
            if take > 0:
                self.logger.record(f"  Profundidad {depth}: {take} páginas añadidas")

        directed = directed[:int(min_pages * 0.9)]
        for page in directed:
            page['selection_type'] = 'dirigida'
            page['selection_reason'] = 'Criterio de representatividad'

        self.logger.record(f"Selección dirigida: {len(directed)} páginas")

        # Selección aleatoria: agregar un porcentaje extra de páginas para cubrir variabilidad.
        available_for_random = [u for u in self.urls if u not in directed]
        random_count = max(2, int(min_pages * random_percent))
        if available_for_random:
            chosen = random.sample(available_for_random, min(random_count, len(available_for_random)))
            for page in chosen:
                page['selection_type'] = 'aleatoria'
                page['selection_reason'] = 'Selección aleatoria del 10%'
            random_selection = chosen
            self.logger.record(f"Selección aleatoria: {len(random_selection)} páginas")

        return directed, random_selection
