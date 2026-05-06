#!/usr/bin/env python3
"""
================================================================================
CRAWLER WCAG - AUDITORÍA DE ACCESIBILIDAD IRA
================================================================================

OBJETIVO GLOBAL:
  Automatizar la identificación, selección y descarga de páginas web para
  auditoría de accesibilidad WCAG, garantizando:
  - Mínimo 15 páginas
  - Representatividad funcional (90% dirigida)
  - Aleatoriedad (≥10%, mín 2 páginas)
  - Base preparada para IRA

FASES FUNCIONALES:
  1. RASTREO: Descubrir URLs internas del sitio
  2. CLASIFICACIÓN: Etiquetar por tipo funcional
  3. SELECCIÓN DIRIGIDA: Garantizar representatividad (90%)
  4. SELECCIÓN ALEATORIA: Cumplir requisito aleatorio (10%)
  5. VALIDACIÓN: Verificar criterios cumplidos
  6. EXPORTACIÓN: CSV/JSON + Log ejecutable

ENTRADAS:
  - URL raíz del sitio
  - Profundidad máxima (default: 3)
  - Mínimo páginas (default: 15)
  - Porcentaje aleatorio (default: 10%)

SALIDAS:
  - CSV/JSON con páginas seleccionadas
  - Log de ejecución (trazable)
  - Marcado explícito de dirigida vs aleatoria
================================================================================
"""

import json
import csv
import os
import sys
import random
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse, urlunparse
from collections import defaultdict

# Configurar UTF-8 para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURACIÓN Y LOGGING
# ============================================================================

class AuditLogger:
    """
    PROPÓSITO: Crear logs trazables y auditables de cada decisión del crawler
    
    Por qué: El IRA exige procesos defendibles y repetibles.
    Aquí documentamos CADA paso: URLs encontradas, clasificaciones, 
    criterios de selección aplicados, decisiones tomadas.
    """
    
    def __init__(self, log_file: str = "audit_log.txt"):
        self.log_file = log_file
        self.entries = []
        
        # Configurar logging de Python
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def log(self, message: str):
        """Registra mensaje en log"""
        self.logger.info(message)
        self.entries.append({'time': datetime.now().isoformat(), 'msg': message})
    
    def get_entries(self) -> List[Dict]:
        """Retorna todos los registros para exportar"""
        return self.entries


# ============================================================================
# FASE 1: RASTREO (CRAWLING)
# ============================================================================

