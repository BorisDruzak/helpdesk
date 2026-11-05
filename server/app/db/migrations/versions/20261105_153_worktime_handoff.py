"""One-use WorkTime browser handoff and source-session leases; no account changes."""
from alembic import op
import sqlalchemy as sa

revision='153'
down_revision='152'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('oidc_flows',sa.Column('return_path',sa.String(1800),nullable=False,server_default='/app'))
    for table, key in [('worktime_authorization_codes','code_hash'),('worktime_session_leases','handle_hash')]:
        columns=[sa.Column(key,sa.String(64),primary_key=True),
            sa.Column('source_token_hash',sa.String(64),sa.ForeignKey('ui_tokens.token_hash',ondelete='CASCADE'),nullable=False),
            sa.Column('person_id',sa.String(36),sa.ForeignKey('registry_people.person_id',ondelete='CASCADE'),nullable=False),
            sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False)]
        if key=='code_hash':columns.extend([sa.Column('challenge',sa.String(43),nullable=False),sa.Column('callback',sa.String(512),nullable=False),sa.Column('consumed_at',sa.DateTime(timezone=True))])
        op.create_table(table,*columns)
        op.create_index('ix_'+table+'_expires',table,['expires_at'])


def downgrade():
    op.drop_table('worktime_session_leases')
    op.drop_table('worktime_authorization_codes')
    op.drop_column('oidc_flows','return_path')
