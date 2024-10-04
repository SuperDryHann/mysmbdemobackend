# myapp/consumers.py
import os
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_openai import OpenAI
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.documents import Document
from langchain_openai import AzureOpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import AzureBlobStorageFileLoader, AzureBlobStorageContainerLoader
from langchain_text_splitters import CharacterTextSplitter
from azure.search.documents.indexes.models import ScoringProfile, SearchableField, SearchField, SearchFieldDataType, SimpleField, TextWeights
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableLambda
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from django.http import JsonResponse
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from django.forms.models import model_to_dict
from dotenv import load_dotenv
import asyncio
from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from pprint import pprint
from backend.auth_azure import websocket_authenticated
from .models import ChatHistory, ChatHistoryClient
from .serializers import ChatHistorySerializer, ChatHistoryClientSerializer
from channels.db import database_sync_to_async


load_dotenv()
AZURE_OPENAI_DEPLOYMENT_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_4")
AZURE_OPENAI_DEPLOYMENT_EMBEDDING = os.getenv("AZURE_OPENAI_DEPLOYMENT_EMBEDDING")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
AZURE_STORAGE_KEY = os.getenv("AZURE_STORAGE_KEY")






import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer

class Chat(AsyncWebsocketConsumer):
    @websocket_authenticated
    async def connect(self):
        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        # Handle WebSocket disconnection (optional cleanup can be added here)
        pass

    async def receive(self, text_data):
        # Parse the received message from WebSocket
        data = json.loads(text_data)
        print(data)
        received_message = data.get('message', '')

        # await self.simulate_streaming(received_message)
        await self.chat(received_message)

    async def chat(self, received_message):
        # setup & variables
        # variables
        user_input = received_message
        username = self.scope["user"].username
        user_uuid = self.scope["user"].user_uuid ########################### Later it should be generated as sub-clients are not in Azure B2C




        # Semantic search configurations
        # Embedding instance
        embeddings: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
            azure_deployment = AZURE_OPENAI_DEPLOYMENT_EMBEDDING,
            openai_api_version = AZURE_OPENAI_API_VERSION,
            azure_endpoint = AZURE_OPENAI_ENDPOINT,
            api_key = AZURE_OPENAI_KEY,
        )

        # Vector store instance (in this case, Azure ai search index)
        vector_store: AzureSearch = AzureSearch(
            azure_search_endpoint=AZURE_SEARCH_ENDPOINT,
            azure_search_key=AZURE_SEARCH_KEY,
            index_name='unsw',
            embedding_function=embeddings.embed_query,
        )

        # Retriever object (langchain object)
        retriever = vector_store.as_retriever(
            search_type = "hybrid",
            k=3,
            # search_kwargs = {"filters" : f"filter_council eq '{filter_council}'"}
        )



        # LLM instance
        llm = AzureChatOpenAI(
        azure_endpoint = AZURE_OPENAI_ENDPOINT,
        azure_deployment = AZURE_OPENAI_DEPLOYMENT_4,
        openai_api_key = AZURE_OPENAI_KEY,
        openai_api_version = AZURE_OPENAI_API_VERSION
        )



        # History aware retriever
        # Reform question to take into account the chat history, this new reformed question will be used to retrieve knowledge
        contextualize_q_system_prompt = """Given a chat history and the latest user input \
        which might reference context in the chat history, formulate a standalone question \
        which can be understood without the chat history. Do NOT answer the question, \
        just reformulate it if needed and otherwise return it as is. \
        This reformulation MUST be based on the latest user input"""
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", contextualize_q_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        # History aware retriever instance
        history_aware_retriever = create_history_aware_retriever(
            llm, retriever, contextualize_q_prompt
        )



        # Main runnable
        # Main prompt (input, context and chat_history needed)
        qa_system_prompt = """You are an assistant for question-answering tasks. \
        Use the following pieces of retrieved context to answer the question. \
        If you don't know the answer, just say that you don't know.  \
        
        Sources (array of JSON): {context}"""

        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", qa_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )



        # Citation interface
        class CitedAnswer(BaseModel):
            """Answer the user question based only on the given sources, and cite the sources used."""

            answer: str = Field(
                ...,
                description="The answer to the user question, which is based only on the given sources. Don't include source_id in the answer.",
            )
            citations: List[str] = Field(
                ...,
                description="List of the source_id of the SPECIFIC sources which justify the answer.",
            )

        def jsonify_docs(docs: List[Document]) -> str:
            formatted = []
            for doc in docs:
                formatted.append({
                    "source_id":doc.metadata['id'],
                    "title": doc.metadata['title'],
                    "content": doc.page_content
                })
            return formatted
        
        def subset_reference(ids:list[str], references: list[dict]) -> list[dict]:
            return [reference for reference in references if reference["source_id"] in ids]



        # Main runnable
        rag_chain = (
            RunnablePassthrough().assign(chat_history = lambda x: chat_history) | # Initial input is always dict only include "input". So, assign chat_history
            RunnablePassthrough().assign(context = (
                history_aware_retriever |  # history_aware_retriever needs input and chat_history, then stringify list of Document objects
                RunnableLambda(jsonify_docs)
            ))|
            RunnableParallel(
                output = (
                    qa_prompt |
                    llm.bind_tools(
                        [CitedAnswer],
                        tool_choice = "CitedAnswer"
                    ) |
                    JsonOutputKeyToolsParser(
                        key_name="CitedAnswer", 
                        first_tool_only=True
                        ) # LLM runnable
                ),
                references = lambda x: x["context"]
            )
        )



        # Retrieve chat history from database (let's not use cache for now...)
        # Retrieve last 5 chat history
        @database_sync_to_async
        def get_chat_history(username):
            return list(ChatHistory.objects.filter(username=username).order_by('-id')[:5][::-1])
        
        histories = await get_chat_history(username)
        print(histories)
        
        # Coerce into langchain chat history format
        chat_history = []
        for history in histories:
            chat_history.extend([HumanMessage(content=history.user_message), history.ai_message])



        final_output = {}
        async for chunk in rag_chain.astream({"input": user_input}):
            final_output = final_output + chunk
            await self.send(text_data=json.dumps({
                "message": chunk.get("output", {}).get("answer", ""),
                }))
    


        # Task complete, send a final message
        final_output = {
            "message": final_output.get("output", {}).get("answer", ""),
            "reference_id": final_output.get("output", {}).get("citations", []),
            "references": subset_reference(final_output.get("output", {}).get("citations", []), final_output.get("references", {})),
            "is_completed": True
        }        
        await self.send(text_data=json.dumps(final_output))



        ## Store chat history into database.
        @database_sync_to_async
        def save_chat_history(username, user_uuid, user_message, ai_message):
            return ChatHistory(user_uuid = user_uuid, username = username, user_message = user_message, ai_message = ai_message).save()
        
        await save_chat_history(username, user_uuid, user_input, final_output.get("message"))


            
