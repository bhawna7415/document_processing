import openai
import pdfplumber
import json
import os
import tiktoken

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

def count_tokens(text, model_name="gpt-4") -> int:
    """Count the number of tokens in a text using TikToken."""
    encoding = tiktoken.encoding_for_model(model_name)
    tokens = encoding.encode(text)
    return len(tokens)

def extract_text_from_pdfplumber(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            text += page.extract_text()
    return text

last_response = ""

def process_chunk(chunk, doc_key,last_response=last_response):
    if doc_key==1:
        task_2_prompt = f"""
                        you are working as an information extractor for non structured text data to transform it into a json object
                        you are currently working to create json objects of research papers, which are large in size
                        here is the first part of the research paper:-
                        =================
                        {chunk}
                        =================
                        the json object we are going to create must contain paper title, authors, abstract, key findings, and references.
                        if any of these information is not present in the part of research paper fill null value in that, you may get other parts of the research paper next time so you can fill them next time.
                        rules - 
                        property name must be enclosed in double quotes in json object
                        1.your final response should just be the json object, directly convertable using json.loads.
                        2.if any of the information is not present in the part of research paper just return json object with null values.
                        """
    else:
        task_2_prompt = f"""
                        you are working as an information extractor for non structured text data to transform it into a json object
                        you are currently working to complete json objects of research papers, which are large in size
                        you are getting the research paper in parts
                        we are searching for paper title, authors, abstract, key findings, and references in the paper.
                        some of it was present in the previous parts of the paper
                        your last response after {doc_key-1} part of research paper was -
                        ===============
                        {last_response}
                        ================

                        here is the {doc_key} of the research paper:-
                        =================
                        {chunk}
                        =================
                        the json object we are working on might have some null values in your last response.
                        search for those informations in this part of research paper.
                        key finding may not be in text as a particular heading, you have to find and update by yourself with new sub headings of paper
                        finally return the modified json object
                        rules - 
                        propety name must be enclosed in double quotes in json object
                        1. your final response should just be the json object, directly convertable using json.loads.
                        2. do not add any new field in json object
                        3. the information got in your response for last part should continue
                        4. if any of null information of previous response is not present in this part of research paper just return json object as it is.
                        5. formation of json object should not be disturbed
                    
                        """

    task_2_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": task_2_prompt},
        ]
    )

    # Extract the content from the response
    parsed_data = task_2_response.choices[0].message.content
    start_index = parsed_data.find('{')
    stripped_data = parsed_data[start_index:] if start_index != -1 else parsed_data
    return stripped_data

# Example PDF paths
pdf_paths = ['ml.pdf','sample.pdf']

# Create a list to store all documents
all_documents = []

for pdf_path in pdf_paths:

    extracted_text = extract_text_from_pdfplumber(pdf_path)

    token_count = count_tokens(extracted_text)
    print(f'Token count in {pdf_path}: {token_count}\n')

    if token_count > 2096:
        print(f'The extracted token count is greater than 2096: {token_count} tokens\n')
        
        chunk_size = 2000
        chunks = [extracted_text[i:i+chunk_size] for i in range(0, len(extracted_text), chunk_size)]
        last_response = ""
        for i, chunk in enumerate(chunks, start=1):
            document_dict = process_chunk(chunk, i,last_response=last_response)
            last_response = document_dict
        final = json.loads(last_response)
        all_documents.append(final)
    else:
        print(f'The extracted token count is less than or equal to 2096: {token_count} tokens\n')
        document_dict = process_chunk(extracted_text, 1) 
        final = json.loads(document_dict)
        all_documents.append(final)
        
# Write the entire list to the JSON file
with open('output.json', 'w') as json_file:
    json.dump(all_documents, json_file, indent=2)