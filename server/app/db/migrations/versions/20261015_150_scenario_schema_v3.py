"""Allow immutable scenario v3 alongside historical v1/v2 definitions.

Revision ID: 150
Revises: 149
No stored definitions, policy registries or tickets are rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "150"
down_revision = "149"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_studio_version_schema", "request_studio_scenario_versions", type_="check")
    op.create_check_constraint("ck_studio_version_schema", "request_studio_scenario_versions", "version > 0 AND schema_version IN (1,2,3)")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM request_studio_scenario_versions WHERE schema_version = 3")):
        raise RuntimeError("Cannot downgrade while immutable v3 scenario versions exist")
    op.drop_constraint("ck_studio_version_schema", "request_studio_scenario_versions", type_="check")
    op.create_check_constraint("ck_studio_version_schema", "request_studio_scenario_versions", "version > 0 AND schema_version IN (1,2)")
