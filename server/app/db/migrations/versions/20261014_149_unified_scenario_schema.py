"""Allow unified map v2 alongside immutable historical v1 versions.

Revision ID: 149
Revises: 148
No stored definitions, templates, tickets or sessions are rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "149"
down_revision = "148"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_studio_version_schema", "request_studio_scenario_versions", type_="check")
    op.create_check_constraint("ck_studio_version_schema", "request_studio_scenario_versions", "version > 0 AND schema_version IN (1,2)")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM request_studio_scenario_versions WHERE schema_version = 2")):
        raise RuntimeError("Cannot downgrade while immutable v2 scenario versions exist")
    op.drop_constraint("ck_studio_version_schema", "request_studio_scenario_versions", type_="check")
    op.create_check_constraint("ck_studio_version_schema", "request_studio_scenario_versions", "version > 0 AND schema_version = 1")
