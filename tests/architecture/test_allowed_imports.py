import sys
from collections.abc import Callable
from typing import Final

import grimp
import pytest

ROOT: Final = "voice_bridge"
FEATURES: Final = f"{ROOT}.features"
LIBRARIES: Final = f"{ROOT}.libraries"
LANGUAGE_EXTENSIONS: Final = frozenset[str]()


@pytest.fixture(scope="module")
def graph() -> grimp.ImportGraph:
    return grimp.build_graph(ROOT, include_external_packages=True, cache_dir=None)


def _within(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def _feature(module: str) -> str:
    return ".".join(module.split(".")[:3])


def _ability(module: str) -> str:
    return ".".join(module.split(".")[:5])


def _kind(module: str) -> str | None:
    if not _within(module, FEATURES):
        return None
    parts = module.split(".")
    if len(parts) > 3 and parts[3] == "domain":
        return "feature domain"
    if len(parts) > 5 and parts[3] == "abilities":
        return f"ability {parts[5]}"
    return None


def _modules_of(graph: grimp.ImportGraph, kind: str) -> list[str]:
    return sorted(module for module in graph.modules if _kind(module) == kind)


def _is_standard_or_extension(imported: str) -> bool:
    top = imported.split(".", maxsplit=1)[0]
    return top in sys.stdlib_module_names or top in LANGUAGE_EXTENSIONS


def _feature_domain_may_import(importer: str, imported: str) -> bool:
    return _is_standard_or_extension(imported) or _within(imported, f"{_feature(importer)}.domain")


def _ability_domain_may_import(importer: str, imported: str) -> bool:
    return _feature_domain_may_import(importer, imported) or _within(imported, f"{_ability(importer)}.domain")


def _ability_implementation_may_import(importer: str, imported: str) -> bool:
    feature = _feature(importer)
    return (
        not _within(imported, ROOT)
        or _within(imported, _ability(importer))
        or _within(imported, f"{feature}.domain")
        or _within(imported, f"{feature}.implementation")
        or _within(imported, LIBRARIES)
    )


def _forbidden_imports(graph: grimp.ImportGraph, kind: str, may_import: Callable[[str, str], bool]) -> str:
    return "\n".join(
        f"{importer} -> {imported}"
        for importer in _modules_of(graph, kind)
        for imported in sorted(graph.find_modules_directly_imported_by(importer))
        if not may_import(importer, imported)
    )


def test_the_rules_find_feature_domains_ability_domains_and_ability_implementations(graph: grimp.ImportGraph) -> None:
    assert _modules_of(graph, "feature domain")
    assert _modules_of(graph, "ability domain")
    assert _modules_of(graph, "ability implementation")


def test_a_feature_domain_imports_only_the_standard_library_and_language_extensions(graph: grimp.ImportGraph) -> None:
    forbidden = _forbidden_imports(graph, "feature domain", _feature_domain_may_import)
    assert not forbidden, forbidden


def test_an_ability_domain_imports_only_what_a_feature_domain_may_and_its_own_feature_domain(
    graph: grimp.ImportGraph,
) -> None:
    forbidden = _forbidden_imports(graph, "ability domain", _ability_domain_may_import)
    assert not forbidden, forbidden


def test_an_ability_implementation_imports_only_its_ability_its_feature_libraries_and_outside_packages(
    graph: grimp.ImportGraph,
) -> None:
    forbidden = _forbidden_imports(graph, "ability implementation", _ability_implementation_may_import)
    assert not forbidden, forbidden
