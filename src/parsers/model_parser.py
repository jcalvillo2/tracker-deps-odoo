"""
Parser de modelos Python de Odoo usando análisis AST.
"""
import ast
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict, field


@dataclass
class OdooField:
    """Representa un campo de un modelo Odoo."""

    name: str
    field_type: str
    related_model: Optional[str] = None
    attributes: Dict = field(default_factory=dict)


@dataclass
class OdooModel:
    """Representa un modelo Odoo."""

    name: Optional[str]  # _name
    inherits: List[str]  # _inherit (puede ser lista o string)
    inherits_models: Dict[str, str]  # _inherits
    description: str
    fields: List[OdooField]
    module: str
    file_path: str
    class_name: str
    is_abstract: bool = False  # Sin _name
    is_extension: bool = False  # Solo tiene _inherit
    is_transient: bool = False

    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        data = asdict(self)
        data["fields"] = [f.__dict__ for f in self.fields]
        return data

    @property
    def model_type(self) -> str:
        """Determina el tipo de modelo según las convenciones Odoo."""
        if self.is_transient:
            return "transient"
        if not self.name:
            return "mixin"
        if self.inherits and self.name in self.inherits:
            return "extension"
        if self.inherits and self.name not in self.inherits:
            return "redefined"
        return "base"


