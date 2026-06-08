import os
import sys
from dotenv import load_dotenv

# Add the bot directory to path so we can import sheets_service
sys.path.append("/Users/kyawyelwin/kot-pjs/alineaintelegrambot")
import sheets_service

def run_test():
    load_dotenv("/Users/kyawyelwin/kot-pjs/alineaintelegrambot/.env")
    print("Testing connection to Customer Spreadsheet...")
    
    try:
        spreadsheet = sheets_service._get_customer_spreadsheet()
        print(f"✅ Successfully connected to: {spreadsheet.title}")
        
        worksheets = spreadsheet.worksheets()
        print(f"Found {len(worksheets)} worksheets.")
        
        if len(worksheets) < 2:
            print("❌ Error: The spreadsheet has less than 2 worksheets. Please add another one.")
            return
            
        print(f"Worksheet 1: {worksheets[0].title} (Will be used for Customer Info)")
        print(f"Worksheet 2: {worksheets[1].title} (Will be used for Order Items)")
        
        print("\nAll checks passed! The bot is ready to write to this spreadsheet.")
    except Exception as e:
        print(f"❌ Error during connection: {e}")

if __name__ == "__main__":
    run_test()
