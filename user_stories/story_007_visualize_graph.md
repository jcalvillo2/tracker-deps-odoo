### Story 007 — Add CLI or Web UI to Visualize the Dependency Graph

**User Story**
As a user or data engineer, I want to visualize the Odoo dependency graph (models and views) through a CLI interface so that I can easily explore relationships, inheritance, and dependencies without directly querying Neo4j.

**Acceptance Criteria**

* Provides at least one visualization interface:

  * **CLI Mode**: prints relationships or dependency trees (text-based).

* Supports filtering by node type (`Model`, `View`, etc.).
* Supports searching for a specific model or view.
* Connects directly to the Neo4j instance and retrieves live data.
* Allows exporting the graph to an HTML file or image.
* Displays relationships such as in e.g:

  * `(:Model)-[:INHERITS]->(:Model)`
  * `(:View)-[:EXTENDS]->(:View)`
  * `(:View)-[:DISPLAYS]->(:Model)` 
  to name a few
* Code must be modular: a `GraphVisualizer` class or similar responsible for querying and rendering.


**Example Input/Output**

*Input (CLI)*:

```bash
python visualize_graph.py --type Model --search res.partner
```

*Output (CLI)*:

```
Model: res.partner
 ├── inherits: mail.thread
 ├── inherits: base.partner.mixin
 └── displayed in: view_partner_form
```

