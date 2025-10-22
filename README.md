# Tracker de Dependencias Odoo

Sistema ETL inteligente para analizar el código fuente de Odoo y representar sus dependencias de modelos y vistas en una base de datos de grafos (Neo4j).

## Características

- **Descubrimiento automático** de módulos Odoo
- **Parsing de modelos Python** con análisis AST completo
- **Parsing de vistas XML** con detección de herencia
- **Carga eficiente a Neo4j** con batch inserts e inserciones idempotentes
- **Actualizaciones incrementales** basadas en hashing de archivos
- **Motor de consultas** con queries predefinidas y personalizables
- **Visualización interactiva** del grafo de dependencias
- **CLI intuitivo** con Rich para mejor experiencia de usuario

## Arquitectura

```
tracker-deps-odoo/
├── src/
│   ├── discovery/          # Descubrimiento de módulos
│   │   └── module_scanner.py
│   ├── parsers/            # Parsers Python y XML
│   │   ├── model_parser.py
│   │   └── view_parser.py
│   ├── graph/              # Integración Neo4j
│   │   ├── schema.py
│   │   └── neo4j_loader.py
│   ├── incremental/        # Sistema de cambios
│   │   ├── state_manager.py
│   │   └── change_detector.py
│   ├── query/              # Motor de consultas
│   │   └── query_engine.py
│   └── visualization/      # Visualización
│       └── graph_visualizer.py
├── cli.py                  # Interfaz CLI
├── config.py               # Configuración
└── requirements.txt
```

## Instalación

### Requisitos

- Python 3.8+
- Neo4j 5.0+
- Pip

### Pasos

1. **Clonar el repositorio**

```bash
git clone <repo-url>
cd tracker-deps-odoo
```

2. **Instalar dependencias**

```bash
pip install -r requirements.txt
```

3. **Configurar Neo4j**

Inicia una instancia de Neo4j (local o remota). Puedes usar Docker:

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

4. **Configurar variables de entorno**

Copia el archivo de ejemplo y edita las credenciales:

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

Variables disponibles:
- `NEO4J_URI`: URI de conexión (default: `bolt://localhost:7687`)
- `NEO4J_USER`: Usuario (default: `neo4j`)
- `NEO4J_PASSWORD`: Contraseña
- `ODOO_SOURCE_PATH`: Ruta al código fuente de Odoo
- `BATCH_SIZE`: Tamaño de batch para cargas (default: 100)
- `MAX_WORKERS`: Workers para procesamiento paralelo (default: 4)

## Uso

### 1. Cargar código fuente de Odoo

```bash
# Carga completa
python cli.py load --source /path/to/odoo

# Carga incremental (solo archivos modificados)
python cli.py load --source /path/to/odoo

# Forzar carga completa
python cli.py load --source /path/to/odoo --full

# Limpiar y recargar
python cli.py load --source /path/to/odoo --clear
```

### 2. Consultas

#### Ver modelos que heredan de otro

```bash
python cli.py query model-children res.partner
```

#### Ver modelos padre

```bash
python cli.py query model-parents sale.order
```

#### Ver vistas de un modelo

```bash
python cli.py query model-views res.partner
```

#### Ver relaciones de campos

```bash
python cli.py query model-relations sale.order
```

#### Análisis de impacto

```bash
python cli.py query model-impact res.partner
```

#### Buscar modelos

```bash
python cli.py query search "sale"
```

### 3. Visualización

#### Jerarquía de herencia de un modelo

```bash
python cli.py visualize model-hierarchy res.partner --output hierarchy.html --depth 3
```

Abre `hierarchy.html` en tu navegador para ver la visualización interactiva.

#### Relaciones de campos

```bash
python cli.py visualize model-relations sale.order --output relations.html
```

#### Dependencias entre módulos

```bash
# Todos los módulos
python cli.py visualize module-deps --output deps.html

# Módulo específico
python cli.py visualize module-deps --module sale --output sale_deps.html
```

### 4. Estadísticas

```bash
python cli.py stats
```

### 5. Limpiar datos

```bash
python cli.py clear
```

## Modelo de Datos

### Nodos

1. **OdooModule**: Representa un módulo Odoo
   - Propiedades: `name`, `version`, `description`, `author`, `category`, `path`

2. **OdooModel**: Representa un modelo Python
   - Propiedades: `name`, `description`, `module`, `file_path`, `class_name`, `model_type`, `is_transient`

3. **OdooView**: Representa una vista XML
   - Propiedades: `xml_id`, `name`, `model`, `view_type`, `module`, `file_path`, `priority`

4. **OdooField**: Representa un campo de un modelo
   - Propiedades: `name`, `field_type`, `model`, `attributes`

### Relaciones

