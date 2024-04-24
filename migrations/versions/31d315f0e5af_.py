"""empty message

Revision ID: 31d315f0e5af
Revises: e5e88c4e22c1
Create Date: 2024-04-25 02:50:19.868053

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '31d315f0e5af'
down_revision = 'e5e88c4e22c1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('room_track')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('room_track',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('track_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('room_id', mysql.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('added_time', mysql.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name='room_track_ibfk_2'),
    sa.ForeignKeyConstraint(['track_id'], ['track.id'], name='room_track_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    # ### end Alembic commands ###
