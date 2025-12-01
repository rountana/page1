import asyncio
import os
from dotenv import load_dotenv
from chatbot import ChatBot

# Load environment variables from .env file
load_dotenv()

async def main():
    try:
        bot = ChatBot()
        print("ChatBot initialized. Type 'exit' or 'quit' to stop.")
        print("----------------------------------------------------")
        json_path = "/Users/shaamsarath/Devstudio/projects/page1/data/data.json"
        bot.load_json_context(json_path)
        
    except ValueError as e:
        print(f"Error: {e}")
        return

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ('exit', 'quit'):
                print("Goodbye!")
                break
            
            response = await bot.chat(user_input)
            print(f"Bot: {response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
