import os
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain.output_parsers.openai_tools import JsonOutputKeyToolsParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pprint import pprint



# Vriables
load_dotenv()
AZURE_OPENAI_DEPLOYMENT = "gpt-4o" # Inser deployment name of your LLM
AZURE_OPENAI_KEY = "e60b41829f7b4a9caebd05507cbc1158" # This is example. Insert your LLM key.
AZURE_OPENAI_ENDPOINT = "https://mysmbdemo.openai.azure.com/" # Insert your endpoint here.
AZURE_OPENAI_API_VERSION = "2024-06-01" # This is the lastest GA API version. You can use this. 

llm = AzureChatOpenAI(
azure_endpoint = AZURE_OPENAI_ENDPOINT,
azure_deployment = AZURE_OPENAI_DEPLOYMENT,
openai_api_key = AZURE_OPENAI_KEY,
openai_api_version = AZURE_OPENAI_API_VERSION,
temperature = 0
)



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


class UserInput(BaseModel):
    planning_pathway: str | None = Field(
        description='e.g., "Complying Development", "Local Council", "None"',
    )
    development_type: str | None = Field(
        description='e.g.,"Outbuilding (Garage)", Outbuilding (Carport), "New Dwelling", "None"',
    )
    zone: str | None  = Field(
        description='or "None"',
    )
    zone_description: str | None = Field(
        description='or "None"',
    )
    minimum_lot_size: str | None = Field(
        description='lot size (sqm) or "None"',
    )
    minimum_lot_width: str | None = Field(
        description='lot width (m) or "None"',
    )
    minimum_front_setback: str | None = Field(
        description='front setback (m) or "None"',
    )
    minimum_side_setback: str | None = Field(
        description='side setback (m) or "None"',
    )
    minimum_real_setback: str | None = Field(
        description='real setback (m) or "None"',
    )
    maximum_percentage_of_lot_used: str | None = Field(
        description='percentage of lot used (%) or "None"',
    )
    maximum_area: str | None = Field(
        description='area (sqm) or "None"',
    )
    maximum_building_height: str | None = Field(
        description='building height (m) or "None"',
    )
    additional_criteria: str | None = Field(
        description='Additional criteria or "None"',
    )


