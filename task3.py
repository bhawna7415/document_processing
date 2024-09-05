from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
import pdfplumber
import openai
import os

embeddings = OpenAIEmbeddings()

def extract_text_from_pdfplumber(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            text += page.extract_text()
    return text

pdfs = ['ml.pdf','nuclear.pdf','sample.pdf']
list_of_docs = []

for pdf in pdfs:
    text = extract_text_from_pdfplumber(pdf)
    new_doc = Document(page_content=text,metadata=dict(source=pdf))
    list_of_docs.append(new_doc)

db = FAISS.from_documents(list_of_docs, embeddings)
results_with_scores = db.similarity_search_with_score("machine learning")

result,score = results_with_scores[0]
the_pdf = result.metadata['source']
the_text = extract_text_from_pdfplumber(the_pdf)
chunk_size = 1000
chunks = [the_text[i:i+chunk_size] for i in range(0, len(the_text), chunk_size)]

pages = []
for i,chunk in enumerate(chunks,start=1):
    new_doc = Document(page_content=chunk,metadata=dict(page=i))
    pages.append(new_doc)

db = FAISS.from_documents(pages, embeddings)
results_author = db.similarity_search("authors")

prompt = f"""
            you are searching for title and authors in a research paper
            here is the first part of the research paper to search title - 
            ============
            {chunks[0]}
            ============
            and here is the part of research paper to search authors names - 
            ============
            {results_author}
            ============

            provide title and authors of the research paper
            """

client = openai.OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
    )

final_output = response.choices[0].message.content

print(final_output)
