"""Add navigation, immutable scenario versions, drafts and pinned sessions.

Revision ID: 147
Revises: 146
No existing catalog, form, ticket or policy row is rewritten.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "147"
down_revision = "146"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("request_studio_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service_code", sa.String(100), sa.ForeignKey("helpdesk_services.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("parent_id", sa.String(36)),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("visibility", sa.String(24), nullable=False, server_default="internal"),
        sa.Column("lifecycle_status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.Text), sa.Column("updated_by", sa.Text), *_timestamps(),
        sa.UniqueConstraint("id", "service_code", name="uq_studio_category_id_service"),
        sa.ForeignKeyConstraint(["parent_id", "service_code"], ["request_studio_categories.id", "request_studio_categories.service_code"], name="fk_studio_category_parent_service", ondelete="RESTRICT"),
        sa.UniqueConstraint("service_code", "parent_id", "slug", name="uq_studio_category_sibling_slug"),
        sa.CheckConstraint("visibility IN ('public','internal','restricted')", name="ck_studio_category_visibility"),
        sa.CheckConstraint("lifecycle_status IN ('draft','published','archived')", name="ck_studio_category_status"),
        sa.CheckConstraint("revision > 0", name="ck_studio_category_revision"),
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_studio_category_slug"))
    op.create_index("uq_studio_category_root_slug", "request_studio_categories", ["service_code", "slug"], unique=True, postgresql_where=sa.text("parent_id IS NULL"))
    op.create_index("ix_studio_category_tree", "request_studio_categories", ["service_code", "parent_id", "sort_order"])
    op.create_table("request_studio_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_key", sa.String(100), nullable=False, unique=True),
        sa.Column("service_code", sa.String(100), sa.ForeignKey("helpdesk_services.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("offering_full_code", sa.String(220), sa.ForeignKey("helpdesk_service_offerings.full_code", ondelete="RESTRICT"), nullable=False),
        sa.Column("category_id", sa.String(36)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("published_version_id", sa.String(36)),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Text), sa.Column("updated_by", sa.Text), *_timestamps(),
        sa.UniqueConstraint("id", "offering_full_code", name="uq_studio_scenario_id_offering"),
        sa.ForeignKeyConstraint(["category_id", "service_code"], ["request_studio_categories.id", "request_studio_categories.service_code"], name="fk_studio_scenario_category_service", ondelete="RESTRICT"),
        sa.CheckConstraint("split_part(offering_full_code,'.',1) = service_code", name="ck_studio_scenario_service"))
    op.create_index("ix_studio_scenario_offering", "request_studio_scenarios", ["offering_full_code"])
    op.create_index("ix_studio_scenario_category", "request_studio_scenarios", ["category_id"])
    op.create_table("request_studio_scenario_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("offering_full_code", sa.String(220), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("schema_version", sa.Integer, nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_snapshot", JSONB, nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="published"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_by", sa.Text, nullable=False),
        sa.ForeignKeyConstraint(["scenario_id", "offering_full_code"], ["request_studio_scenarios.id", "request_studio_scenarios.offering_full_code"], name="fk_studio_version_scenario_offering", ondelete="RESTRICT"),
        sa.UniqueConstraint("scenario_id", "version", name="uq_studio_version_number"),
        sa.UniqueConstraint("scenario_id", "id", name="uq_studio_version_scenario_id"),
        sa.CheckConstraint("state IN ('published','retired','revoked')", name="ck_studio_version_state"),
        sa.CheckConstraint("version > 0 AND schema_version = 1", name="ck_studio_version_schema"),
        sa.CheckConstraint("content_hash ~ '^[a-f0-9]{64}$'", name="ck_studio_version_hash"))
    op.create_index("uq_studio_version_active_offering", "request_studio_scenario_versions", ["offering_full_code"], unique=True, postgresql_where=sa.text("state = 'published'"))
    op.create_foreign_key("fk_studio_scenario_active_version", "request_studio_scenarios", "request_studio_scenario_versions", ["id", "published_version_id"], ["scenario_id", "id"], deferrable=True, initially="DEFERRED")
    op.create_table("request_studio_drafts",
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("request_studio_scenarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("base_version_id", sa.String(36)),
        sa.Column("updated_by", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["scenario_id", "base_version_id"], ["request_studio_scenario_versions.scenario_id", "request_studio_scenario_versions.id"], name="fk_studio_draft_base_version"),
        sa.CheckConstraint("revision > 0", name="ck_studio_draft_revision"))
    op.create_table("request_studio_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_actor_id", sa.Text, nullable=False),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("request_studio_scenario_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("current_block_id", sa.String(100), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("answers", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("history", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("results", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(32), nullable=False, server_default="active"),
        sa.Column("linked_ticket_id", sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), *_timestamps(),
        sa.CheckConstraint("revision > 0", name="ck_studio_session_revision"),
        sa.CheckConstraint("state IN ('active','completed_self_service','ticket_created','canceled','expired','revoked')", name="ck_studio_session_state"),
        sa.CheckConstraint("expires_at > created_at", name="ck_studio_session_expiry"))
    op.create_index("ix_studio_session_owner", "request_studio_sessions", ["owner_actor_id", "state", "expires_at"])
    op.create_index("ix_studio_session_version", "request_studio_sessions", ["version_id"])
    op.create_index("ix_studio_session_ticket", "request_studio_sessions", ["linked_ticket_id"])
    _guards()


def _guards():
    op.execute("""
    CREATE FUNCTION request_studio_category_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE cursor_id varchar(36); depth integer := 1; subtree integer;
    BEGIN
      PERFORM pg_advisory_xact_lock(hashtextextended(NEW.service_code, 0));
      IF TG_OP = 'UPDATE' AND NEW.service_code IS DISTINCT FROM OLD.service_code THEN
        RAISE EXCEPTION 'category service is immutable' USING ERRCODE = '23514';
      END IF;
      cursor_id := NEW.parent_id;
      WHILE cursor_id IS NOT NULL LOOP
        IF cursor_id = NEW.id OR depth >= 16 THEN
          RAISE EXCEPTION 'category cycle or depth limit' USING ERRCODE = '23514';
        END IF;
        SELECT parent_id INTO cursor_id FROM request_studio_categories WHERE id = cursor_id AND service_code = NEW.service_code;
        depth := depth + 1;
      END LOOP;
      WITH RECURSIVE descendants AS (
        SELECT id, 1 AS n FROM request_studio_categories WHERE id = NEW.id
        UNION ALL SELECT c.id, d.n + 1 FROM request_studio_categories c JOIN descendants d ON c.parent_id = d.id WHERE d.n <= 16
      ) SELECT coalesce(max(n),1) INTO subtree FROM descendants;
      IF depth + subtree - 1 > 16 THEN
        RAISE EXCEPTION 'category depth limit' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$;
    """)
    op.execute("CREATE TRIGGER request_studio_category_guard BEFORE INSERT OR UPDATE ON request_studio_categories FOR EACH ROW EXECUTE FUNCTION request_studio_category_guard()")
    op.execute("""
    CREATE FUNCTION request_studio_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'scenario version is immutable' USING ERRCODE = '23514'; END IF;
      IF (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state') THEN
        RAISE EXCEPTION 'scenario version is immutable' USING ERRCODE = '23514';
      END IF;
      IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
        (OLD.state = 'published' AND NEW.state IN ('retired','revoked')) OR
        (OLD.state = 'retired' AND NEW.state = 'revoked')) THEN
        RAISE EXCEPTION 'scenario version cannot be reactivated' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$;
    """)
    op.execute("CREATE TRIGGER request_studio_version_guard BEFORE UPDATE OR DELETE ON request_studio_scenario_versions FOR EACH ROW EXECUTE FUNCTION request_studio_version_guard()")
    op.execute("""
    CREATE FUNCTION request_studio_session_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.id IS DISTINCT FROM OLD.id OR NEW.owner_actor_id IS DISTINCT FROM OLD.owner_actor_id OR NEW.version_id IS DISTINCT FROM OLD.version_id THEN
        RAISE EXCEPTION 'scenario session identity is immutable' USING ERRCODE = '23514';
      END IF;
      RETURN NEW;
    END $$;
    """)
    op.execute("CREATE TRIGGER request_studio_session_guard BEFORE UPDATE ON request_studio_sessions FOR EACH ROW EXECUTE FUNCTION request_studio_session_guard()")


def downgrade():
    # Explicitly limited to this additive revision; never cross forward-only 144/143.
    op.drop_constraint("fk_studio_scenario_active_version", "request_studio_scenarios", type_="foreignkey")
    for name in ("request_studio_sessions", "request_studio_drafts", "request_studio_scenario_versions", "request_studio_scenarios", "request_studio_categories"):
        op.drop_table(name)
    for name in ("request_studio_session_guard", "request_studio_version_guard", "request_studio_category_guard"):
        op.execute(sa.text("DROP FUNCTION " + name + "()"))
