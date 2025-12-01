from typing import List, Optional
import os
import json
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.messages import ModelMessage
from ddgs import DDGS

class ChatBot:
    def __init__(self, model_name: str = 'gemini-2.5-flash', api_key: Optional[str] = None):
        if api_key:
            os.environ['GEMINI_API_KEY'] = api_key
        elif not os.getenv('GEMINI_API_KEY'):
             raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.model = GeminiModel(model_name)
        self.system_prompt = "You are a helpful chat bot with memory. You remember details from the conversation."
        self.agent = Agent(self.model, system_prompt=self.system_prompt)
        self.history: List[ModelMessage] = []
        self.hotel_data_dir = "hotel_data"

    def load_json_context(self, file_path: str):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # 1. Initialize Consolidated Hotel File
            self.consolidated_file = "consolidated_hotels.json"
            
            hotels = data.get("hotels", [])
            
            # Load existing consolidated data if file exists, otherwise start fresh
            consolidated_data = {}
            if os.path.exists(self.consolidated_file):
                try:
                    with open(self.consolidated_file, 'r') as hf:
                        consolidated_data = json.load(hf)
                except Exception as e:
                    print(f"Warning: Could not load existing consolidated file: {e}. Starting fresh.")
                    consolidated_data = {}
            
            # Merge/update with hotels from input data
            for hotel in hotels:
                h_id = hotel.get("hotel_id")
                h_name = hotel.get("name")
                if h_id and h_name:
                    if h_id in consolidated_data:
                        # Update existing hotel: preserve existing fields, update hotel_name if changed
                        # consolidated_data[h_id]["hotel_name"] = h_name
                        # Keep existing hotel_id (should be the same)
                        if "hotel_id" not in consolidated_data[h_id]:
                            consolidated_data[h_id]["hotel_id"] = h_id
                    else:
                        # Add new hotel entry
                        consolidated_data[h_id] = {
                            "hotel_name": h_name,
                            "hotel_id": h_id
                        }
            
            with open(self.consolidated_file, 'w') as hf:
                json.dump(consolidated_data, hf, indent=2)

            context_str = json.dumps(data, indent=2)
            self.system_prompt += (
                f"\n\nHere is some context from a file:\n{context_str}\n\n"
                "Use this context to answer questions. If the answer is not explicitly in the file "
                "(e.g., proximity to landmarks like parks), use your general knowledge based on the "
                "address or coordinates provided in the file.\n\n"
                "IMPORTANT: When you determine that specific hotels match a user's criteria (e.g., are near a park), "
                "you MUST use the `update_hotel_record` tool to update the records for those specific hotels. "
                "Infer the `field_name` from the question (e.g., 'situated_near_park') and provide a 'justification'."
                "\n\nYou also have access to a `web_search` tool. Use it to find information about the hotels, their surroundings, or any other general knowledge questions the user asks if you don't know the answer."
            )
            
            # 2. Define Tool
            # 2. Define Tool
            from pydantic import BaseModel, Field
            
            class HotelUpdateArgs(BaseModel):
                hotel_id: str = Field(..., description="The ID of the hotel to update.")
                field_name: str = Field(..., description="The inferred boolean field name.")
                value: bool = Field(..., description="True or False.")
                justification: str = Field(..., description="The reason for this value.")
                
                # This configuration helps prevent 'additionalProperties' from appearing in the generated JSON schema,
                # which causes 400 errors with the Gemini API.
                model_config = {'extra': 'ignore'}

            class SearchArgs(BaseModel):
                query: str = Field(..., description="The search query to submit to the search engine.")
                model_config = {'extra': 'ignore'}

            def web_search(ctx: RunContext[None], args: SearchArgs) -> str:
                """
                Perform a web search to find information not present in the context.
                """
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.text(args.query, max_results=5))
                        if not results:
                            return "No results found."
                        return json.dumps(results, indent=2)
                except Exception as e:
                    return f"Error performing search: {str(e)}"


            async def update_hotel_record(ctx: RunContext[None], args: HotelUpdateArgs) -> str:
                """
                Updates the record for a specific hotel in the consolidated file.
                """
                hotel_id = args.hotel_id
                field_name = args.field_name
                value = args.value
                justification = args.justification

                if not os.path.exists(self.consolidated_file):
                    return "Error: Consolidated hotel file not found."
                
                try:
                    with open(self.consolidated_file, 'r') as hf:
                        all_records = json.load(hf)
                    
                    if hotel_id not in all_records:
                        return f"Error: Hotel ID {hotel_id} not found in records."
                    
                    all_records[hotel_id][field_name] = value
                    all_records[hotel_id]["justification"] = justification
                    
                    with open(self.consolidated_file, 'w') as hf:
                        json.dump(all_records, hf, indent=2)
                    return f"Successfully updated record for {hotel_id}."
                except Exception as e:
                    return f"Error updating record: {str(e)}"

            # 3. Re-initialize Agent with Tool
            self.agent = Agent(
                self.model, 
                system_prompt=self.system_prompt,
                tools=[update_hotel_record, web_search]
            )
            print(f"Loaded context from {file_path} and initialized consolidated records in '{self.consolidated_file}'.")
        except Exception as e:
            print(f"Error loading JSON context: {e}")

    async def chat(self, user_input: str) -> str:
        # Run the agent with the current history
        result = await self.agent.run(user_input, message_history=self.history)
        
        # Update history with the new messages (user input + model response)
        # result.new_messages() returns the messages added during this run
        self.history.extend(result.new_messages())
        
        return result.output
