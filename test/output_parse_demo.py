import os
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# Vriables
load_dotenv()
AZURE_OPENAI_DEPLOYMENT = "gpt-4o" # Inser deployment name of your LLM
AZURE_OPENAI_KEY = "e60b41829f7b4a9caebd05507cbc1158" # This is example. Insert your LLM key.
AZURE_OPENAI_ENDPOINT = "https://mysmbdemo.openai.azure.com/" # Insert your endpoint here.
AZURE_OPENAI_API_VERSION = "2024-06-01" # This is the lastest GA API version. You can use this. 



def output_json(input:str, schema:BaseModel, AZURE_OPENAI_ENDPOINT:str, AZURE_OPENAI_DEPLOYMENT:str, AZURE_OPENAI_KEY:str, AZURE_OPENAI_API_VERSION:str):
    # Define LLM
    llm = AzureChatOpenAI(
    azure_endpoint = AZURE_OPENAI_ENDPOINT,
    azure_deployment = AZURE_OPENAI_DEPLOYMENT,
    openai_api_key = AZURE_OPENAI_KEY,
    openai_api_version = AZURE_OPENAI_API_VERSION,
    temperature = 0
    )

    # Define a chain 
    chain = (
        llm.bind_tools(
            [schema],
            tool_choice = schema.__name__
        ) |
        JsonOutputKeyToolsParser(
            key_name = schema.__name__ ,
            first_tool_only = True
        )
    )

    # Invoke the chain
    return chain.invoke(input)


class Development(BaseModel):
    category: str = Field(
        ...,
        description='Category that matches user input',
    )
    planning_pathway: str = Field(
        ...,
        description='"Planning Pathway" field THE Category',
    )
    development_type: str = Field(
        ...,
        description='"Development Type" field THE Category',
    )
    zone: str = Field(
        ...,
        description='"Zone" field THE Category',
    )
    zone_description: str = Field(
        ...,
        description='"Zone Description" field THE Category',
    )
    minimum_lot_size: str = Field(
        ...,
        description='"Minimum Lot Size (sqm)" field THE Category',
    )
    minimum_lot_width: str = Field(
        ...,
        description='"Minimum Lot Width (m)" field THE Category',
    )
    minimum_front_setback: str = Field(
        ...,
        description='"Minimum Front Setback (m)" field THE Category',
    )
    minimum_side_setback: str = Field(
        ...,
        description='"Minimum Side Setback (m)" field THE Category',
    )
    minimum_real_setback: str = Field(
        ...,
        description='"Minimum Rear Setback (m)" field THE Category',
    )
    maximum_percentage_of_lot_used: str = Field(
        ...,
        description='"Maximum Percentage of Lot Used (%)" field THE Category',
    )
    maximum_area: str = Field(
        ...,
        description='"Maximum Area (sqm)" field THE Category',
    )
    maximum_building_height: str = Field(
        ...,
        description='"Maximum Building Height (m)" field THE Category',
    )
    additional_criteria: str = Field(
        ...,
        description='"Additional Criteria" field THE Category',
    )
    reason: str = Field(
        ...,
        description='Reason why this category satisfies user input',
    )



class MatchedDevelopment(BaseModel):
    """Only list Development category that match user input. Be cautious with 'Minimum' and 'Maximum'"""
    satisfied_category: List[Development] = Field(
        ...,
        description='Development that matches user input',
    )

