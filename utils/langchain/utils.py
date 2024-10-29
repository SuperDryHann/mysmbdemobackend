from langchain_core.chat_history import BaseChatMessageHistory
from chat.models import ChatHistory
from langchain_core.messages.utils import messages_from_dict
from langchain_core.messages import (
    BaseMessage, 
    ToolMessage, 
    SystemMessage, 
    AIMessageChunk,
    HumanMessage, 
    AIMessage
)
from asgiref.sync import sync_to_async



# ChatHistory instance
class OrmChatMessageHistory(BaseChatMessageHistory):
    '''
    Chat history class to get,store and clear the chat history in Django ORM leveraging langchain's BaseChatMessageHistory.
    This class deals with langchain's BaseMessage objects. So, this can directly be insert to langchain or langraph.
    '''
    def __init__(self, user_uuid: str):
        self.user_uuid=user_uuid

    @property
    async def aget_messages(self):
        # get history function
        @sync_to_async
        def get_chat_history(user_uuid: str):
            chat_history, created=ChatHistory.objects.get_or_create(user_uuid=user_uuid)
            return messages_from_dict(chat_history.messages)
        
        return await get_chat_history(self.user_uuid)
    
    def clear(self):
        pass

    async def aadd_messages(self, messages: list[BaseMessage]):
        @sync_to_async
        def append_messages(user_uuid: str, messages: list[BaseMessage]):
            chat_history, created=ChatHistory.objects.get_or_create(user_uuid=user_uuid)
            chat_history.messages.extend(messages)
            chat_history.save()
        await append_messages(self.user_uuid, messages)