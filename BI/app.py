from gpt_researcher import GPTResearcher
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
AZURE_OPENAI_KEY = os.getenv('AZURE_OPENAI_KEY')
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT_EMBEDDING = os.getenv('AZURE_OPENAI_DEPLOYMENT_EMBEDDING')
AZURE_OPENAI_API_VERSION=os.getenv('AZURE_OPENAI_API_VERSION')
AZURE_OPENAI_DEPLOYMENT_4=os.getenv('AZURE_OPENAI_DEPLOYMENT_4')
os.environ['AZURE_OPENAI_API_KEY'] = AZURE_OPENAI_KEY
os.environ['TAVILY_API_KEY'] = TAVILY_API_KEY
os.environ['AZURE_EMBEDDING_MODEL'] = AZURE_OPENAI_DEPLOYMENT_EMBEDDING
os.environ['OPENAI_API_VERSION'] = AZURE_OPENAI_API_VERSION
os.environ['AZURE_OPENAI_ENDPOINT'] = AZURE_OPENAI_ENDPOINT
os.environ['EMBEDDING_PROVIDER']="azure_openai"
os.environ['LLM_PROVIDER']="azure_openai"
os.environ['DEFAULT_LLM_MODEL']=AZURE_OPENAI_DEPLOYMENT_4
os.environ['FAST_LLM_MODEL']=AZURE_OPENAI_DEPLOYMENT_4
os.environ['SMART_LLM_MODEL']=AZURE_OPENAI_DEPLOYMENT_4




async def get_report(query: str, report_type: str) -> str:
    researcher = GPTResearcher(query, report_type)
    research_result = await researcher.conduct_research()
    report = await researcher.write_report()
    return report






































if __name__ == "__main__":
    query = "I am running AI Start up company. I am curious abnout which business incentives are out there in NSW Australia?"
    report_type = "research_report"

    report = asyncio.run(get_report(query, report_type))
    print(report)





