"""
Parser de vistas XML de Odoo.
"""
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from lxml import etree


@dataclass
class OdooView:
    """Representa una vista de Odoo."""

    xml_id: str  # ID externo (module.view_id)
    name: str
    model: str  # Modelo al que aplica la vista
    view_type: str  # form, tree, kanban, etc.
    inherit_id: Optional[str]  # Vista que extiende
    module: str
    file_path: str
    priority: int = 16
    arch: str = ""  # Estructura XML de la vista

    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return asdict(self)

    @property
    def is_extension(self) -> bool:
        """Determina si es una extensión de otra vista."""
        return self.inherit_id is not None


class ViewParser:
    """Parser de vistas XML de Odoo."""

    def __init__(self, module_name: str):
        """
        Inicializa el parser.

        Args:
            module_name: Nombre del módulo Odoo
        """
        self.module_name = module_name
        self.views: List[OdooView] = []

    def parse_file(self, file_path: Path) -> List[OdooView]:
        """
        Parsea un archivo XML buscando definiciones de vistas.

        Args:
            file_path: Ruta al archivo XML

        Returns:
            Lista de vistas encontradas
        """
        try:
            tree = etree.parse(str(file_path))
            root = tree.getroot()

            views = []

            # Buscar todos los <record> con model="ir.ui.view"
            for record in root.xpath("//record[@model='ir.ui.view']"):
                view = self._parse_view_record(record, file_path)
                if view:
                    views.append(view)

            return views

        except Exception as e:
            print(f"Error parseando XML {file_path}: {e}")
            return []

    def parse_directory(self, directory: Path) -> List[OdooView]:
        """
        Parsea todos los archivos XML en un directorio.

        Args:
            directory: Directorio a escanear

        Returns:
            Lista de todas las vistas encontradas
        """
        all_views = []

        # Buscar en subdirectorios comunes de vistas
        search_patterns = ["views/**/*.xml", "data/**/*.xml", "security/**/*.xml"]

        for pattern in search_patterns:
            for xml_file in directory.glob(pattern):
                if xml_file.is_file():
                    views = self.parse_file(xml_file)
                    all_views.extend(views)

        # También buscar en raíz
        for xml_file in directory.glob("*.xml"):
            if xml_file.is_file():
                views = self.parse_file(xml_file)
                all_views.extend(views)

        return all_views

    def _parse_view_record(
        self, record: etree.Element, file_path: Path
    ) -> Optional[OdooView]:
        """
        Parsea un <record> de vista.

        Args:
            record: Elemento XML del record
            file_path: Ruta del archivo

        Returns:
            OdooView o None
        """
        try:
            # Obtener ID del record
            xml_id = record.get("id")
            if not xml_id:
                return None

            # Construir ID completo (module.xml_id)
            full_xml_id = f"{self.module_name}.{xml_id}"

            # Extraer campos
            name = self._get_field_value(record, "name") or xml_id
            model = self._get_field_value(record, "model")
            view_type = self._get_field_value(record, "type") or "form"
            inherit_id = self._get_field_ref(record, "inherit_id")
            priority = self._get_field_value(record, "priority") or "16"
            arch = self._get_field_arch(record)

            # Validar campos requeridos
            if not model:
                return None

            return OdooView(
                xml_id=full_xml_id,
                name=name,
                model=model,
                view_type=view_type,
                inherit_id=inherit_id,
                module=self.module_name,
                file_path=str(file_path.absolute()),
                priority=int(priority) if priority.isdigit() else 16,
                arch=arch,
            )

        except Exception as e:
            print(f"Error parseando record de vista: {e}")
            return None

    def _get_field_value(self, record: etree.Element, field_name: str) -> Optional[str]:
        """
        Obtiene el valor de un campo <field name="...">valor</field>.

        Args:
            record: Elemento record
            field_name: Nombre del campo

        Returns:
            Valor del campo o None
        """
        field = record.find(f".//field[@name='{field_name}']")
        if field is not None:
            return field.text
        return None

    def _get_field_ref(self, record: etree.Element, field_name: str) -> Optional[str]:
        """
        Obtiene la referencia de un campo <field name="..." ref="..."/>.

        Args:
            record: Elemento record
            field_name: Nombre del campo

        Returns:
            Valor del atributo ref o None
        """
        field = record.find(f".//field[@name='{field_name}']")
        if field is not None:
            return field.get("ref")
        return None

    def _get_field_arch(self, record: etree.Element) -> str:
        """
        Obtiene el contenido del campo arch (estructura de la vista).

        Args:
            record: Elemento record

        Returns:
            Contenido XML del arch como string
        """
        arch_field = record.find(".//field[@name='arch']")
        if arch_field is not None:
            # Serializar el contenido interno
            content = []
            if arch_field.text:
                content.append(arch_field.text)
            for child in arch_field:
                content.append(etree.tostring(child, encoding="unicode"))
            return "".join(content)
        return ""

    def get_view_inheritance_graph(self, views: List[OdooView]) -> Dict[str, List[str]]:
        """
        Genera un grafo de herencia de vistas.

        Args:
            views: Lista de vistas

        Returns:
            Diccionario con herencias por vista
        """
        graph = {}
        for view in views:
            if view.inherit_id:
                if view.inherit_id not in graph:
                    graph[view.inherit_id] = []
                graph[view.inherit_id].append(view.xml_id)
        return graph

    def get_views_by_model(self, views: List[OdooView]) -> Dict[str, List[OdooView]]:
        """
        Agrupa vistas por modelo.

        Args:
            views: Lista de vistas

        Returns:
            Diccionario de vistas agrupadas por modelo
        """
        by_model = {}
        for view in views:
            if view.model not in by_model:
                by_model[view.model] = []
            by_model[view.model].append(view)
        return by_model
