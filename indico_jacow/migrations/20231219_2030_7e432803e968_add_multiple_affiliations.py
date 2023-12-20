"""Add multiple affiliations

Revision ID: 7e432803e968
Revises:
Create Date: 2023-12-19 20:30:41.318370
"""

import sqlalchemy as sa
from alembic import op

from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = '7e432803e968'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(CreateSchema('plugin_jacow'))
    op.create_table(
        'multiple_affiliations',
        sa.Column('person_link_id', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('person_link_id', 'affiliation_id'),
        sa.ForeignKeyConstraint(['person_link_id'], ['events.contribution_person_links.id']),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id']),
        schema='plugin_jacow'
    )


def downgrade():
    op.drop_table('multiple_affiliations', schema='plugin_jacow')
    op.execute(DropSchema('plugin_jacow'))