input="""
Userw ask about development planning question. Your task is to guide users to appropriate Category. Each 'Development Category' below  has criteria and you should provide If user input safisfy criteria in each  Development Category, then the category is considered as matched. 
Note 'Development Category' is an array of json.
You MUST provide ONLY matched Development Category.

Development Category:
[
  { 
    "Category": "category1",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "R1",
    "Zone Description": "General Residential",
    "Minimum Lot Size (sqm)": "450",
    "Minimum Lot Width (m)": "15",
    "Minimum Front Setback (m)": "4.5",
    "Minimum Side Setback (m)": "0.9",
    "Minimum Rear Setback (m)": "3",
    "Maximum Percentage of Lot Used (%)": "0.5",
    "Maximum Area (sqm)": "60",
    "Maximum Building Height (m)": "3.5",
    "Additional Criteria": "No more than 1 garage per lot"
  },
  {
    "Category": "category2",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "R2",
    "Zone Description": "Low-Density Residential",
    "Minimum Lot Size (sqm)": "500",
    "Minimum Lot Width (m)": "15",
    "Minimum Front Setback (m)": "6",
    "Minimum Side Setback (m)": "0.9",
    "Minimum Rear Setback (m)": "3",
    "Maximum Percentage of Lot Used (%)": "0.5",
    "Maximum Area (sqm)": "60",
    "Maximum Building Height (m)": "3.5",
    "Additional Criteria": "No garage in front setback zone"
  },
  {
    "Category": "category3",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "R3",
    "Zone Description": "Medium-Density Residential",
    "Minimum Lot Size (sqm)": "400",
    "Minimum Lot Width (m)": "12",
    "Minimum Front Setback (m)": "4",
    "Minimum Side Setback (m)": "0.9",
    "Minimum Rear Setback (m)": "3",
    "Maximum Percentage of Lot Used (%)": "0.45",
    "Maximum Area (sqm)": "60",
    "Maximum Building Height (m)": "3.5",
    "Additional Criteria": "Materials must match existing house"
  },
  {
    "Category": "category4",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "R4",
    "Zone Description": "High-Density Residential",
    "Minimum Lot Size (sqm)": "400",
    "Minimum Lot Width (m)": "12",
    "Minimum Front Setback (m)": "4",
    "Minimum Side Setback (m)": "0.9",
    "Minimum Rear Setback (m)": "3",
    "Maximum Percentage of Lot Used (%)": "0.45",
    "Maximum Area (sqm)": "60",
    "Maximum Building Height (m)": "3.5",
    "Additional Criteria": "Roof pitch ≤ 20 degrees"
  },
  {
    "Category": "category5",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "R5",
    "Zone Description": "Large Lot Residential",
    "Minimum Lot Size (sqm)": "2000",
    "Minimum Lot Width (m)": "20",
    "Minimum Front Setback (m)": "10",
    "Minimum Side Setback (m)": "1.5",
    "Minimum Rear Setback (m)": "5",
    "Maximum Percentage of Lot Used (%)": "0.4",
    "Maximum Area (sqm)": "100",
    "Maximum Building Height (m)": "4",
    "Additional Criteria": "Screening required for adjacent properties"
  },
  {
    "Category": "category6",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "RU1",
    "Zone Description": "Primary Production",
    "Minimum Lot Size (sqm)": "10000",
    "Minimum Lot Width (m)": "50",
    "Minimum Front Setback (m)": "10",
    "Minimum Side Setback (m)": "5",
    "Minimum Rear Setback (m)": "5",
    "Maximum Percentage of Lot Used (%)": "0.2",
    "Maximum Area (sqm)": "100",
    "Maximum Building Height (m)": "4.5",
    "Additional Criteria": "Flood-prone land restrictions apply"
  },
  {
    "Category": "category7",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "RU2",
    "Zone Description": "Rural Landscape",
    "Minimum Lot Size (sqm)": "10000",
    "Minimum Lot Width (m)": "50",
    "Minimum Front Setback (m)": "10",
    "Minimum Side Setback (m)": "5",
    "Minimum Rear Setback (m)": "5",
    "Maximum Percentage of Lot Used (%)": "0.2",
    "Maximum Area (sqm)": "100",
    "Maximum Building Height (m)": "4.5",
    "Additional Criteria": "Must retain rural character"
  },
  {
    "Category": "category8",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "RU4",
    "Zone Description": "Primary Production Small Lots",
    "Minimum Lot Size (sqm)": "4000",
    "Minimum Lot Width (m)": "25",
    "Minimum Front Setback (m)": "10",
    "Minimum Side Setback (m)": "2.5",
    "Minimum Rear Setback (m)": "5",
    "Maximum Percentage of Lot Used (%)": "0.3",
    "Maximum Area (sqm)": "80",
    "Maximum Building Height (m)": "4",
    "Additional Criteria": "Vegetation clearance limited"
  },
  {
    "Category": "category9",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "RU5",
    "Zone Description": "Village",
    "Minimum Lot Size (sqm)": "2000",
    "Minimum Lot Width (m)": "20",
    "Minimum Front Setback (m)": "6",
    "Minimum Side Setback (m)": "1.5",
    "Minimum Rear Setback (m)": "3",
    "Maximum Percentage of Lot Used (%)": "0.35",
    "Maximum Area (sqm)": "80",
    "Maximum Building Height (m)": "4",
    "Additional Criteria": "Heritage controls may apply"
  },
  {
    "Category": "category10",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "E2",
    "Zone Description": "Environmental Conservation",
    "Minimum Lot Size (sqm)": "5000",
    "Minimum Lot Width (m)": "50",
    "Minimum Front Setback (m)": "20",
    "Minimum Side Setback (m)": "10",
    "Minimum Rear Setback (m)": "10",
    "Maximum Percentage of Lot Used (%)": "0.1",
    "Maximum Area (sqm)": "50",
    "Maximum Building Height (m)": "4",
    "Additional Criteria": "Must be designed to minimize visual impact"
  },
  {
    "Category": "category11",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "E4",
    "Zone Description": "Environmental Living",
    "Minimum Lot Size (sqm)": "4000",
    "Minimum Lot Width (m)": "30",
    "Minimum Front Setback (m)": "15",
    "Minimum Side Setback (m)": "5",
    "Minimum Rear Setback (m)": "5",
    "Maximum Percentage of Lot Used (%)": "0.2",
    "Maximum Area (sqm)": "60",
    "Maximum Building Height (m)": "3.5",
    "Additional Criteria": "Bushfire management plan required"
  },
  {
    "Category": "category12",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "SP3",
    "Zone Description": "Tourist",
    "Minimum Lot Size (sqm)": "1000",
    "Minimum Lot Width (m)": "20",
    "Minimum Front Setback (m)": "10",
    "Minimum Side Setback (m)": "2.5",
    "Minimum Rear Setback (m)": "5",
    "Maximum Percentage of Lot Used (%)": "0.25",
    "Maximum Area (sqm)": "80",
    "Maximum Building Height (m)": "4",
    "Additional Criteria": "Must align with tourist facility aesthetics"
  },
  {
    "Category": "category13",
    "Planning Pathway": "Complying Development",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "MU1",
    "Zone Description": "Mixed Use",
    "Minimum Lot Size (sqm)": "500",
    "Minimum Lot Width (m)": "15",
    "Minimum Front Setback (m)": "4",
    "Minimum Side Setback (m)": "0.9",
    "Minimum Rear Setback (m)": "3",
    "Maximum Percentage of Lot Used (%)": "0.5",
    "Maximum Area (sqm)": "60",
    "Maximum Building Height (m)": "3.5",
    "Additional Criteria": "No commercial use allowed in garage"
  },
  {
    "Category": "category14",
    "Planning Pathway": "Local Council",
    "Development Type": "Outbuilding (Garage)",
    "Zone": "Any",
    "Zone Description": "Any",
    "Minimum Lot Size (sqm)": "Any",
    "Minimum Lot Width (m)": "Any",
    "Minimum Front Setback (m)": "Any",
    "Minimum Side Setback (m)": "Any",
    "Minimum Rear Setback (m)": "Any",
    "Maximum Percentage of Lot Used (%)": "Any",
    "Maximum Area (sqm)": "Any",
    "Maximum Building Height (m)": "Any",
    "Additional Criteria": "Any"
  },
  {
    "Category": "category15",
    "Planning Pathway": "Local Council",
    "Development Type": "Outbuilding (Carport)",
    "Zone": "Any",
    "Zone Description": "Any",
    "Minimum Lot Size (sqm)": "Any",
    "Minimum Lot Width (m)": "Any",
    "Minimum Front Setback (m)": "Any",
    "Minimum Side Setback (m)": "Any",
    "Minimum Rear Setback (m)": "Any",
    "Maximum Percentage of Lot Used (%)": "Any",
    "Maximum Area (sqm)": "Any",
    "Maximum Building Height (m)": "Any",
    "Additional Criteria": "Any"
  },
  {
    "Category": "category16",
    "Planning Pathway": "Local Council",
    "Development Type": "New Dwelling",
    "Zone": "Any",
    "Zone Description": "Any",
    "Minimum Lot Size (sqm)": "Any",
    "Minimum Lot Width (m)": "Any",
    "Minimum Front Setback (m)": "Any",
    "Minimum Side Setback (m)": "Any",
    "Minimum Rear Setback (m)": "Any",
    "Maximum Percentage of Lot Used (%)": "Any",
    "Maximum Area (sqm)": "Any",
    "Maximum Building Height (m)": "Any",
    "Additional Criteria": "Any"
  }
]

User input: I want to build garage in busy area that is 3.6 meter.
"""
output = output_json(input, MatchedDevelopment, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION)
from pprint import pprint
pprint(output)