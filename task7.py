import openai
import json
import os

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

key_findings = input("Enter the key findings for the research paper: ")

prompt = f"""
Generate an abstract for a new research paper based on the following key findings:
{key_findings}
The abstract should provide a concise summary of the research, highlighting its significance and key contributions.
"""

# Make the API call to openai
response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )

# Extract and print the generated abstract
abstract = response.choices[0].message.content
print(f"Generated Abstract:\n{abstract}")
