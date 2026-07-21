from app.models.conversation import Conversation
from app.repositories.base import OrgScopedRepository


class ConversationRepository(OrgScopedRepository[Conversation]):
    model = Conversation
