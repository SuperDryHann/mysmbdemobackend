import os
import json
from backend.auth_azure import websocket_authenticated
from dotenv import load_dotenv
from pprint import pprint
from typing import(
    Annotated, 
    Sequence, 
    TypedDict, 
    List
)
from langchain_core.messages import (
    BaseMessage, 
    ToolMessage, 
    SystemMessage, 
    AIMessageChunk,
    HumanMessage, 
    AIMessage
)
from langgraph.graph.message import add_messages
from langchain_openai import (
    AzureChatOpenAI, 
    AzureOpenAIEmbeddings
)
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.azuresearch import AzureSearch
from langgraph.graph import (
    StateGraph,
    START,
    END
)
from langgraph.checkpoint.memory import MemorySaver
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from langchain.pydantic_v1 import (
    BaseModel, 
    Field
)
from langchain.tools import StructuredTool
from langgraph.prebuilt import ToolNode
from utils.miscellaneous import (
    get_claim_from_token_ws, 
    get_parameter_ws
)
from utils.langchain.tools import tool_retriever_local
from utils.langchain.utils import OrmChatMessageHistory
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery
from openai import AzureOpenAI
from asgiref.sync import sync_to_async
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages.base import messages_to_dict



async def achat_rag(
        self: AsyncWebsocketConsumer,
        user_input: str, 
        index_name: str,
        chat_message_history: BaseChatMessageHistory,
        tools: list[StructuredTool],
        AZURE_OPENAI_ENDPOINT: str, 
        AZURE_OPENAI_DEPLOYMENT: str,
        AZURE_OPENAI_KEY: str, 
        AZURE_OPENAI_API_VERSION: str, 
        AZURE_SEARCH_ENDPOINT: str, 
        AZURE_SEARCH_KEY: str):



    # LLM instance
    llm = AzureChatOpenAI(
        azure_endpoint = AZURE_OPENAI_ENDPOINT,
        azure_deployment = AZURE_OPENAI_DEPLOYMENT,
        openai_api_key = AZURE_OPENAI_KEY,
        openai_api_version = AZURE_OPENAI_API_VERSION
        )



    # Chat history instance
    chat_history=await chat_message_history.aget_messages
    chat_history_subset=chat_history[-10:]



    # tool_retriever_local
    tool_retriever_local_instance = tool_retriever_local(
        index_name=index_name,
        AZURE_SEARCH_ENDPOINT=AZURE_SEARCH_ENDPOINT,
        AZURE_SEARCH_KEY=AZURE_SEARCH_KEY,
        title_field="title",
        content_field="chunk",
        vector_field="chunk_vector",
        semantic_search_inclusion=["title", "chunk", "chunk_id"]
    )



    # Graph state
    class AgentState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        final_output: dict
        answer: str
        references: List[dict]



    # Node and Endge functions
    # Tool excution node
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
    user_input_langchain = [HumanMessage(content=user_input)]

    output = AIMessageChunk(content="")
    config = {"configurable": {"thread_id": "1"}}
    async for msg, metadata in graph.astream(input = {"messages" : user_input_langchain}, config = config, stream_mode="messages"):
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
    human_message=HumanMessage(content=user_input)
    ai_message=AIMessage(content=answer)
    langchain_messages: Sequence[BaseMessage]=[human_message, ai_message]
    serialised_messages = messages_to_dict(langchain_messages)

    await chat_message_history.aadd_messages(serialised_messages)
    


    # Send the final message
    await self.send(text_data=json.dumps(final_output))