categories = [{'additional_criteria': 'No more than 1 garage per lot',
  'id': 'category1',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '60',
  'maximum_building_height': '3.5',
  'maximum_percentage_of_lot_used': '0.5',
  'minimum_front_setback': '4.5',
  'minimum_lot_size': '450',
  'minimum_lot_width': '15',
  'minimum_real_setback': '3',
  'minimum_side_setback': '0.9',
  'planning_pathway': 'Complying Development',
  'zone': 'R1',
  'zone_description': 'General Residential'},
 {'additional_criteria': 'No garage in front setback zone',
  'id': 'category2',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '60',
  'maximum_building_height': '3.5',
  'maximum_percentage_of_lot_used': '0.5',
  'minimum_front_setback': '6',
  'minimum_lot_size': '500',
  'minimum_lot_width': '15',
  'minimum_real_setback': '3',
  'minimum_side_setback': '0.9',
  'planning_pathway': 'Complying Development',
  'zone': 'R2',
  'zone_description': 'Low-Density Residential'},
 {'additional_criteria': 'Materials must match existing house',
  'id': 'category3',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '60',
  'maximum_building_height': '3.5',
  'maximum_percentage_of_lot_used': '0.45',
  'minimum_front_setback': '4',
  'minimum_lot_size': '400',
  'minimum_lot_width': '12',
  'minimum_real_setback': '3',
  'minimum_side_setback': '0.9',
  'planning_pathway': 'Complying Development',
  'zone': 'R3',
  'zone_description': 'Medium-Density Residential'},
 {'additional_criteria': 'Roof pitch ≤ 20 degrees',
  'id': 'category4',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '60',
  'maximum_building_height': '3.5',
  'maximum_percentage_of_lot_used': '0.45',
  'minimum_front_setback': '4',
  'minimum_lot_size': '400',
  'minimum_lot_width': '12',
  'minimum_real_setback': '3',
  'minimum_side_setback': '0.9',
  'planning_pathway': 'Complying Development',
  'zone': 'R4',
  'zone_description': 'High-Density Residential'},
 {'additional_criteria': 'Screening required for adjacent properties',
  'id': 'category5',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '100',
  'maximum_building_height': '4',
  'maximum_percentage_of_lot_used': '0.4',
  'minimum_front_setback': '10',
  'minimum_lot_size': '2000',
  'minimum_lot_width': '20',
  'minimum_real_setback': '5',
  'minimum_side_setback': '1.5',
  'planning_pathway': 'Complying Development',
  'zone': 'R5',
  'zone_description': 'Large Lot Residential'},
 {'additional_criteria': 'Flood-prone land restrictions apply',
  'id': 'category6',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '100',
  'maximum_building_height': '4.5',
  'maximum_percentage_of_lot_used': '0.2',
  'minimum_front_setback': '10',
  'minimum_lot_size': '10000',
  'minimum_lot_width': '50',
  'minimum_real_setback': '5',
  'minimum_side_setback': '5',
  'planning_pathway': 'Complying Development',
  'zone': 'RU1',
  'zone_description': 'Primary Production'},
 {'additional_criteria': 'Must retain rural character',
  'id': 'category7',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '100',
  'maximum_building_height': '4.5',
  'maximum_percentage_of_lot_used': '0.2',
  'minimum_front_setback': '10',
  'minimum_lot_size': '10000',
  'minimum_lot_width': '50',
  'minimum_real_setback': '5',
  'minimum_side_setback': '5',
  'planning_pathway': 'Complying Development',
  'zone': 'RU2',
  'zone_description': 'Rural Landscape'},
 {'additional_criteria': 'Vegetation clearance limited',
  'id': 'category8',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '80',
  'maximum_building_height': '4',
  'maximum_percentage_of_lot_used': '0.3',
  'minimum_front_setback': '10',
  'minimum_lot_size': '4000',
  'minimum_lot_width': '25',
  'minimum_real_setback': '5',
  'minimum_side_setback': '2.5',
  'planning_pathway': 'Complying Development',
  'zone': 'RU4',
  'zone_description': 'Primary Production Small Lots'},
 {'additional_criteria': 'Heritage controls may apply',
  'id': 'category9',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '80',
  'maximum_building_height': '4',
  'maximum_percentage_of_lot_used': '0.35',
  'minimum_front_setback': '6',
  'minimum_lot_size': '2000',
  'minimum_lot_width': '20',
  'minimum_real_setback': '3',
  'minimum_side_setback': '1.5',
  'planning_pathway': 'Complying Development',
  'zone': 'RU5',
  'zone_description': 'Village'},
 {'additional_criteria': 'Must be designed to minimize visual impact',
  'id': 'category10',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '50',
  'maximum_building_height': '4',
  'maximum_percentage_of_lot_used': '0.1',
  'minimum_front_setback': '20',
  'minimum_lot_size': '5000',
  'minimum_lot_width': '50',
  'minimum_real_setback': '10',
  'minimum_side_setback': '10',
  'planning_pathway': 'Complying Development',
  'zone': 'E2',
  'zone_description': 'Environmental Conservation'},
 {'additional_criteria': 'Bushfire management plan required',
  'id': 'category11',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '60',
  'maximum_building_height': '3.5',
  'maximum_percentage_of_lot_used': '0.2',
  'minimum_front_setback': '15',
  'minimum_lot_size': '4000',
  'minimum_lot_width': '30',
  'minimum_real_setback': '5',
  'minimum_side_setback': '5',
  'planning_pathway': 'Complying Development',
  'zone': 'E4',
  'zone_description': 'Environmental Living'},
 {'additional_criteria': 'Must align with tourist facility aesthetics',
  'id': 'category12',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '80',
  'maximum_building_height': '4',
  'maximum_percentage_of_lot_used': '0.25',
  'minimum_front_setback': '10',
  'minimum_lot_size': '1000',
  'minimum_lot_width': '20',
  'minimum_real_setback': '5',
  'minimum_side_setback': '2.5',
  'planning_pathway': 'Complying Development',
  'zone': 'SP3',
  'zone_description': 'Tourist'},
 {'additional_criteria': 'No commercial use allowed in garage',
  'id': 'category13',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': '60',
  'maximum_building_height': '3.5',
  'maximum_percentage_of_lot_used': '0.5',
  'minimum_front_setback': '4',
  'minimum_lot_size': '500',
  'minimum_lot_width': '15',
  'minimum_real_setback': '3',
  'minimum_side_setback': '0.9',
  'planning_pathway': 'Complying Development',
  'zone': 'MU1',
  'zone_description': 'Mixed Use'},
 {'additional_criteria': 'Any',
  'id': 'category14',
  'development_type': 'Outbuilding (Garage)',
  'maximum_area': 'Any',
  'maximum_building_height': 'Any',
  'maximum_percentage_of_lot_used': 'Any',
  'minimum_front_setback': 'Any',
  'minimum_lot_size': 'Any',
  'minimum_lot_width': 'Any',
  'minimum_real_setback': 'Any',
  'minimum_side_setback': 'Any',
  'planning_pathway': 'Local Council',
  'zone': 'Any',
  'zone_description': 'Any'},
 {'additional_criteria': 'Any',
  'id': 'category15',
  'development_type': 'Outbuilding (Carport)',
  'maximum_area': 'Any',
  'maximum_building_height': 'Any',
  'maximum_percentage_of_lot_used': 'Any',
  'minimum_front_setback': 'Any',
  'minimum_lot_size': 'Any',
  'minimum_lot_width': 'Any',
  'minimum_real_setback': 'Any',
  'minimum_side_setback': 'Any',
  'planning_pathway': 'Local Council',
  'zone': 'Any',
  'zone_description': 'Any'},
 {'additional_criteria': 'Any',
  'id': 'category16',
  'development_type': 'New Dwelling',
  'maximum_area': 'Any',
  'maximum_building_height': 'Any',
  'maximum_percentage_of_lot_used': 'Any',
  'minimum_front_setback': 'Any',
  'minimum_lot_size': 'Any',
  'minimum_lot_width': 'Any',
  'minimum_real_setback': 'Any',
  'minimum_side_setback': 'Any',
  'planning_pathway': 'Local Council',
  'zone': 'Any',
  'zone_description': 'Any'}]


