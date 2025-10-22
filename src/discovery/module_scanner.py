"""
Escaneo y descubrimiento de módulos Odoo en el filesystem.
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class OdooModule:
    """Representa un módulo de Odoo con sus metadatos."""

    name: str
    path: str
    version: str
    depends: List[str]
    description: str
    author: str
    category: str
    installable: bool = True
    auto_install: bool = False

    def to_dict(self) -> Dict:
        """Convierte el módulo a diccionario."""
        return asdict(self)


class ModuleScanner:
    """Escáner de módulos Odoo."""

    MANIFEST_FILES = ["__manifest__.py", "__openerp__.py"]

    def __init__(self, root_path: Path):
        """
        Inicializa el escáner.

        Args:
            root_path: Ruta raíz donde buscar módulos
        """
        self.root_path = Path(root_path)
        if not self.root_path.exists():
            raise ValueError(f"La ruta {root_path} no existe")

    def scan(self) -> List[OdooModule]:
        """
        Escanea el directorio en busca de módulos Odoo.

        Returns:
            Lista de módulos encontrados
        """
        modules = []

        for path in self.root_path.rglob("*"):
            if not path.is_dir():
                continue

            # Verificar si contiene un manifest
            manifest = self._find_manifest(path)
            if manifest:
                try:
                    module = self._parse_module(path, manifest)
                    if module:
                        modules.append(module)
                except Exception as e:
                    print(f"Error procesando módulo en {path}: {e}")

        return modules

    def _find_manifest(self, module_path: Path) -> Optional[Path]:
        """
        Busca el archivo manifest en el directorio.

        Args:
            module_path: Ruta del módulo

        Returns:
            Ruta al manifest o None si no existe
        """
        for manifest_name in self.MANIFEST_FILES:
            manifest_path = module_path / manifest_name
            if manifest_path.exists():
                return manifest_path
        return None

    def _parse_module(
        self, module_path: Path, manifest_path: Path
    ) -> Optional[OdooModule]:
        """
        Parsea el manifest y crea un objeto OdooModule.

        Args:
            module_path: Ruta del módulo
            manifest_path: Ruta al archivo manifest

        Returns:
            OdooModule o None si hay error
        """
        try:
            # Leer y evaluar el manifest (eval seguro en contexto controlado)
            manifest_content = manifest_path.read_text(encoding="utf-8")
            manifest_data = self._safe_eval_manifest(manifest_content)

            if not isinstance(manifest_data, dict):
                return None

            return OdooModule(
                name=module_path.name,
                path=str(module_path.absolute()),
                version=manifest_data.get("version", "1.0"),
                depends=manifest_data.get("depends", []),
                description=manifest_data.get("summary", "")
                or manifest_data.get("description", ""),
                author=manifest_data.get("author", ""),
                category=manifest_data.get("category", "Uncategorized"),
                installable=manifest_data.get("installable", True),
                auto_install=manifest_data.get("auto_install", False),
            )

        except Exception as e:
            print(f"Error parseando manifest {manifest_path}: {e}")
            return None

    def _safe_eval_manifest(self, content: str) -> Dict:
        """
        Evalúa el contenido del manifest de forma segura.

        Args:
            content: Contenido del archivo

        Returns:
            Diccionario con datos del manifest
        """
        # Crear namespace limitado para eval
        namespace = {"__builtins__": {}}
        try:
            # Evaluar el contenido
            result = eval(content, namespace)
            return result if isinstance(result, dict) else {}
        except:
            return {}

    def export_to_json(self, modules: List[OdooModule], output_path: Path) -> None:
        """
        Exporta la lista de módulos a JSON.

        Args:
            modules: Lista de módulos
            output_path: Ruta de salida
        """
        data = [module.to_dict() for module in modules]
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_module_dependencies_graph(
        self, modules: List[OdooModule]
    ) -> Dict[str, List[str]]:
        """
        Genera un grafo de dependencias entre módulos.

        Args:
            modules: Lista de módulos

        Returns:
            Diccionario con dependencias por módulo
        """
        return {module.name: module.depends for module in modules}
