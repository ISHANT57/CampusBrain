from app.models.conversation import Conversation
from app.repositories.base import OrgScopedRepository


class ConversationRepository(OrgScopedRepository[Conversation]):
    model = Conversation

    def get_for_user(self, id: int, user_id: int) -> Conversation | None:
        """Org scoping alone isn't enough for conversations: within one org, a
        user must not read or continue another user's private chat. Every
        conversation lookup driven by a client-supplied id goes through here."""
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.id == id,
                Conversation.org_id == self.org_id,
                Conversation.user_id == user_id,
            )
            .first()
        )
