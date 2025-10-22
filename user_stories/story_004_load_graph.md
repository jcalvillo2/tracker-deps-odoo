### Story 004 — Build Graph Relationships in Neo4j

**User Story**  
As a developer, I want to load the parsed model and view data into Neo4j so that I can explore their dependency graph.

**Acceptance Criteria**  
- Creates nodes for each model and view.  
- Adds relationships:  
  - `(:Model)-[:INHERITS]->(:Model)`  
  - `(:View)-[:EXTENDS]->(:View)`  
  - `(:View)-[:DISPLAYS]->(:Model)`  
- Ensures idempotent loading (no duplicates).  

**Technical Tasks**  
- Connect to Neo4j using the Bolt driver.  
- Implement upsert logic.  
- Use batch inserts for performance.  

**Example Input/Output**  

**Input:**  

Model: res.partner
Inherits: mail.thread


**Output (Neo4j):**  

(:Model {name: "res.partner"})-[:INHERITS]->(:Model {name: "mail.thread"})