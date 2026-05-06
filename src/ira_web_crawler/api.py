from __future__ import annotations

import csv
import json
import math
import random
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


SERVICE_KEYWORDS = ("tramite", "tramites", "servicio", "servicios", "proceso", "solicitud")
NAV_KEYWORDS = ("categoria", "categorias", "listado", "buscar", "busqueda", "directorio")


@dataclass(slots=True)
class CandidatePage:
    url: str
    depth: int
    source_url: str | None
    categories: set[str] = field(default_factory=set)


@dataclass(slots=True)
class SelectedPage:
    url: str
    categories: list[str]
    depth: int
    selection: str
    random: bool
    source_url: str | None


@dataclass(slots=True)
class CrawlResult:
    root_url: str
    selected_pages: list[SelectedPage]
    candidate_count: int
    random_percentage_real: float
    logs: list[str]

    def to_dict(self) -> dict:
        return {
            "root_url": self.root_url,
            "candidate_count": self.candidate_count,
            "selected_pages": [asdict(page) for page in self.selected_pages],
            "random_percentage_real": self.random_percentage_real,
            "logs": self.logs,
        }


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="", query="")
    if cleaned.path == "":
        cleaned = cleaned._replace(path="/")
    return urlunparse(cleaned)


def _is_same_domain(root_netloc: str, url: str) -> bool:
    return urlparse(url).netloc == root_netloc