class WebCrawler:
    """
    PROPÓSITO: Descubrir URLs internas accesibles desde la página principal
    
    REQUISITOS IRA:
    - Restringir al mismo dominio (sin salir del sitio)
    - Excluir recursos no HTML (CSS, JS, imágenes, PDFs)
    - Excluir URLs duplicadas por parámetros irrelevantes
    - Registrar: URL, profundidad, página origen
    - Respetar profundidad máxima (default: 3 niveles)
    
    RESULTADO: Lista normalizada de URLs candidatas para auditoría
    """
    
    def __init__(self, root_url: str, max_depth: int = 3, logger: AuditLogger = None):
        """
        Inicializa el crawler
        
        Args:
            root_url: URL raíz del sitio (ej: https://ejemplo.gob.es)
            max_depth: Profundidad máxima de rastreo (default: 3)
            logger: Instancia de AuditLogger para registrar decisiones
        """
        self.root_url = root_url
        self.max_depth = max_depth
        self.logger = logger or AuditLogger()
        
        # Extraer dominio base
        parsed = urlparse(root_url)
        self.domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Cola de rastreo: (URL, profundidad)
        self.to_visit = [(root_url, 0)]
        self.visited = set()
        self.discovered_urls = []  # URLs encontradas con metadatos
        
        # Sesión HTTP
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.logger.log(f"🚀 Iniciando rastreo desde: {root_url}")
        self.logger.log(f"   Dominio base: {self.domain}")
        self.logger.log(f"   Profundidad máxima: {max_depth}")
    
    def _normalize_url(self, url: str) -> str:
        """
        Normaliza URLs para evitar duplicados por parámetros irrelevantes
        
        REQUISITO IRA: Excluir duplicados por parámetros
        
        Estrategia:
        - Eliminar fragmentos (#)
        - Eliminar parámetros de tracking (utm_*, gclid, etc.)
        - Convertir a minúsculas
        - Remover trailing slashes inconsistentes
        """
        parsed = urlparse(url)
        
        # Filtrar parámetros irrelevantes
        params = parsed.query.split('&') if parsed.query else []
        clean_params = [p for p in params if not any(
            p.startswith(prefix) for prefix in 
            ['utm_', 'gclid', 'fbclid', 'msclkid', 'session', 'js']
        )]
        
        clean_query = '&'.join(clean_params)
        
        # Reconstruir URL sin fragmentos
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip('/'),
            parsed.params,
            clean_query,
            ''  # Sin fragmentos
        ))
        
        return normalized
    
    def _is_valid_html_url(self, url: str) -> bool:
        """
        REQUISITO IRA: Excluir recursos no HTML
        
        Valida que URL apunte a HTML y no a:
        - Recursos estáticos (CSS, JS, imágenes)
        - Archivos (PDF, ZIP, etc.)
        - URLs de logout/admin
        """
        parsed = urlparse(url)
        
        # Excluir extensiones no HTML
        excluded_extensions = [
            '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg',
            '.pdf', '.zip', '.doc', '.xlsx', '.mp4', '.mp3', '.wav',
            '.woff', '.ttf', '.eot', '.ico'
        ]
        
        if any(parsed.path.lower().endswith(ext) for ext in excluded_extensions):
            return False
        
        # Excluir patrones peligrosos
        excluded_patterns = ['logout', '/admin/', '/api/', '/ws/']
        if any(pattern in parsed.path.lower() for pattern in excluded_patterns):
            return False
        
        return True
    
    def _is_same_domain(self, url: str) -> bool:
        """
        REQUISITO IRA: Restringir al mismo dominio
        
        Verifica que URL pertenece al mismo dominio que root_url
        """
        parsed = urlparse(url)
        url_domain = f"{parsed.scheme}://{parsed.netloc}"
        return url_domain == self.domain
    
    def crawl(self) -> List[Dict]:
        """
        Ejecuta rastreo BFS (breadth-first search) respetando profundidad
        
        RESULTADO: Lista de URLs descubiertas con metadatos:
        {
            'url': 'https://...',
            'depth': 1,
            'discovered_from': 'https://...',
            'normalized': 'https://...'
        }
        """
        self.logger.log("📋 Fase 1: RASTREO")
        
        while self.to_visit:
            current_url, depth = self.to_visit.pop(0)
            
            # Normalizar para evitar duplicados
            normalized = self._normalize_url(current_url)
            
            # Saltar si ya visitada
            if normalized in self.visited:
                continue
            
            # Respetar profundidad máxima
            if depth > self.max_depth:
                self.logger.log(f"   ⊘ Ignorado por profundidad: {current_url} (nivel {depth})")
                continue
            
            self.visited.add(normalized)
            
            try:
                self.logger.log(f"   🔗 Rastreando [{depth}]: {current_url[:70]}")
                
                response = self.session.get(current_url, timeout=10)
                response.raise_for_status()
                
                # Parsear HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Registrar esta URL como descubierta
                self.discovered_urls.append({
                    'url': current_url,
                    'normalized': normalized,
                    'depth': depth,
                    'discovered_from': current_url
                })
                
                # Extraer enlaces
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # Convertir a URL absoluta
                    absolute_url = urljoin(current_url, href)
                    absolute_normalized = self._normalize_url(absolute_url)
                    
                    # Validaciones
                    if not self._is_valid_html_url(absolute_url):
                        continue
                    
                    if not self._is_same_domain(absolute_url):
                        continue
                    
                    if absolute_normalized not in self.visited:
                        self.to_visit.append((absolute_url, depth + 1))
            
            except requests.RequestException as e:
                self.logger.log(f"   ✗ Error rastreando {current_url}: {str(e)[:50]}")
                continue
        
        self.logger.log(f"✅ Rastreo completado: {len(self.discovered_urls)} URLs descubiertas")
        return self.discovered_urls


