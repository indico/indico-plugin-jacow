"""Add multiple affiliations

Revision ID: 7e432803e968
Revises:
Create Date: 2023-12-19 20:30:41.318370
"""

import sqlalchemy as sa
from alembic import context, op

from sqlalchemy.sql.ddl import CreateSchema, DropSchema


# revision identifiers, used by Alembic.
revision = '7e432803e968'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise Exception('This upgrade is only possible in online mode')

    op.execute(CreateSchema('plugin_jacow'))
    op.create_table(
        'abstract_affiliations',
        sa.Column('person_link_id', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id']),
        sa.ForeignKeyConstraint(['person_link_id'], ['event_abstracts.abstract_person_links.id']),
        sa.PrimaryKeyConstraint('person_link_id', 'affiliation_id'),
        schema='plugin_jacow'
    )
    op.create_table(
        'contribution_affiliations',
        sa.Column('person_link_id', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id']),
        sa.ForeignKeyConstraint(['person_link_id'], ['events.contribution_person_links.id']),
        sa.PrimaryKeyConstraint('person_link_id', 'affiliation_id'),
        schema='plugin_jacow'
    )
    op.create_index(
        'ix_uq_abstract_affiliations_person_link_id_display_order',
        'abstract_affiliations',
        ['person_link_id', 'display_order'],
        unique=True,
        schema='plugin_jacow'
    )
    op.create_index(
        'ix_uq_contribution_affiliations_person_link_id_display_order',
        'contribution_affiliations',
        ['person_link_id', 'display_order'],
        unique=True,
        schema='plugin_jacow'
    )

    # Populate tables with the current affiliations
    conn = op.get_bind()
    for target, source in (('abstract_affiliations', 'event_abstracts.abstract_person_links'),
                           ('contribution_affiliations', 'events.contribution_person_links')):
        conn.execute(f'''
            INSERT INTO plugin_jacow.{target} (person_link_id, affiliation_id, display_order)
            SELECT id, affiliation_id, 0 FROM {source} pl
            WHERE pl.affiliation_id IS NOT NULL
        ''')


def downgrade():
    op.drop_table('contribution_affiliations', schema='plugin_jacow')
    op.drop_table('abstract_affiliations', schema='plugin_jacow')
    op.execute(DropSchema('plugin_jacow'))