class ModelParser:
    """Parser de modelos Odoo desde archivos Python."""

    # Tipos de campos relacionales
    RELATIONAL_FIELDS = {
        "Many2one",
        "One2many",
        "Many2many",
        "Reference",
    }

    def __init__(self, module_name: str):
        """
        Inicializa el parser.

        Args:
            module_name: Nombre del módulo Odoo
        """
        self.module_name = module_name
        self.models: List[OdooModel] = []

    def parse_file(self, file_path: Path) -> List[OdooModel]:
        """
        Parsea un archivo Python buscando modelos Odoo.

        Args:
            file_path: Ruta al archivo .py

        Returns:
            Lista de modelos encontrados
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            models = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    model = self._parse_class(node, file_path)
                    if model:
                        models.append(model)

            return models

        except Exception as e:
            print(f"Error parseando {file_path}: {e}")
            return []

    def parse_directory(self, directory: Path) -> List[OdooModel]:
        """
        Parsea todos los archivos Python en un directorio.

        Args:
            directory: Directorio a escanear

        Returns:
            Lista de todos los modelos encontrados
        """
        all_models = []

        for py_file in directory.rglob("*.py"):
            # Excluir archivos de test
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue

            models = self.parse_file(py_file)
            all_models.extend(models)

        return all_models

    def _parse_class(self, node: ast.ClassDef, file_path: Path) -> Optional[OdooModel]:
        """
        Parsea una clase buscando modelos Odoo.

        Args:
            node: Nodo AST de la clase
            file_path: Ruta del archivo

        Returns:
            OdooModel o None si no es un modelo válido
        """
        # Verificar si hereda de models.Model o models.TransientModel
        if not self._is_odoo_model(node):
            return None

        # Extraer atributos del modelo
        name = self._get_attribute(node, "_name")
        inherits = self._get_attribute(node, "_inherit") or []
        inherits_models = self._get_attribute(node, "_inherits") or {}
        description = self._get_attribute(node, "_description") or ""
        transient_model = self._get_attribute(node, "_transient") or False

        # Normalizar _inherit (puede ser string o lista)
        if isinstance(inherits, str):
            inherits = [inherits]

        # Detectar si es TransientModel por herencia de clase
        is_transient = transient_model or self._inherits_transient(node)

        # Parsear campos
        fields = self._parse_fields(node)

        # Determinar si es extensión (solo _inherit, sin _name)
        is_extension = bool(inherits) and not name

        # Si es extensión, usar el nombre heredado como referencia
        if is_extension and len(inherits) == 1:
            effective_name = inherits[0]
        else:
            effective_name = name

        return OdooModel(
            name=effective_name,
            inherits=inherits,
            inherits_models=inherits_models,
            description=description,
            fields=fields,
            module=self.module_name,
            file_path=str(file_path.absolute()),
            class_name=node.name,
            is_abstract=name is None,
            is_extension=is_extension,
            is_transient=is_transient,
        )

    def _is_odoo_model(self, node: ast.ClassDef) -> bool:
        """
        Verifica si una clase es un modelo Odoo.

        Args:
            node: Nodo de clase AST

        Returns:
            True si es modelo Odoo
        """
        for base in node.bases:
            # Buscar herencia de models.Model o models.TransientModel
            if isinstance(base, ast.Attribute):
                if (
                    isinstance(base.value, ast.Name)
                    and base.value.id == "models"
                    and base.attr in ("Model", "TransientModel", "AbstractModel")
                ):
                    return True

        return False

    def _inherits_transient(self, node: ast.ClassDef) -> bool:
        """Verifica si hereda de TransientModel."""
        for base in node.bases:
            if isinstance(base, ast.Attribute):
                if (
                    isinstance(base.value, ast.Name)
                    and base.value.id == "models"
                    and base.attr == "TransientModel"
                ):
                    return True
        return False

    def _get_attribute(self, node: ast.ClassDef, attr_name: str):
        """
        Obtiene el valor de un atributo de clase.

        Args:
            node: Nodo de clase
            attr_name: Nombre del atributo

        Returns:
            Valor del atributo o None
        """
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return self._eval_node(item.value)
        return None

    def _eval_node(self, node):
        """
        Evalúa un nodo AST de forma segura.

        Args:
            node: Nodo AST

        Returns:
            Valor evaluado
        """
        try:
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Str):  # Python < 3.8
                return node.s
            elif isinstance(node, ast.List):
                return [self._eval_node(n) for n in node.elts]
            elif isinstance(node, ast.Dict):
                return {
                    self._eval_node(k): self._eval_node(v)
                    for k, v in zip(node.keys, node.values)
                }
            elif isinstance(node, ast.Name):
                # Constantes conocidas
                if node.id == "True":
                    return True
                elif node.id == "False":
                    return False
                elif node.id == "None":
                    return None
        except:
            pass
        return None

    def _parse_fields(self, node: ast.ClassDef) -> List[OdooField]:
        """
        Extrae los campos definidos en el modelo.

        Args:
            node: Nodo de clase

        Returns:
            Lista de campos
        """
        fields = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field = self._parse_field_definition(target.id, item.value)
                        if field:
                            fields.append(field)

        return fields

    def _parse_field_definition(
        self, field_name: str, value_node
    ) -> Optional[OdooField]:
        """
        Parsea la definición de un campo.

        Args:
            field_name: Nombre del campo
            value_node: Nodo AST del valor

        Returns:
            OdooField o None
        """
        if not isinstance(value_node, ast.Call):
            return None

        # Obtener tipo de campo
        field_type = self._get_field_type(value_node)
        if not field_type:
            return None

        # Obtener modelo relacionado (para campos relacionales)
        related_model = None
        if field_type in self.RELATIONAL_FIELDS:
            related_model = self._get_related_model(value_node)

        # Extraer atributos adicionales
        attributes = self._extract_field_attributes(value_node)

        return OdooField(
            name=field_name,
            field_type=field_type,
            related_model=related_model,
            attributes=attributes,
        )

    def _get_field_type(self, call_node: ast.Call) -> Optional[str]:
        """Obtiene el tipo de campo desde el nodo Call."""
        if isinstance(call_node.func, ast.Attribute):
            if (
                isinstance(call_node.func.value, ast.Name)
                and call_node.func.value.id == "fields"
            ):
                return call_node.func.attr
        return None

    def _get_related_model(self, call_node: ast.Call) -> Optional[str]:
        """Obtiene el modelo relacionado de un campo relacional."""
        # Primer argumento posicional suele ser el comodel_name
        if call_node.args:
            first_arg = call_node.args[0]
            if isinstance(first_arg, (ast.Constant, ast.Str)):
                return self._eval_node(first_arg)

        # O puede estar en kwargs
        for keyword in call_node.keywords:
            if keyword.arg == "comodel_name":
                return self._eval_node(keyword.value)

        return None

    def _extract_field_attributes(self, call_node: ast.Call) -> Dict:
        """Extrae atributos de la definición del campo."""
        attributes = {}

        for keyword in call_node.keywords:
            if keyword.arg:
                value = self._eval_node(keyword.value)
                if value is not None:
                    attributes[keyword.arg] = value

        return attributes