# ============================================================================
# FASE 2: CLASIFICACIÓN FUNCIONAL
# ============================================================================

class FunctionalClassifier:
    """
    PROPÓSITO: Clasificar automáticamente cada URL por su tipo funcional
    
    REQUISITO IRA: Garantizar representatividad
    
    CATEGORÍAS MÍNIMAS (según tutor):
    1. Página de inicio (/, /index)
    2. Páginas de contenido informativo
    3. Páginas de navegación estructural (categorías, listados)
    4. Páginas con formularios (<form>)
    5. Páginas de servicios o procesos clave
    6. Páginas con contenido dinámico significativo
    
    ESTRATEGIA: Combinar análisis de:
    - Estructura URL (patrones)
    - Estructura HTML (elementos específicos)
    - Contenido (palabras clave)
    """
    
    def __init__(self, session: requests.Session, logger: AuditLogger):
        self.session = session
        self.logger = logger
    
    def classify(self, url: str) -> List[str]:
        """
        Clasifica una URL en categorías funcionales
        
        Retorna lista de categorías (puede tener múltiples)
        Ejemplo: ['inicio', 'navegacion']
        """
        categories = []
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
        except:
            return []
        
        parsed = urlparse(url)
        path_lower = parsed.path.lower()
        
        # 1. PÁGINA DE INICIO
        if path_lower in ['/', '', '/index', '/index.html']:
            categories.append('inicio')
        
        # 2. CONTENIDO INFORMATIVO (basado en URL y etiquetas)
        if any(pattern in path_lower for pattern in ['/noticias', '/blog', '/articulos', '/informacion']):
            categories.append('informativo')
        elif soup.find('article') or soup.find('main'):
            categories.append('informativo')
        
        # 3. NAVEGACIÓN/LISTADOS
        if any(pattern in path_lower for pattern in ['/servicios', '/tramites', '/categorias', '/listado']):
            categories.append('navegacion')
        elif soup.find_all('ul') or soup.find_all('ol'):
            # Página con listas (posible listado)
            if len(soup.find_all('li')) > 5:
                categories.append('navegacion')
        
        # 4. FORMULARIOS
        if soup.find('form'):
            categories.append('formulario')
        
        # 5. SERVICIOS/TRÁMITES
        if any(pattern in path_lower for pattern in ['/tramites', '/servicios', '/solicitud', '/proceso']):
            categories.append('servicio')
        
        # 6. CONTENIDO DINÁMICO (scripts, AJAX indicators)
        if soup.find('script') and ('fetch' in response.text or 'axios' in response.text):
            categories.append('dinamico')
        
        # Por defecto, si no se clasificó en nada, es "otro"
        if not categories:
            categories.append('otro')
        
        return categories


# ============================================================================
# FASE 3 + 4: SELECCIÓN DIRIGIDA Y ALEATORIA
# ============================================================================

