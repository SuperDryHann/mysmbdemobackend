import os
import json
from backend.auth_azure import websocket_authenticated
from dotenv import load_dotenv
from pprint import pprint
from typing import Annotated, Sequence, TypedDict, List
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, AIMessageChunk, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.azuresearch import AzureSearch
from langgraph.graph import StateGraph, END
from langgraph.constants import END, START
from langgraph.checkpoint.memory import MemorySaver
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool
from langgraph.prebuilt import ToolNode
from utils.miscellaneous import get_claim_from_token_ws, get_parameter_ws
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from openai import AzureOpenAI
from .models import ChatHistory
from asgiref.sync import sync_to_async
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages.utils import messages_from_dict
from langchain_core.messages.base import messages_to_dict
from django.forms.models import model_to_dict



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
AZURE_OPENAI_EMBEDDING_DIMENSION = os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSION")



class Chat(AsyncWebsocketConsumer):
    @websocket_authenticated
    async def connect(self):
        # Accept the WebSocket connections
        await self.accept()

    async def disconnect(self, close_code):
        # Handle WebSocket disconnection (optional cleanup can be added here)
        pass

    async def receive(self, text_data):
        # Parse the received message from WebSocket
        data = json.loads(text_data)
        received_message = data.get('message', '')

        # await self.simulate_streaming(received_message)
        await self.chat(received_message)

    async def chat(self, received_message):
        # setup & variables
        # variables
        tenant_id=get_claim_from_token_ws(self.scope, 'tid')
        sub=get_claim_from_token_ws(self.scope, 'sub')
        oid=get_claim_from_token_ws(self.scope, 'oid')
        email=get_claim_from_token_ws(self.scope, 'upn')
        user_input = received_message

        case=get_parameter_ws(self.scope, 'case')
        if case=="customerservice":
            index_name = "customerservice"
        elif case=="organisation":
            index_name = tenant_id



        # LLM instance
        llm = AzureChatOpenAI(
            azure_endpoint = AZURE_OPENAI_ENDPOINT,
            azure_deployment = AZURE_OPENAI_DEPLOYMENT_4,
            openai_api_key = AZURE_OPENAI_KEY,
            openai_api_version = AZURE_OPENAI_API_VERSION
            )



        # ChatHistory instance
        class OrmChatHistory(BaseChatMessageHistory):
            def __init__(self, sub: str):
                self.sub=sub

            @property
            async def aget_messages(self):
                # get history function
                @sync_to_async
                def get_chat_history(sub: str):
                    chat_history, created=ChatHistory.objects.get_or_create(
                        sub=sub,
                        defaults={
                            "tenant_id": tenant_id,
                            "oid": oid,
                            "username": email,
                            "messages": []
                        }
                    )
                    return messages_from_dict(chat_history.messages)
                
                return await get_chat_history(self.sub)
            
            def clear(self):
                pass

            async def aadd_messages(self, messages: list[BaseMessage]):
                @sync_to_async
                def append_messages(sub: str, messagess: list[BaseMessage]):
                    chat_history, created=ChatHistory.objects.get_or_create(
                        sub=sub,
                        defaults={
                            "tenant_id": tenant_id,
                            "oid": oid,
                            "username": email,
                            "messages": []
                        }
                    )
                    chat_history.messages.extend(messages)
                    chat_history.save()
                await append_messages(self.sub, messages)
        
        orm_chat_history=OrmChatHistory(sub)
        chat_history=await orm_chat_history.aget_messages
        print(chat_history)
        chat_history_subset=chat_history[-10:]



        # Retriever function (for tool)
        def retrieve_local(query: str):
            """Retrieve reference knowledge and facts from the database to respond to the user."""
            credential=AzureKeyCredential(AZURE_SEARCH_KEY)

            search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT,
                      index_name=index_name,
                      credential=credential)
            
            vector_query = VectorizableTextQuery(
                text=query, 
                k_nearest_neighbors=5, 
                fields="chunk_vector")

            documents = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                query_type="semantic",
                select=["title", "chunk", "chunk_id"],
                top=5
                )

            documents_dict = []
            for i, document in enumerate(documents):
                dict_output = {
                    # "reference_id": document["chunk_id"],
                    "reference_id": str(1+i),
                    "title": document["title"],
                    "content": document["chunk"],
                }
                documents_dict.append(dict_output)

            return documents_dict
        


        # retriever_local_tool input type
        class RetrieverLocalInput(BaseModel):
            query: str = Field(description="Query to retrieve knowledge from the database")
        


        # retriever_local_tool
        retriever_local_tool = StructuredTool.from_function(
            func = retrieve_local,
            name = "retrieve_local",
            description = "Retrieve reference knowledge and facts from the database to respond to the user.",
            args_schema=RetrieverLocalInput,
            return_direct = True
        )



        # Graph state
        class AgentState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], add_messages]
            final_output: dict
            answer: str
            references: List[dict]



        # Tool excution node
        tools = [retriever_local_tool]

        llm_with_tools = llm.bind_tools(tools)

        tools_by_name = {tool.name: tool for tool in tools}

        def tool_node(state: AgentState):
            outputs = []
            for tool_call in state["messages"][-1].tool_calls: # Get the last message and its tool calls decision
                tool_result = tools_by_name[tool_call["name"]].invoke(tool_call["args"]) # Invoke the tool
                outputs.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )

            return {
                "messages": outputs,
                "references": tool_result
                }



        # Function call node
        def call_model(state: AgentState, config: RunnableConfig):
            system_prompt = SystemMessage(
                "You are a AI assistant, please respond to the users query with comprehensive response based on reference documents. NEVER use facts outside of the reference. If you cannot answer based on the reference, say you don't know.",
            )
            
            response = llm_with_tools.invoke([system_prompt] + chat_history_subset + state["messages"], config)
            return {
                "messages": response,
                "answer": response.content
                }

        

        # Output parse node
        # List of Reference object type
        class ReferencedAnswer(BaseModel):
            """Parse the output of the LLM with tools to get the answer and references."""
            answer: str = Field(
                ...,
                description="The answer",
            )
            reference_ids: List[str] = Field(
                ...,
                    description="The reference_ids of the SPECIFIC sources which justify the answer. Provide ONLY the reference_ids of the sources which justify the answer.",
            )

        # Output parser llm 
        llm_with_structured_output = llm.with_structured_output(ReferencedAnswer)

        # Node function
        def output_model(state: AgentState, config: RunnableConfig):
            input =f"""
                Answer: {state.get("answer")}
                References: {state.get("references")}
            """

            input =[HumanMessage(content=input)]
            response = llm_with_structured_output.invoke(input, config)
            response = response.dict()
            reference_ids = response.get("reference_ids")
            try:
                response["references"] = [reference for reference in state.get("references") if reference["reference_id"] in reference_ids]
            except:
                response["references"] = []
            return {"final_output": response}



        # Conditional edge
        def should_continue(state: AgentState):
            messages = state["messages"]
            last_message = messages[-1]
            # If there is no function call, then we finish
            if not last_message.tool_calls:
                return "output_parser"
            # Otherwise if there is, we continue
            else:
                return "tools"



        # Define graph
        workflow = StateGraph(AgentState)



        # Nodes
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_node("output_parser", output_model)



        # Edges (from, condition function, mapping "(result: next node)"")
        # Conditional edge
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            ["tools", "output_parser"]
        )

        # Edge
        workflow.add_edge("tools", "agent")
        workflow.add_edge("output_parser", END)



        # Compile the graph
        memory = MemorySaver()
        workflow.add_edge(START, "agent")
        graph = workflow.compile(checkpointer=memory)



        # Run the graph
        user_input = [HumanMessage(content=user_input)]

        output = AIMessageChunk(content="")
        config = {"configurable": {"thread_id": "1"}}
        async for msg, metadata in graph.astream(input = {"messages" : user_input}, config = config, stream_mode="messages"):
            if msg.content and isinstance(msg, AIMessageChunk): # check msg.content is not empty string. It has placeholder while tools are running.
                output = output + msg

                await asyncio.sleep(0.01)
                await self.send(text_data=json.dumps({
                    "message": output.content
                }))
        


        # Task complete, send a final message
        answer = graph.get_state(config).values["final_output"]["answer"]
        references = graph.get_state(config).values["final_output"]["references"]
        final_output = {
            "message": answer,
            "references": references,
            "is_completed": True
        }



        # Save the chat history
        human_message=HumanMessage(content=received_message)
        ai_message=AIMessage(content=answer)
        langchain_messages: Sequence[BaseMessage]=[human_message, ai_message]
        serialised_messages = messages_to_dict(langchain_messages)

        await orm_chat_history.aadd_messages(serialised_messages)
        
        # await save_chat_history(sub, tenant_id, oid, email, received_message, answer)



        # Send the final message
        await self.send(text_data=json.dumps(final_output))


            
