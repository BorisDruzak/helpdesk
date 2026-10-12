import importlib.util
from pathlib import Path
import pytest


@pytest.mark.no_db
def test_tool_run_upgrade_reuses_module_columns_and_preserves_existing_rows():
    path = Path(__file__).parents[1] / "app/db/migrations/versions/20261012_148_endpoint_tool_runs.py"
    assert path.exists()
    spec = importlib.util.spec_from_file_location("tool_run_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "148" and module.down_revision == "147"
    class Recorder:
        def __init__(self): self.columns = []; self.tables = []
        def add_column(self, table, column): self.columns.append((table, column.name))
        def create_table(self, table, *args): self.tables.append(table)
        def create_index(self, *args, **kwargs): pass
        def drop_constraint(self, *args, **kwargs): pass
        def create_check_constraint(self, *args, **kwargs): pass
    recorder = Recorder()
    module.op = recorder
    module.upgrade()
    assert recorder.columns == [("endpoint_operation_links", "context_profile"), ("endpoint_operation_links", "endpoint_collection_ref")]
    assert recorder.tables == ["endpoint_tool_runs"]
    with pytest.raises(RuntimeError): module.downgrade()