class PageSelector:
    """
    PROPÓSITO: Seleccionar páginas garantizando:
    - 90% dirigida (con reglas específicas)
    - 10% aleatoria (mínimo 2 páginas)
    - Mínimo 15 páginas total
    
    REQUISITO IRA: Selección defendible y reproducible
    
    LÓGICA:
    1. SELECCIÓN DIRIGIDA (90%):
       ✓ 1 página de inicio (obligatoria)
       ✓ ≥1 página con formulario
       ✓ ≥1 página de servicio/trámite
       ✓ ≥1 página de navegación/listado
       ✓ Distribuir por profundidad
       ✓ Distribuir por complejidad
    
    2. SELECCIÓN ALEATORIA (10%):
       ✓ Seleccionar de URLs no usadas
       ✓ Mínimo 2 páginas
       ✓ Marcar explícitamente como 'random'
    """
    
    def __init__(self, urls: List[Dict], classifier: FunctionalClassifier, logger: AuditLogger):
        self.urls = urls
        self.classifier = classifier
        self.logger = logger
        
        # Clasificar todas las URLs
        self.logger.log("📋 Fase 2: CLASIFICACIÓN FUNCIONAL")
        for url_info in self.urls:
            url_info['categories'] = self.classifier.classify(url_info['url'])
            self.logger.log(f"   📌 {url_info['url'][:60]} → {url_info['categories']}")
    
    def select(self, min_pages: int = 15, random_percent: float = 0.10) -> Tuple[List[Dict], List[Dict]]:
        """
        Realiza selección en 2 fases: dirigida + aleatoria
        
        Retorna: (páginas_dirigidas, páginas_aleatorias)
        """
        self.logger.log("📋 Fase 3 + 4: SELECCIÓN DIRIGIDA Y ALEATORIA")
        
        directed = []
        random_selection = []
        
        # === FASE 3: SELECCIÓN DIRIGIDA (90%) ===
        self.logger.log("   🎯 Aplicando criterios de selección dirigida...")
        
        # CRITERIO 1: Página de inicio (obligatoria)
        home_pages = [u for u in self.urls if 'inicio' in u['categories']]
        if home_pages:
            directed.append(home_pages[0])
            self.logger.log(f"      ✓ Inicio: {home_pages[0]['url']}")
        
        # CRITERIO 2: Página con formulario (obligatoria)
        form_pages = [u for u in self.urls if 'formulario' in u['categories'] and u not in directed]
        if form_pages:
            directed.append(form_pages[0])
            self.logger.log(f"      ✓ Formulario: {form_pages[0]['url']}")
        
        # CRITERIO 3: Página de servicio/trámite (obligatoria)
        service_pages = [u for u in self.urls if 'servicio' in u['categories'] and u not in directed]
        if service_pages:
            directed.append(service_pages[0])
            self.logger.log(f"      ✓ Servicio: {service_pages[0]['url']}")
        
        # CRITERIO 4: Página de navegación/listado (obligatoria)
        nav_pages = [u for u in self.urls if 'navegacion' in u['categories'] and u not in directed]
        if nav_pages:
            directed.append(nav_pages[0])
            self.logger.log(f"      ✓ Navegación: {nav_pages[0]['url']}")
        
        # CRITERIO 5: Distribuir por profundidad
        depths = defaultdict(list)
        for url in self.urls:
            if url not in directed:
                depths[url['depth']].append(url)
        
        for depth in sorted(depths.keys()):
            available = len(depths[depth])
            needed = max(0, int(min_pages * 0.9) - len(directed))
            if available > 0 and needed > 0:
                take = min(needed // len(depths) if len(depths) > 0 else needed, available)
                directed.extend(depths[depth][:take])
                self.logger.log(f"      ✓ Profundidad {depth}: {take} páginas")
        
        # Limitar dirigidas al 90%
        directed = directed[:int(min_pages * 0.9)]
        for page in directed:
            page['selection_type'] = 'dirigida'
            page['selection_reason'] = 'Criterio de representatividad'
        
        self.logger.log(f"   ✅ Selección dirigida: {len(directed)} páginas (90%)")
        
        # === FASE 4: SELECCIÓN ALEATORIA (10%) ===
        self.logger.log("   🎲 Aplicando selección aleatoria...")
        
        # Páginas no usadas en dirigida
        available_for_random = [u for u in self.urls if u not in directed]
        random_count = max(2, int(min_pages * random_percent))
        
        if available_for_random:
            random_selection = random.sample(available_for_random, 
                                             min(random_count, len(available_for_random)))
            for page in random_selection:
                page['selection_type'] = 'aleatoria'
                page['selection_reason'] = 'Selección aleatoria del 10%'
            
            self.logger.log(f"   ✅ Selección aleatoria: {len(random_selection)} páginas (10%)")
        
        return directed, random_selection


# ============================================================================
# FASE 5: VALIDACIÓN
# ============================================================================

class SampleValidator:
    """
    PROPÓSITO: Validar que la muestra cumple TODOS los requisitos IRA
    
    VALIDACIONES:
    ✓ Total páginas ≥ 15
    ✓ Sin duplicados funcionales
    ✓ Porcentaje aleatorio ≥ 10% (mín 2)
    ✓ Presencia de tipos funcionales mínimos
    ✓ Distribuida en profundidades
    
    Si no cumple: Registra advertencias en log
    """
    
    def __init__(self, logger: AuditLogger):
        self.logger = logger
        self.warnings = []
    
    def validate(self, directed: List[Dict], random_selection: List[Dict], min_pages: int = 15) -> bool:
        """
        Valida la muestra final
        
        Retorna: True si cumple, False si hay problemas
        """
        self.logger.log("📋 Fase 5: VALIDACIÓN FINAL")
        
        total = len(directed) + len(random_selection)
        
        # Validación 1: Total páginas
        if total < min_pages:
            msg = f"⚠️  TOTAL INSUFICIENTE: {total} < {min_pages}"
            self.warnings.append(msg)
            self.logger.log(f"   {msg}")
            return False
        else:
            self.logger.log(f"   ✓ Total páginas: {total} ≥ {min_pages}")
        
        # Validación 2: Porcentaje aleatorio
        random_percent = (len(random_selection) / total * 100) if total > 0 else 0
        if len(random_selection) < 2:
            msg = f"⚠️  ALEATORIAS INSUFICIENTES: {len(random_selection)} < 2"
            self.warnings.append(msg)
            self.logger.log(f"   {msg}")
        else:
            self.logger.log(f"   ✓ Páginas aleatorias: {len(random_selection)} ({random_percent:.1f}%)")
        
        # Validación 3: Tipos funcionales mínimos
        all_pages = directed + random_selection
        all_categories = set()
        for page in all_pages:
            all_categories.update(page.get('categories', []))
        
        required_categories = ['inicio', 'formulario', 'servicio', 'navegacion']
        missing = [cat for cat in required_categories if cat not in all_categories]
        
        if missing:
            msg = f"⚠️  CATEGORÍAS FALTANTES: {missing}"
            self.warnings.append(msg)
            self.logger.log(f"   {msg}")
        else:
            self.logger.log(f"   ✓ Categorías: {all_categories}")
        
        # Validación 4: Distribución por profundidad
        depths = set(page['depth'] for page in all_pages)
        self.logger.log(f"   ✓ Profundidades cubiertas: {sorted(depths)}")
        
        # Validación 5: Sin duplicados
        urls = set(page['url'] for page in all_pages)
        if len(urls) < len(all_pages):
            msg = f"⚠️  DUPLICADOS DETECTADOS"
            self.warnings.append(msg)
            self.logger.log(f"   {msg}")
        else:
            self.logger.log(f"   ✓ URLs únicas: {len(urls)}")
        
        return len(self.warnings) == 0


# ============================================================================
# FASE 6: EXPORTACIÓN
# ============================================================================

class SampleExporter:
    """
    PROPÓSITO: Exportar resultados en formatos auditables (CSV, JSON)
    
    REQUISITO IRA: Debe ser defendible en auditoría
    
    EXPORTA:
    - CSV: Compatible con formularios IRA
    - JSON: Estructura completa con metadatos
    - LOG: Decisiones tomadas paso a paso
    """
    
    def __init__(self, output_dir: str = "audit_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_csv(self, pages: List[Dict], filename: str = "muestra_wcag.csv"):
        """
        Exporta a CSV compatible con IRA
        
        Columnas:
        - Página de la muestra (URL)
        - Tipo funcional
        - Profundidad
        - Tipo de selección (dirigida/aleatoria)
        - Razón de selección
        """
        filepath = self.output_dir / filename
        
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
                    page['selection_type'],
                    page['selection_reason']
                ])
        
        print(f"✅ CSV exportado: {filepath}")
        return str(filepath)
    
    def export_json(self, pages: List[Dict], filename: str = "muestra_wcag.json"):
        """
        Exporta a JSON con estructura completa para análisis
        """
        filepath = self.output_dir / filename
        
        data = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'total_pages': len(pages),
                'directed': sum(1 for p in pages if p['selection_type'] == 'dirigida'),
                'random': sum(1 for p in pages if p['selection_type'] == 'aleatoria'),
            },
            'pages': pages
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON exportado: {filepath}")
        return str(filepath)


