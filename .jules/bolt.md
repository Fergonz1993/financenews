## 2026-03-12 - Optimize get_topics_from_articles database query
**Learning:** Found a performance bottleneck where a list of unique array topics was constructed via nested Python loops after pulling full records from PostgreSQL instead of letting PostgreSQL `unnest` do the lifting.
**Action:** When working with PostgreSQL ARRAY columns in SQLAlchemy, prefer `func.unnest(Column).label("...")` combined with `.distinct()` inside the database query to reduce the Python application memory footprint and parsing overhead.