1. **DEPENDS_ON**: Módulo → Módulo (dependencias)
2. **CONTAINS_MODEL**: Módulo → Modelo
3. **CONTAINS_VIEW**: Módulo → Vista
4. **INHERITS**: Modelo → Modelo (herencia simple)
5. **INHERITS_DELEGATION**: Modelo → Modelo (herencia por delegación)
6. **HAS_FIELD**: Modelo → Campo
7. **RELATES_TO**: Campo → Modelo (campos relacionales)
8. **EXTENDS**: Vista → Vista (herencia de vistas)
9. **VIEW_FOR**: Vista → Modelo

## Ejemplos de Consultas Cypher

### Modelos más extendidos

```cypher
MATCH (child:OdooModel)-[:INHERITS]->(parent:OdooModel)
WITH parent, count(child) as children_count
ORDER BY children_count DESC
LIMIT 10
RETURN parent.name, children_count
```

### Módulos con más modelos

```cypher
MATCH (m:OdooModule)-[:CONTAINS_MODEL]->(model:OdooModel)
WITH m, count(model) as model_count
ORDER BY model_count DESC
LIMIT 10
RETURN m.name, model_count
```

### Cadena de dependencias de un módulo

```cypher
MATCH path = (m:OdooModule {name: 'sale'})-[:DEPENDS_ON*]->(dep:OdooModule)
RETURN path
```

### Modelos con más relaciones

```cypher
MATCH (m:OdooModel)-[:HAS_FIELD]->(f:OdooField)-[:RELATES_TO]->(target:OdooModel)
WITH m, count(DISTINCT target) as relations_count
ORDER BY relations_count DESC
LIMIT 10
RETURN m.name, m.module, relations_count
```

## Sistema de Actualizaciones Incrementales

El sistema detecta automáticamente qué archivos han cambiado desde la última ejecución:

1. **Primera ejecución**: Carga completa de todos los módulos
2. **Ejecuciones subsecuentes**: Solo procesa módulos con cambios
3. **Estrategia inteligente**: Si más del 30% de módulos cambiaron, hace carga completa

El estado se guarda en `.cache/state.json` con:
- Hash SHA256 de cada archivo procesado
- Timestamp de última actualización
- Metadatos de módulos

## Performance

### Optimizaciones implementadas

- **Batch inserts**: Carga en lotes configurables
- **Operaciones idempotentes**: MERGE en lugar de CREATE
- **Índices y constraints**: Búsquedas optimizadas
- **Parsing incremental**: Solo archivos modificados
- **Procesamiento paralelo**: Múltiples workers

### Benchmarks

En un repositorio Odoo Enterprise con ~200 módulos:

- **Carga completa inicial**: ~5-10 minutos
- **Actualización incremental**: ~30-60 segundos
- **Consultas simples**: <100ms
- **Visualizaciones**: ~1-3 segundos

## Desarrollo

### Estructura de clases

```python
# Discovery
ModuleScanner: Escanea directorios en busca de módulos
OdooModule: Representa un módulo

# Parsers
ModelParser: Parsea archivos Python usando AST
ViewParser: Parsea archivos XML con lxml
OdooModel, OdooView, OdooField: Modelos de datos

# Graph
GraphSchema: Define esquema del grafo
Neo4jLoader: Carga datos en Neo4j con batch processing

# Incremental
StateManager: Gestiona estado de archivos
ChangeDetector: Detecta cambios en módulos

# Query
QueryEngine: Motor de consultas predefinidas

# Visualization
GraphVisualizer: Genera visualizaciones con pyvis
```

### Testing

```bash
pytest
```

### Formateo

```bash
black .
```

## Casos de Uso

1. **Auditoría de código**: Entender dependencias antes de modificar
2. **Documentación**: Generar documentación visual de arquitectura
3. **Refactoring**: Identificar impacto de cambios
4. **Migración**: Planificar actualizaciones entre versiones
5. **Onboarding**: Ayudar a nuevos desarrolladores a entender el sistema
6. **Code review**: Validar que las dependencias sean correctas

## Limitaciones

- No detecta dependencias dinámicas (ej: `env['model.name']`)
- No analiza JavaScript
- Solo soporta Odoo 12+
- Requiere código fuente local

## Roadmap

- [ ] Soporte para análisis JavaScript
- [ ] Detección de dependencias dinámicas
- [ ] API REST para consultas
- [ ] Dashboard web interactivo
- [ ] Exportación a múltiples formatos (Gephi, D3.js)
- [ ] Análisis de complejidad y métricas de código
- [ ] Integración con CI/CD

## Contribuir

1. Fork del proyecto
2. Crea una rama para tu feature
3. Commit con mensajes descriptivos
4. Push a tu fork
5. Abre un Pull Request

## Licencia

MIT

## Autor

Sistema desarrollado siguiendo las mejores prácticas de ingeniería de software y arquitectura de datos.

## Soporte

Para reportar bugs o solicitar features, abre un issue en GitHub



