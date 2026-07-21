from app.models.message import Message
from app.repositories.base import OrgScopedRepository


class MessageRepository(OrgScopedRepository[Message]):
    model = Message

    def list_for_conversation(self, conversation_id: int, limit: int | None = None) -> list[Message]:
        query = (
            self.db.query(Message)
            .filter(Message.org_id == self.org_id, Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        rows = query.all()
        return rows[-limit:] if limit else rows
