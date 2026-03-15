## 2024-03-12 - Optimize get_topics_from_articles database query
**Learning:** Found a performance bottleneck where a list of unique array topics was constructed via nested Python loops after pulling full records from PostgreSQL instead of letting PostgreSQL `unnest` do the lifting.
**Action:** When working with PostgreSQL ARRAY columns in SQLAlchemy, prefer `func.unnest(Column).label("...")` combined with `.distinct()` inside the database query to reduce the Python application memory footprint and parsing overhead.

## 2026-03-15 - Optimize get API queries post-filtering
**Learning:** Found a severe "N+1 query" like bottleneck where all matching articles were being loaded into Python memory before paginating if a 'topic' or 'search' parameter was provided. This occurs because filtering against ARRAY columns or multiple OR conditions wasn't pushed down to SQLAlchemy.
**Action:** When filtering paginated lists against PostgreSQL ARRAY columns (like topics or entities), push the filtering to the DB layer using an `EXISTS` subquery around `func.unnest(column)`. For multi-column search, use a combined `or_` with `ilike`. This ensures pagination handles only matched counts without dragging huge payloads into the Python runtime.
