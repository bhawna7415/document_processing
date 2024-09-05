import openai
import json
import os

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)
# Load the JSON file
with open('output.json', 'r') as file:
    research_papers = json.load(file)

prompt = f"""
here is the data extracted from multiple research papers in json format -
================
{research_papers}
================
each paper contains title, abstract, key-findings.
Provide a one paragraph summary for each research paper by extracting relevant information from the 'Abstract' and 'Key Findings' sections.
rules - 
1. summary should not contain sub-headings and pointwise description
2. summary must be only a simple paragraph to understand base Idea
3. use formation like - 'paper1 title: one paragraph summary \npaper2 title - one paragraph summary' 
"""

# Make the API call to openai
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
)

# Extract and print the generated summary
generated_summary = response.choices[0].message.content
print(generated_summary)