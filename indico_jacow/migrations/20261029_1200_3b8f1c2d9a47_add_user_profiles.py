"""Add user profiles

Revision ID: 3b8f1c2d9a47
Revises: 7e432803e968
Create Date: 2026-10-29 12:00:00.000000
"""

from enum import Enum

import sqlalchemy as sa
from alembic import op

from indico.core.db.sqlalchemy import PyIntEnum, UTCDateTime


# revision identifiers, used by Alembic.
revision = '3b8f1c2d9a47'
down_revision = '7e432803e968'
branch_labels = None
depends_on = None


class _InitialsFormat(int, Enum):
    spaced = 0
    hyphenated = 1


def upgrade():
    op.create_table(
        'user_profiles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('orcid', sa.String(), nullable=True),
        sa.Column('orcid_connected_dt', UTCDateTime, nullable=True),
        sa.Column('initials_format', PyIntEnum(_InitialsFormat), nullable=False),
        sa.Column('full_first_name', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.users.id']),
        sa.PrimaryKeyConstraint('user_id'),
        schema='plugin_jacow'
    )
    op.create_table(
        'user_affiliations',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('affiliation_id', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['affiliation_id'], ['indico.affiliations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['plugin_jacow.user_profiles.user_id']),
        sa.PrimaryKeyConstraint('user_id', 'affiliation_id'),
        schema='plugin_jacow'
    )
    op.create_index(
        'ix_uq_user_affiliations_user_id_display_order',
        'user_affiliations',
        ['user_id', 'display_order'],
        unique=True,
        schema='plugin_jacow'
    )


def downgrade():
    op.drop_table('user_affiliations', schema='plugin_jacow')
    op.drop_table('user_profiles', schema='plugin_jacow')