def _is_html_response(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    return "text/html" in content_type or "application/xhtml+xml" in content_type


def _excluded_by_patterns(url: str, exclusion_patterns: Iterable[str]) -> bool:
    for pattern in exclusion_patterns:
        if re.search(pattern, url, flags=re.IGNORECASE):
            return True
    return False


def _classify_page(url: str, soup: BeautifulSoup) -> set[str]:
    categories: set[str] = set()
    path = urlparse(url).path.lower()

    if path in ("", "/", "/index", "/index.html"):
        categories.add("home")

    if soup.find("form"):
        categories.add("form")

    if any(token in path for token in SERVICE_KEYWORDS):
        categories.add("service")

    link_count = len(soup.find_all("a", href=True))
    if link_count >= 20 or any(token in path for token in NAV_KEYWORDS):
        categories.add("navigation")

    script_count = len(soup.find_all("script"))
    if script_count >= 12 or soup.find(attrs={"data-reactroot": True}) or soup.find(attrs={"ng-app": True}):
        categories.add("dynamic")

    if not categories:
        categories.add("informative")

    return categories


def _extract_internal_links(base_url: str, soup: BeautifulSoup, root_netloc: str) -> set[str]:
    found: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        joined = _normalize_url(urljoin(base_url, a_tag["href"]))
        if _is_same_domain(root_netloc, joined):
            found.add(joined)
    return found


def _crawl(
    root_url: str,
    max_depth: int,
    timeout_seconds: int,
    exclusion_patterns: list[str],
    user_agent: str,
) -> tuple[dict[str, CandidatePage], list[str]]:
    logs: list[str] = []
    root_url = _normalize_url(root_url)
    root_netloc = urlparse(root_url).netloc
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    queue: deque[tuple[str, int, str | None]] = deque([(root_url, 0, None)])
    seen: set[str] = set()
    candidates: dict[str, CandidatePage] = {}

    while queue:
        url, depth, source_url = queue.popleft()
        if url in seen or depth > max_depth:
            continue
        if _excluded_by_patterns(url, exclusion_patterns):
            logs.append(f"Excluida por patrón: {url}")
            continue

        seen.add(url)
        try:
            response = session.get(url, timeout=timeout_seconds)
        except requests.RequestException as exc:
            logs.append(f"Error al solicitar {url}: {exc}")
            continue

        if response.status_code >= 400:
            logs.append(f"HTTP {response.status_code} en {url}")
            continue

        if not _is_html_response(response):
            logs.append(f"No HTML, descartada: {url}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        categories = _classify_page(url, soup)
        candidates[url] = CandidatePage(url=url, depth=depth, source_url=source_url, categories=categories)

        if depth < max_depth:
            for link in sorted(_extract_internal_links(url, soup, root_netloc)):
                if link not in seen:
                    queue.append((link, depth + 1, url))

    logs.append(f"Crawl finalizado con {len(candidates)} URLs HTML candidatas")
    return candidates, logs


def _pick_first_by_category(pages: list[CandidatePage], category: str, used: set[str]) -> CandidatePage | None:
    for page in pages:
        if page.url not in used and category in page.categories:
            return page
    return None


def _build_selection(candidates: dict[str, CandidatePage], min_pages: int, random_percent: int) -> tuple[list[SelectedPage], list[str]]:
    logs: list[str] = []
    pages = sorted(candidates.values(), key=lambda p: (p.depth, p.url))
    used: set[str] = set()
    selected: list[SelectedPage] = []

    min_random_by_percent = max(1, math.ceil(min_pages * (random_percent / 100)))
    max_random_by_90_rule = max(0, min_pages - math.ceil(min_pages * 0.9))
    random_target = max(min_random_by_percent, max_random_by_90_rule)
    directed_target = max(0, min_pages - random_target)

    required_categories = ("home", "form", "service", "navigation")
    for category in required_categories:
        page = _pick_first_by_category(pages, category, used)
        if page:
            used.add(page.url)
            selected.append(
                SelectedPage(
                    url=page.url,
                    categories=sorted(page.categories),
                    depth=page.depth,
                    selection="dirigida",
                    random=False,
                    source_url=page.source_url,
                )
            )
        else:
            logs.append(f"Advertencia: no se encontró página para categoría obligatoria '{category}'")

    seen_depths = {page.depth for page in selected}
    for page in pages:
        if len(selected) >= directed_target:
            break
        if page.url in used:
            continue
        if page.depth not in seen_depths:
            used.add(page.url)
            seen_depths.add(page.depth)
            selected.append(
                SelectedPage(
                    url=page.url,
                    categories=sorted(page.categories),
                    depth=page.depth,
                    selection="dirigida",
                    random=False,
                    source_url=page.source_url,
                )
            )

    for page in pages:
        if len(selected) >= directed_target:
            break
        if page.url in used:
            continue
        used.add(page.url)
        selected.append(
            SelectedPage(
                url=page.url,
                categories=sorted(page.categories),
                depth=page.depth,
                selection="dirigida",
                random=False,
                source_url=page.source_url,
            )
        )

    remaining = [page for page in pages if page.url not in used]
    if random_target > len(remaining):
        logs.append("Advertencia: no hay suficientes URLs restantes para cubrir el cupo aleatorio")
    random_take = min(random_target, len(remaining))
    for page in random.sample(remaining, k=random_take):
        used.add(page.url)
        selected.append(
            SelectedPage(
                url=page.url,
                categories=sorted(page.categories),
                depth=page.depth,
                selection="aleatoria",
                random=True,
                source_url=page.source_url,
            )
        )

    return selected, logs


def _validate_selection(selected: list[SelectedPage], min_pages: int, random_percent: int) -> list[str]:
    logs: list[str] = []
    unique_urls = {page.url for page in selected}

    if len(selected) < min_pages:
        logs.append(f"Advertencia: total de páginas insuficiente ({len(selected)}/{min_pages})")
    if len(unique_urls) != len(selected):
        logs.append("Advertencia: se detectaron URLs duplicadas en la selección final")

    random_count = sum(1 for page in selected if page.random)
    random_required = max(1, math.ceil(min_pages * (random_percent / 100)))
    if random_count < random_required:
        logs.append(f"Advertencia: porcentaje aleatorio insuficiente ({random_count}/{random_required})")

    required_categories = {"home", "form", "service", "navigation"}
    found_categories = {cat for page in selected for cat in page.categories}
    missing = sorted(required_categories - found_categories)
    if missing:
        logs.append(f"Advertencia: faltan categorías funcionales mínimas: {', '.join(missing)}")

    return logs


def export_json(result: CrawlResult, output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def export_csv(result: CrawlResult, output_path: str | Path) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["pagina_muestra", "url", "tipo_funcional", "profundidad", "seleccion", "random", "pagina_origen"],
        )
        writer.writeheader()
        for page in result.selected_pages:
            writer.writerow(
                {
                    "pagina_muestra": page.url,
                    "url": page.url,
                    "tipo_funcional": "|".join(page.categories),
                    "profundidad": page.depth,
                    "seleccion": page.selection,
                    "random": page.random,
                    "pagina_origen": page.source_url,
                }
            )


def crawl_and_select(
    root_url: str,
    max_depth: int = 3,
    min_pages: int = 15,
    random_percent: int = 10,
    exclusion_patterns: list[str] | None = None,
    timeout_seconds: int = 10,
    user_agent: str = "ira-web-crawler/0.1",
) -> CrawlResult:
    patterns = exclusion_patterns or [r"logout", r"track", r"utm_", r"\.(jpg|jpeg|png|gif|webp|svg|css|js|pdf)$"]
    candidates, crawl_logs = _crawl(
        root_url=root_url,
        max_depth=max_depth,
        timeout_seconds=timeout_seconds,
        exclusion_patterns=patterns,
        user_agent=user_agent,
    )

    selected, selection_logs = _build_selection(candidates, min_pages=min_pages, random_percent=random_percent)
    validation_logs = _validate_selection(selected, min_pages=min_pages, random_percent=random_percent)

    random_count = sum(1 for page in selected if page.random)
    random_percentage_real = (random_count / len(selected) * 100) if selected else 0.0
    logs = [
        *crawl_logs,
        *selection_logs,
        *validation_logs,
        f"Páginas seleccionadas: {len(selected)}",
        f"Porcentaje aleatorio real: {random_percentage_real:.2f}%",
    ]

    return CrawlResult(
        root_url=_normalize_url(root_url),
        selected_pages=selected,
        candidate_count=len(candidates),
        random_percentage_real=random_percentage_real,
        logs=logs,
    )
