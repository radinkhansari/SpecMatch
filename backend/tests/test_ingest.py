import os
import tempfile

from app.core.db import get_conn
from app.services.ingest import run_ingest


def test_run_ingest_is_idempotent_for_records():
    previous_data_dir = os.environ.get("DATA_DIR")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATA_DIR"] = tmp
        conn = get_conn()
        try:
            run_ingest(conn)
            run_ingest(conn)

            record_count = conn.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]

            assert record_count == 150
        finally:
            conn.close()
            if previous_data_dir is None:
                os.environ.pop("DATA_DIR", None)
            else:
                os.environ["DATA_DIR"] = previous_data_dir
