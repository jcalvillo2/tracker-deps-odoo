### Story 006 — Incremental Updates

**User Story**  
As a data engineer, I want the ETL to detect code changes and reprocess only modified files to optimize performance.

**Acceptance Criteria**  
- Detects changed or new files since last run.  
- Reprocesses only affected models or views.  
- Updates Neo4j incrementally.  

**Technical Tasks**  
- Use file hashes or modification timestamps.  
- Track ETL state in a metadata storage (e.g., SQLite, JSON).  
- Rebuild only the necessary graph elements.  

**Example Input/Output**  

**Input:**  
Modified files: ["models/sale_order.py", "views/sale_order_view.xml"]

**Output:**  

Reprocessed 2 items.
Updated relationships in Neo4j.