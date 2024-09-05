import openai
import json
import os

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)
# Load the JSON file
with open('output.json', 'r') as file:
    research_papers = json.load(file)

# Set up openai API key
openai.api_key = os.environ["OPENAI_API_KEY"]

# Iterate through each research paper and get user input for a query
for doc in research_papers:
    doc_key = list(doc.keys())[0]
    paper_data = doc[doc_key]
    
user_query = input(f"Enter your query here:")

prompt = f"""
provide me answer of {user_query} from json file:\n{research_papers}\n.Don't provide any other information outside from given json file.
"""
# Make the API call to openai
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
)
# Extract and print the generated response
answer = response.choices[0].message.content
print(f"Query Response:\n{answer}\n")