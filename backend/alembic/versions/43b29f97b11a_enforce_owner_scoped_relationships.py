"""Enforce same-owner parent/child relationships.

Revision ID: 43b29f97b11a
Revises: d7d4d2df32b8
"""


from alembic import op

revision = "43b29f97b11a"
down_revision = "d7d4d2df32b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize child ownership to the parent before adding database constraints.
    op.execute(
        "UPDATE messages SET user_id = (SELECT user_id FROM conversations "
        "WHERE conversations.id = messages.conversation_id) "
        "WHERE EXISTS (SELECT 1 FROM conversations "
        "WHERE conversations.id = messages.conversation_id)"
    )
    op.execute(
        "UPDATE document_chunks SET user_id = (SELECT user_id FROM documents "
        "WHERE documents.id = document_chunks.document_id) "
        "WHERE EXISTS (SELECT 1 FROM documents "
        "WHERE documents.id = document_chunks.document_id)"
    )
    op.execute(
        "UPDATE tool_executions SET user_id = (SELECT user_id FROM messages "
        "WHERE messages.id = tool_executions.message_id) "
        "WHERE message_id IS NOT NULL AND EXISTS (SELECT 1 FROM messages "
        "WHERE messages.id = tool_executions.message_id)"
    )

    with op.batch_alter_table("conversations") as batch:
        batch.create_unique_constraint("uq_conversations_id_user", ["id", "user_id"])

    with op.batch_alter_table(
        "messages",
        naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
        },
    ) as batch:
        batch.drop_constraint(
            "fk_messages_conversation_id_conversations", type_="foreignkey"
        )
        batch.create_unique_constraint("uq_messages_id_user", ["id", "user_id"])
        batch.create_foreign_key(
            "fk_messages_conversation_user",
            "conversations",
            ["conversation_id", "user_id"],
            ["id", "user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("documents") as batch:
        batch.create_unique_constraint("uq_documents_id_user", ["id", "user_id"])

    with op.batch_alter_table(
        "document_chunks",
        naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
        },
    ) as batch:
        batch.drop_constraint(
            "fk_document_chunks_document_id_documents", type_="foreignkey"
        )
        batch.create_foreign_key(
            "fk_chunks_document_user",
            "documents",
            ["document_id", "user_id"],
            ["id", "user_id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table(
        "tool_executions",
        naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
        },
    ) as batch:
        batch.drop_constraint(
            "fk_tool_executions_message_id_messages", type_="foreignkey"
        )
        batch.create_foreign_key(
            "fk_tool_exec_message_user",
            "messages",
            ["message_id", "user_id"],
            ["id", "user_id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "tool_executions",
        naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
        },
    ) as batch:
        batch.drop_constraint("fk_tool_exec_message_user", type_="foreignkey")
        batch.create_foreign_key(
            "fk_tool_executions_message_id_messages",
            "messages",
            ["message_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table(
        "document_chunks",
        naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
        },
    ) as batch:
        batch.drop_constraint("fk_chunks_document_user", type_="foreignkey")
        batch.create_foreign_key(
            "fk_document_chunks_document_id_documents",
            "documents",
            ["document_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("uq_documents_id_user", type_="unique")

    with op.batch_alter_table(
        "messages",
        naming_convention={
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
        },
    ) as batch:
        batch.drop_constraint("fk_messages_conversation_user", type_="foreignkey")
        batch.create_foreign_key(
            "fk_messages_conversation_id_conversations",
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.drop_constraint("uq_messages_id_user", type_="unique")

    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("uq_conversations_id_user", type_="unique")