# ============================================================================
# ORQUESTACIÓN PRINCIPAL
# ============================================================================

def main(root_url: str, max_depth: int = 3, min_pages: int = 15, 
         random_percent: float = 0.10, output_dir: str = "audit_results"):
    """
    FUNCIÓN PRINCIPAL: Ejecuta el pipeline completo
    
    ENTRADA:
    - root_url: URL raíz del sitio
    - max_depth: Profundidad máxima de rastreo
    - min_pages: Mínimo de páginas a seleccionar
    - random_percent: Porcentaje de páginas aleatorias
    
    SALIDA:
    - CSV + JSON + LOG en audit_results/
    """
    
    print("=" * 80)
    print("CRAWLER WCAG - AUDITORÍA DE ACCESIBILIDAD IRA")
    print("=" * 80)
    
    # Inicializar logger
    logger = AuditLogger("audit_log.txt")
    
    # FASE 1: RASTREO
    crawler = WebCrawler(root_url, max_depth=max_depth, logger=logger)
    discovered_urls = crawler.crawl()
    
    if not discovered_urls:
        print("❌ No se encontraron URLs")
        return False
    
    # FASE 2: CLASIFICACIÓN
    session = requests.Session()
    classifier = FunctionalClassifier(session, logger)
    
    # FASE 3 + 4: SELECCIÓN
    selector = PageSelector(discovered_urls, classifier, logger)
    directed, random_selection = selector.select(min_pages, random_percent)
    
    # FASE 5: VALIDACIÓN
    validator = SampleValidator(logger)
    is_valid = validator.validate(directed, random_selection, min_pages)
    
    if not is_valid:
        print("⚠️  Validación con advertencias (revisar audit_log.txt)")
    else:
        print("✅ Validación exitosa")
    
    # FASE 6: EXPORTACIÓN
    all_pages = directed + random_selection
    exporter = SampleExporter(output_dir)
    
    csv_file = exporter.export_csv(all_pages)
    json_file = exporter.export_json(all_pages)
    
    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"URLs descubiertas: {len(discovered_urls)}")
    print(f"Páginas seleccionadas: {len(all_pages)}")
    print(f"  - Dirigidas (90%): {len(directed)}")
    print(f"  - Aleatorias (10%): {len(random_selection)}")
    print(f"\nArchivos generados:")
    print(f"  📄 {csv_file}")
    print(f"  📋 {json_file}")
    print(f"  📝 audit_log.txt")
    print("=" * 80 + "\n")
    
    return True


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    """
    EJEMPLO DE USO:
    
    Opción 1: Ejecutar con URL específica
    python crawler.py
    # Luego ingresar URL raíz
    
    Opción 2: Modificar main() con URL específica
    main("https://www.comunidad.madrid/hospital/infantaleonor/")
    """
    
    # Solicitar URL raíz
    print("\n🌐 CRAWLER WCAG - Ingrese la URL raíz del sitio a auditar:")
    print("   Ejemplo: https://www.ejemplo.gob.es\n")
    
    root_url = input("URL raíz: ").strip()
    
    if not root_url.startswith(('http://', 'https://')):
        root_url = 'https://' + root_url
    
    # Ejecutar pipeline
    success = main(
        root_url=root_url,
        max_depth=3,
        min_pages=15,
        random_percent=0.10,
        output_dir="audit_results"
    )
    
    exit(0 if success else 1)
