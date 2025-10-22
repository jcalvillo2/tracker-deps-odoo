"""
Gestión del estado para actualizaciones incrementales.
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Set
from datetime import datetime
from config import Config


class StateManager:
    """Gestiona el estado de archivos procesados."""

    def __init__(self, state_file: Path = None):
        """
        Inicializa el gestor de estado.

        Args:
            state_file: Ruta al archivo de estado
        """
        self.state_file = state_file or Config.STATE_FILE
        Config.ensure_cache_dir()
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """
        Carga el estado desde el archivo.

        Returns:
            Diccionario con el estado
        """
        if not self.state_file.exists():
            return {
                "last_update": None,
                "files": {},  # path -> hash
                "modules": {},  # module_name -> data
            }

        try:
            with open(self.state_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando estado: {e}")
            return {"last_update": None, "files": {}, "modules": {}}

    def save_state(self):
        """Guarda el estado actual al archivo."""
        self.state["last_update"] = datetime.now().isoformat()

        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_file_hash(self, file_path: Path) -> str:
        """
        Calcula el hash SHA256 de un archivo.

        Args:
            file_path: Ruta al archivo

        Returns:
            Hash del archivo
        """
        sha256 = hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Error calculando hash de {file_path}: {e}")
            return ""

    def has_changed(self, file_path: Path) -> bool:
        """
        Verifica si un archivo ha cambiado desde la última ejecución.

        Args:
            file_path: Ruta al archivo

        Returns:
            True si cambió o es nuevo
        """
        file_key = str(file_path.absolute())
        current_hash = self.get_file_hash(file_path)

        if not current_hash:
            return False

        previous_hash = self.state["files"].get(file_key)

        return previous_hash != current_hash

    def update_file(self, file_path: Path):
        """
        Actualiza el hash de un archivo en el estado.

        Args:
            file_path: Ruta al archivo
        """
        file_key = str(file_path.absolute())
        current_hash = self.get_file_hash(file_path)
        self.state["files"][file_key] = current_hash

    def get_changed_files(self, file_paths: Set[Path]) -> Set[Path]:
        """
        Obtiene la lista de archivos que han cambiado.

        Args:
            file_paths: Conjunto de rutas a verificar

        Returns:
            Conjunto de archivos que cambiaron
        """
        changed = set()

        for file_path in file_paths:
            if self.has_changed(file_path):
                changed.add(file_path)

        return changed

    def mark_files_processed(self, file_paths: Set[Path]):
        """
        Marca archivos como procesados actualizando sus hashes.

        Args:
            file_paths: Conjunto de archivos procesados
        """
        for file_path in file_paths:
            self.update_file(file_path)

    def get_module_state(self, module_name: str) -> Dict:
        """
        Obtiene el estado guardado de un módulo.

        Args:
            module_name: Nombre del módulo

        Returns:
            Estado del módulo
        """
        return self.state["modules"].get(module_name, {})

    def update_module_state(self, module_name: str, data: Dict):
        """
        Actualiza el estado de un módulo.

        Args:
            module_name: Nombre del módulo
            data: Datos del módulo
        """
        self.state["modules"][module_name] = data

    def clear_state(self):
        """Limpia todo el estado."""
        self.state = {"last_update": None, "files": {}, "modules": {}}
        if self.state_file.exists():
            self.state_file.unlink()
