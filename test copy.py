import os
from dotenv import load_dotenv
from pprint import pprint
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
import json
from langchain_core.messages import ToolMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_openai import AzureOpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from langgraph.graph import StateGraph, END
from langgraph.constants import END

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



# LLM instance
llm = AzureChatOpenAI(
    azure_endpoint = AZURE_OPENAI_ENDPOINT,
    azure_deployment = AZURE_OPENAI_DEPLOYMENT_4,
    openai_api_key = AZURE_OPENAI_KEY,
    openai_api_version = AZURE_OPENAI_API_VERSION
    )



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

# Create the retriever tool
retriever_tool = create_retriever_tool(
    retriever,
    "retrieve_knowledge",
    "Retrieve reference documents from databases outside of current knowledge")



# Graph state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]



# LLM with tools
tools = [retriever_tool]

llm_with_tools = llm.bind_tools(tools)



# Tool node
tools_by_name = {tool.name: tool for tool in tools}

def tool_node(state: AgentState):
    outputs = []
    for tool_call in state["messages"][-1].tool_calls: # Get the last message and its tool calls decision
        tool_result = tools_by_name[tool_call["name"]].invoke(tool_call["args"]) # Invoke the tool
        # print("****************************************************************************************************")
        # print(tool_result)
        # print("****************************************************************************************************")
        outputs.append(
            ToolMessage(
                content=json.dumps(tool_result),
                name=tool_call["name"],
                tool_call_id=tool_call["id"],
            )
        )
    return {"messages": outputs}





# Function call node
def call_model(
    state: AgentState,
    config: RunnableConfig,
):
    # this is similar to customizing the create_react_agent with state_modifier, but is a lot more flexible
    system_prompt = SystemMessage(
        "You are a AI assistant, please respond to the users query based on reference documents. NEVER use facts outside of the reference. If you cannot answer based on the reference, say you don't know.",
    )
    response = llm_with_tools.invoke([system_prompt] + state["messages"], config)
    return {"messages": [response]}



# Conditional edge
def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]

    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"




# Define graph
workflow = StateGraph(AgentState)



# Nodes
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)



# Edges (from, condition function, mapping "(result: next node)"")
# Conditional edge
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "end": END,
    },
)

# Edge (tool -> agent)
workflow.add_edge("tools", "agent")



# Compile the graph
workflow.set_entry_point("agent")
graph = workflow.compile()




# Helper function for formatting the stream nicely
def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()


inputs = {"messages": [("user", "Who is president of UNSW?")]}
print_stream(graph.stream(inputs, stream_mode="values"))