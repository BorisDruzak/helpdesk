"""Allow v4 scenarios; refuse a lossy downgrade."""
from alembic import op
from sqlalchemy import text

revision = "157"
down_revision = "156"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_studio_version_schema", "request_studio_scenario_versions", type_="check")
    op.create_check_constraint("ck_studio_version_schema", "request_studio_scenario_versions", "version > 0 AND schema_version IN (1,2,3,4)")


def downgrade():
    connection = op.get_bind()
    if connection.execute(text("SELECT 1 FROM request_studio_scenario_versions WHERE schema_version = 4 LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while v4 scenario versions exist")
    if connection.execute(text("SELECT 1 FROM request_studio_drafts WHERE definition ->> 'schema_version' = '4' LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while v4 scenario drafts exist")
    op.drop_constraint("ck_studio_version_schema", "request_studio_scenario_versions", type_="check")
    op.create_check_constraint("ck_studio_version_schema", "request_studio_scenario_versions", "version > 0 AND schema_version IN (1,2,3)")
