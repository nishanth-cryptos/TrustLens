"""${message}

Revision: ${up_revision}
Contract reference and change class: fill in before review.
"""
from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    raise NotImplementedError("Write and review explicit contract-aligned SQL before applying this revision")


def downgrade():
    raise NotImplementedError("Downgrade requires separate review of lossless rollback")
