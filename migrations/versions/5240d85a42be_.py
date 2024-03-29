"""empty message

Revision ID: 5240d85a42be
Revises: 47957de76ad9
Create Date: 2024-03-22 17:13:46.800476

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '5240d85a42be'
down_revision = '47957de76ad9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('recent_tracks', schema=None) as batch_op:
        batch_op.drop_index('encode_id')
        batch_op.drop_index('spotify_id')

    op.drop_table('recent_tracks')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('recent_tracks',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('track_id', mysql.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('played_at', mysql.DATETIME(), nullable=False),
    sa.Column('encode_id', mysql.VARCHAR(length=100), nullable=True),
    sa.Column('spotify_id', mysql.VARCHAR(length=100), nullable=False),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], name='recent_tracks_ibfk_2'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='recent_tracks_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    with op.batch_alter_table('recent_tracks', schema=None) as batch_op:
        batch_op.create_index('spotify_id', ['spotify_id'], unique=True)
        batch_op.create_index('encode_id', ['encode_id'], unique=True)

    # ### end Alembic commands ###