user_input = "I want to build garage that is 3.6. meters high and area is 70 square meter"
user_input_json = output_json(user_input, UserInput, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION)

subset_matched = []
for category in categories:
  category_id = category["id"]
  subset_category = {key: category[key] for key in user_input_json.keys() if key in category}
  subset_category["id"] = category_id


  class IsMatched(BaseModel):
      f"""Does the user input match the criteria?"""
      id: str = Field(
          ...,
          description='Category field',
      )
      
      matched: bool = Field(
          ...,
          description='Whether user input matched with teh Development Category given',
      )
      reason: str = Field(
          ...,
          description='Reason why you made the "matched" decision',
      )


  input=f"""
  Does User input matches criteria?

  User input: {user_input_json}

  Criteria (JSON): 
    {subset_category}
  """
  output = output_json(input, IsMatched, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_KEY, AZURE_OPENAI_API_VERSION)
  if output["matched"]:
      subset_matched.append(output)
  pprint(output)

pprint(subset_matched)







subset_ids = {item['id'] for item in subset_matched}
matched = [category for category in categories if category['id'] in subset_ids]
pprint(matched)


input_best_question = f"""
In previous process, the user input was compared with list of categories to confirm the user input satisfies criteria of categories.
Matched Categories are all categories that matches Previous User Input.
Now, I want to ask user further question to narrow the Matched Categories down into 1. What series of question do I need to ask? Provie me ONLY question without reasoning.

Previous User Input: {user_input_json}

Matched Categories: {matched}

"""

best_question = llm.invoke(input_best_question).content
best_question

