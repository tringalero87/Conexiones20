import os

if os.environ.get('DATABASE_URL'):
    from .postgres_dal import PostgresDAL as DataAccessLayer
else:
    from .sqlite_dal import SQLiteDAL as DataAccessLayer

dal = DataAccessLayer()
