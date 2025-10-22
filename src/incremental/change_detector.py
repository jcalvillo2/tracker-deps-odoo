"""
Detector de cambios en módulos Odoo.
"""
from pathlib import Path
from typing import Set, List, Dict
from .state_manager import StateManager


class ChangeDetector:
    """Detecta cambios en módulos Odoo para actualizaciones incrementales."""

    def __init__(self, state_manager: StateManager = None):
        """
        Inicializa el detector de cambios.

        Args:
            state_manager: Gestor de estado
        """
        self.state_manager = state_manager or StateManager()

    def detect_changed_modules(self, modules: List[Dict]) -> List[Dict]:
        """
        Detecta qué módulos han cambiado desde la última ejecución.

        Args:
            modules: Lista de módulos descubiertos

        Returns:
            Lista de módulos que han cambiado
        """
        changed_modules = []

        for module in modules:
            module_path = Path(module["path"])

            if self._has_module_changed(module_path):
                changed_modules.append(module)

        return changed_modules

    def _has_module_changed(self, module_path: Path) -> bool:
        """
        Verifica si un módulo ha cambiado.

        Args:
            module_path: Ruta al módulo

        Returns:
            True si el módulo cambió
        """
        # Recopilar todos los archivos relevantes del módulo
        relevant_files = self._get_relevant_files(module_path)

        # Verificar si algún archivo cambió
        changed_files = self.state_manager.get_changed_files(relevant_files)

        return len(changed_files) > 0

    def _get_relevant_files(self, module_path: Path) -> Set[Path]:
        """
        Obtiene todos los archivos relevantes de un módulo.

        Args:
            module_path: Ruta al módulo

        Returns:
            Conjunto de archivos relevantes
        """
        files = set()

        # Manifest
        for manifest in ["__manifest__.py", "__openerp__.py"]:
            manifest_path = module_path / manifest
            if manifest_path.exists():
                files.add(manifest_path)

        # Archivos Python
        for py_file in module_path.rglob("*.py"):
            if "__pycache__" not in str(py_file) and "test_" not in py_file.name:
                files.add(py_file)

        # Archivos XML
        for xml_file in module_path.rglob("*.xml"):
            files.add(xml_file)

        return files

    def get_changed_python_files(self, module_path: Path) -> Set[Path]:
        """
        Obtiene archivos Python que han cambiado en un módulo.

        Args:
            module_path: Ruta al módulo

        Returns:
            Conjunto de archivos Python modificados
        """
        py_files = set()
        for py_file in module_path.rglob("*.py"):
            if "__pycache__" not in str(py_file) and "test_" not in py_file.name:
                if self.state_manager.has_changed(py_file):
                    py_files.add(py_file)

        return py_files

    def get_changed_xml_files(self, module_path: Path) -> Set[Path]:
        """
        Obtiene archivos XML que han cambiado en un módulo.

        Args:
            module_path: Ruta al módulo

        Returns:
            Conjunto de archivos XML modificados
        """
        xml_files = set()
        for xml_file in module_path.rglob("*.xml"):
            if self.state_manager.has_changed(xml_file):
                xml_files.add(xml_file)

        return xml_files

    def mark_module_processed(self, module_path: Path):
        """
        Marca todos los archivos de un módulo como procesados.

        Args:
            module_path: Ruta al módulo
        """
        relevant_files = self._get_relevant_files(module_path)
        self.state_manager.mark_files_processed(relevant_files)

    def get_incremental_strategy(self, modules: List[Dict]) -> Dict:
        """
        Determina la estrategia de actualización incremental.

        Args:
            modules: Lista de todos los módulos

        Returns:
            Diccionario con estrategia:
                - full_reload: bool - si requiere carga completa
                - changed_modules: List - módulos a actualizar
                - reason: str - razón de la estrategia
        """
        # Si no hay estado previo, hacer carga completa
        if not self.state_manager.state.get("last_update"):
            return {
                "full_reload": True,
                "changed_modules": modules,
                "reason": "Primera ejecución - no hay estado previo",
            }

        # Detectar módulos cambiados
        changed_modules = self.detect_changed_modules(modules)

        # Si cambiaron más del 30% de módulos, puede ser más eficiente recargar todo
        change_ratio = len(changed_modules) / len(modules) if modules else 0

        if change_ratio > 0.3:
            return {
                "full_reload": True,
                "changed_modules": modules,
                "reason": f"Muchos cambios detectados ({change_ratio:.1%})",
            }

        # Actualización incremental
        return {
            "full_reload": False,
            "changed_modules": changed_modules,
            "reason": f"{len(changed_modules)} módulos modificados",
        }
