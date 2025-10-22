### Story 005 — Querying Dependencies

**User Story**  
As a user, I want to query the graph to understand dependencies and inheritance so that I can trace where models or views originate.

**Acceptance Criteria**  
- Enables Cypher queries like:  
  - “Find all models inheriting from X.”  
  - “Find all views extending Y.”  
- Returns structured JSON results.  

**Technical Tasks**  
- Define query templates.  
- Create a lightweight query interface (REST or CLI).  
- Format results for downstream visualization.  

**Example Input/Output**  

**Input (Cypher):**  
MATCH (m:Model)-[:INHERITS]->(p:Model {name:"mail.thread"}) RETURN m.name;

**Output:**  
```json
["res.partner", "crm.lead", "sale.order"]
```