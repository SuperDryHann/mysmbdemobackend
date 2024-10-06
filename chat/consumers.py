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
        received_message = data.get('message', '')

        # await self.simulate_streaming(received_message)
        await self.chat(received_message)

    async def chat(self, received_message):
        # setup & variables
        # variables
        user_input = received_message
        username = self.scope["user"].username
        user_uuid = self.scope["user"].user_uuid ########################### Later it should be generated as sub-clients are not in Azure B2C



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

            # Retriever (as a tool)
            # Embeddings instance
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
                k=5,
                # search_kwargs = {"filters" : f"filter_council eq '{filter_council}'"}
            )
            
            documents = retriever.invoke(query)
            documents_json = []
            for document in documents:
                document_json = document.to_json().get("kwargs")
                json_output = {
                    "id": document_json["metadata"]["id"],
                    "title": document_json["metadata"]["title"],
                    "content": document_json["page_content"],
                }
                documents_json.append(json_output)
            return documents_json

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
            
            response = llm_with_tools.invoke([system_prompt] + state["messages"], config)
            return {
                "messages": response,
                "answer": response.content
                }

        

        # Output parse node
        # Reference object type
        class Reference(BaseModel):
            source_id: str = Field(
                ...,
                description="The unique identifier of the reference."
                )
            title: str = Field(
                ..., 
                escription="The title of the reference."
                )
            content: str = Field(
                ..., 
                description="The content of reference."
                )

        # List of Reference object type
        class ReferencedAnswer(BaseModel):
            """Parse the output of the LLM with tools to get the answer and references."""
            answer: str = Field(
                ...,
                description="The answer",
            )
            references: List[Reference] = Field(
                ...,
                description="List of the references of the SPECIFIC sources which justify the answer. Include ONLY the references used to create the answer.",
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
        await self.send(text_data=json.dumps(final_output))


            
