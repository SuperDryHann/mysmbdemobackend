import os
from .models import ChatHistory, ChatHistoryClient
from .serializers import ChatHistorySerializer, ChatHistoryClientSerializer
from rest_framework import viewsets
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
from rest_framework.decorators import api_view
from rest_framework.response import Response
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

# Vriables
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

@api_view(['POST'])
def chat(request):
    # setup & variables
    # variables
    body = request.body.decode('utf-8')
    body = json.loads(body)
    query = body["message"]
    username = request.user.username



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
    contextualize_q_system_prompt = """Given a chat history and the latest user question \
    which might reference context in the chat history, formulate a standalone question \
    which can be understood without the chat history. Do NOT answer the question, \
    just reformulate it if needed and otherwise return it as is."""
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
    If you don't know the answer, just say that you don't know. \
    
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

    # # Stringify List of Document obehects
    # def stringify_docs(docs: List[Document]) -> str:
    #     formatted = [
    #         f"Source ID: {doc.metadata['id']}\nArticle Title: {doc.metadata['title']}\nArticle Snippet: {doc.page_content}"
    #         for i, doc in enumerate(docs)
    #     ]
    #     return "\n\n" + "\n\n".join(formatted)

    # Jsonify list of Document objects
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
            reference = lambda x: x["context"]
        )
    )



    # Retrieve chat history from database (let's not use cache for now...)
    ## Retrieve last 5 chat history
    histories = ChatHistory.objects.filter(username=username).order_by('-id')[:5][::-1]
    
    # Coerce into langchain chat history format
    chat_history = []
    for history in histories:
        chat_history.extend([HumanMessage(content=history.user_message), history.ai_message])



    ## Invoke the chain
    output = rag_chain.invoke({"input": query}) # the chain needs input, chat_hitory and context
    answer = output["output"]["answer"]
    reference_id = output["output"]["citations"]
    reference = output["reference"]



    ## Store chat history into database.
    user_id = request.user.user_uuid ########################### Later it should be generated as sub-clients are not in Azure B2C
    ChatHistory(user_id = user_id, username = username, user_message = query, ai_message = answer).save()


    for chunk in rag_chain.stream({"input": "How can I pay?"}):
        print(chunk, flush=True)



    # Contact agent
    # Extract logs and aggregate in one text
    chat_histories = ChatHistory.objects.filter(user_id=user_id).values()
    log = ""
    for chat_history in chat_histories:
        log += f"User: {chat_history['user_message']}\nAI: {chat_history['ai_message']}\n\n"
    
    # Store aggregated log in ChatHistoryClient model
    chat_history_client, created = ChatHistoryClient.objects.get_or_create(user_id=user_id)
    chat_history_client.log = log



    # Summary of log
    summary_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Summarise chat log in 3 sentences."),
            ("human", "chat log: {input}"),
        ]
    )

    summarise_chain = (
        summary_prompt
        |llm
        |StrOutputParser()
    )

    summarised_log = summarise_chain.invoke(log)

    chat_history_client.summary = summarised_log



    # Priority of action
    priority_prompt = """
    Given a summary of the chat log, assign a priority to follow-up action, strictly following guidelines:
    - High priority: Course question, Enrolment question
    - Medium priority: Refund question, Tuition fee question
    - Low priority: Anything else

    Answer MUST be one of: High, Medium, Low
    """

    priority_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", priority_prompt),
            ("human", "chat log summary: {input}"),
        ]
    )
    
    priority_chain = (
        priority_prompt
        |llm
        |StrOutputParser()
    )
    priority = priority_chain.invoke(summarised_log)

    chat_history_client.priority = priority

    chat_history_client.save()

    return Response({
        "message": answer,
        "reference": reference
        })



class ChatHistoryViewSet(viewsets.ModelViewSet):
    queryset = ChatHistory.objects.all()
    serializer_class = ChatHistorySerializer



class ChatHistoryClientViewSet(viewsets.ModelViewSet):
    queryset = ChatHistoryClient.objects.all()
    serializer_class = ChatHistoryClientSerializer
