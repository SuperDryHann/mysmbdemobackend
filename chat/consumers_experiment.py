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
from utils.miscellaneous import get_claim_from_token_ws
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from openai import AzureOpenAI
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from langgraph.types import StreamWriter







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
        index_name = tenant_id
        user_input = received_message
        # username = self.scope["user"].username
        # user_uuid = self.scope["user"].user_uuid ########################### Later it should be generated as sub-clients are not in Azure B2C



        # LLM instance
        llm = AzureChatOpenAI(
            azure_endpoint = AZURE_OPENAI_ENDPOINT,
            azure_deployment = AZURE_OPENAI_DEPLOYMENT_4,
            openai_api_key = AZURE_OPENAI_KEY,
            openai_api_version = AZURE_OPENAI_API_VERSION
            )



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
                    "reference_id": str(i+1),
                    # "reference_id": document["chunk_id"],
                    "title": document["title"],
                    "content": document["chunk"],
                }
                documents_dict.append(dict_output)
            # pprint(documents_dict)

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

            try: 
                output={
                    "messages": outputs,
                    "references": tool_result
                }
            except:
                output={
                    "messages": outputs,
                    "references": []
                }

            return output



        # Function call node
        def call_model(state: AgentState, config: RunnableConfig):
            system_prompt = SystemMessage(
                "You are a AI assistant, please respond to the users query with comprehensive response based on reference documents. NEVER use facts outside of the reference. If you cannot answer based on the reference, say you don't know.",
            )
            
            response = llm_with_tools.invoke([system_prompt] + state["messages"], config)
            return {
                "messages": response,
                "answer": response.content
                }

        

        # Output parse node
        async def output_model(
                state: AgentState, 
                writer: StreamWriter,
                config: RunnableConfig):
            
            # # Reference object type
            # class Reference(BaseModel):
            #     source_id: str = Field(
            #         ...,
            #         description="The unique identifier of the reference."
            #         )
            #     title: str = Field(
            #         ..., 
            #         escription="The title of the reference."
            #         )
            #     content: str = Field(
            #         ..., 
            #         description="The content of reference."
            #         )

            # List of Reference object type
            class ReferencedAnswer(BaseModel):
                """Provide comprehensive answer based on reference documents."""
                answer: str = Field(
                    ...,
                    description="""Comprehensive response for user query based on reference documents in markdown format. Always use numbered list structure for response when it is possible. NEVER use facts outside of the reference. Do not mention reference id in the answer.
                    If user query cannot be answered based on the reference, say you cannot provide an answer based on knowledge base.""",
                )
                reference_ids: List[str] = Field(
                    ...,
                    description="The reference_ids of the SPECIFIC sources which justify the answer. Provide ONLY the reference_ids of the sources which justify the answer.",
                )

            # Output parser llm
            rag_chain = (
                llm.bind_tools(
                            [ReferencedAnswer],
                            tool_choice = "ReferencedAnswer"
                        ) |
                        JsonOutputKeyToolsParser(
                            key_name="ReferencedAnswer", 
                            first_tool_only=True
                            )
            )
            
            input =f"""
                User Query: {state.get("messages")[0].content}
                References: {state.get("references")}
            """

            input =[HumanMessage(content=input)]

            async for chunk in rag_chain.astream(input):
                writer(chunk)
            
            reference_ids = chunk.get("reference_ids")
            chunk["references"] = [reference for reference in state["references"] if reference["reference_id"] in reference_ids]
            return {"final_output": chunk}



        # Define graph
        workflow = StateGraph(AgentState)



        # Nodes
        workflow.add_node("function_call", call_model)
        workflow.add_node("tool_execution", tool_node)
        workflow.add_node("output_parser", output_model)



        # Edges (from, condition function, mapping "(result: next node)"")

        # Edge
        workflow.add_edge("function_call", "tool_execution")    
        workflow.add_edge("tool_execution", "output_parser")
        workflow.add_edge("output_parser", END)



        # Compile the graph
        memory = MemorySaver()
        workflow.add_edge(START, "function_call")
        graph = workflow.compile(checkpointer=memory)



        # Run the graph
        user_input = [HumanMessage(content=user_input)]

        output = AIMessageChunk(content="")
        config = {"configurable": {"thread_id": "1"}}
        async for chunk in graph.astream(input = {"messages" : user_input}, config = config, stream_mode="custom"):
            if chunk.get("answer"): # check msg.content is not empty string. It has placeholder while tools are running.
                await self.send(text_data=json.dumps({
                    "message": chunk.get("answer")
                }))
        
        # Task complete, send a final message
        answer = graph.get_state(config).values["final_output"]["answer"]
        references = graph.get_state(config).values["final_output"]["references"]
        final_output = {
            "message": answer,
            "references": references,
            "is_completed": True
        }
        await self.send(text_data=json.dumps(final_output))


            
