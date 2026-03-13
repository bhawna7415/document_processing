from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
from pydantic import BaseModel
import os
import json
import re
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Dict
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from app.system_prompt import SYSTEM_PROMPT
from app.invoice_system_prompt import INVOICE_SYSTEM_PROMPT
from app.credit_memo_system_prompt import CREDIT_MEMO_SYSTEM_PROMPT

class EmailAttachment(BaseModel):
    filename: str
    content: str  # Base64
    contentType: str
    emailSubject: str = ""
    emailFrom: str = ""

load_dotenv()

openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
AZURE_OPENAI_DEPLOYMENT = os.environ["AZURE_DEPLOYMENT"]
doc_intelligence_endpoint = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT")
doc_intelligence_key = os.getenv("AZURE_DOC_INTELLIGENCE_KEY")

document_analysis_client = DocumentAnalysisClient(
    endpoint=doc_intelligence_endpoint,
    credential=AzureKeyCredential(doc_intelligence_key)
)

app = FastAPI(title="Sales order generation")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_document_type(subject: str) -> str:
    subject_lower = subject.lower()
    if "purchase order" in subject_lower or "po" in subject_lower:
        return "purchase_order"
    elif "invoice" in subject_lower:
        return "invoice"
    elif "credit memo" in subject_lower:
        return "credit_memo"
    return "unknown"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def validate_and_save_file(file: UploadFile) -> Path:
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ["pdf", "png", "jpg", "jpeg", "tiff", "bmp", "webp"]:
        raise HTTPException(
            status_code=400,
            detail="Only PDF or image files supported (PDF, PNG, JPG, JPEG, TIFF, BMP)"
        )
    file_path = Path(UPLOAD_FOLDER) / file.filename
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    return file_path

def ask_azure_openai(prompt_text: str, system_prompt: str) -> str:
    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": prompt_text}
        ]
    )
    return response.choices[0].message.content

def clean_json_response(text: str) -> Dict[str, Any]:
    try:
        text = re.sub(r"```(?:json)?", "", text).strip()
        return json.loads(text)
    except Exception:
        try:
            match = re.search(r"{.*}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            return {"error": "Failed to parse JSON", "raw": text}

def extract_document_content(file_path: str) -> str:
    with open(file_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document(
            model_id="prebuilt-document",
            document=f
        )
        result = poller.result()
    extracted_text = ""
    for page_num, page in enumerate(result.pages, start=1):
        extracted_text += f"\n--- Page {page_num} ---\n"
        for line in page.lines:
            extracted_text += line.content + "\n"

    if result.tables:
        extracted_text += "\n\n=== TABLES ===\n"
        for table_idx, table in enumerate(result.tables, start=1):
            extracted_text += f"\n--- Table {table_idx} ---\n"
            extracted_text += f"Rows: {table.row_count}, Columns: {table.column_count}\n"
            table_data = {}
            for cell in table.cells:
                row = cell.row_index
                col = cell.column_index
                table_data.setdefault(row, {})[col] = cell.content
            for row_idx in sorted(table_data.keys()):
                row_cells = table_data[row_idx]
                row_text = " | ".join([row_cells.get(col, "") for col in sorted(row_cells.keys())])
                extracted_text += row_text + "\n"

    if result.key_value_pairs:
        extracted_text += "\n\n=== KEY-VALUE PAIRS ===\n"
        for kv in result.key_value_pairs:
            key = kv.key.content if kv.key else ""
            value = kv.value.content if kv.value else ""
            if key or value:
                extracted_text += f"{key}: {value}\n"

    return extracted_text.strip()

def extract_document_content_invoice_model(file_path: str) -> str:
    with open(file_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document(
            model_id="prebuilt-invoice",
            document=f
        )
        result = poller.result()
    extracted_text = ""
    for doc in result.documents:
        extracted_text += "\n=== STRUCTURED DATA ===\n"
        fields = doc.fields
        if "InvoiceId" in fields:
            extracted_text += f"Invoice/PO Number: {fields['InvoiceId'].value}\n"
        if "InvoiceDate" in fields:
            extracted_text += f"Date: {fields['InvoiceDate'].value}\n"
        if "DueDate" in fields:
            extracted_text += f"Due Date: {fields['DueDate'].value}\n"
        if "VendorName" in fields:
            extracted_text += f"Vendor: {fields['VendorName'].value}\n"
        if "CustomerName" in fields:
            extracted_text += f"Customer: {fields['CustomerName'].value}\n"

        if "Items" in fields:
            extracted_text += "\n=== LINE ITEMS ===\n"
            items = fields["Items"].value
            for idx, item in enumerate(items, start=1):
                extracted_text += f"\nItem {idx}:\n"
                item_fields = item.value
                if "Description" in item_fields:
                    extracted_text += f"  Description: {item_fields['Description'].value}\n"
                if "Quantity" in item_fields:
                    extracted_text += f"  Quantity: {item_fields['Quantity'].value}\n"
                if "UnitPrice" in item_fields:
                    extracted_text += f"  Unit Price: {item_fields['UnitPrice'].value}\n"
                if "Amount" in item_fields:
                    extracted_text += f"  Amount: {item_fields['Amount'].value}\n"

        if "SubTotal" in fields:
            extracted_text += f"\nSubtotal: {fields['SubTotal'].value}\n"
        if "TotalTax" in fields:
            extracted_text += f"Total Tax: {fields['TotalTax'].value}\n"
        if "InvoiceTotal" in fields:
            extracted_text += f"Total: {fields['InvoiceTotal'].value}\n"

    extracted_text += "\n\n=== RAW TEXT ===\n"
    for page in result.pages:
        for line in page.lines:
            
            extracted_text += line.content + "\n"
    return extracted_text.strip()

@app.post("/process-email-attachment")
async def process_email_attachment(attachment: EmailAttachment):
    # Decode base64
    file_content = base64.b64decode(attachment.content)
    
    # Save temporarily
    file_path = Path(UPLOAD_FOLDER) / attachment.filename
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Detect type
    doc_type = detect_document_type(attachment.emailSubject)
    
    # Use your existing code
    if doc_type == "purchase_order":
        extracted = extract_document_content(str(file_path))
        ai_response = ask_azure_openai(extracted, SYSTEM_PROMPT)
    elif doc_type == "invoice":
        extracted = extract_document_content_invoice_model(str(file_path))
        ai_response = ask_azure_openai(extracted, INVOICE_SYSTEM_PROMPT)
    elif doc_type == "credit_memo":
        extracted = extract_document_content_invoice_model(str(file_path))
        ai_response = ask_azure_openai(extracted, CREDIT_MEMO_SYSTEM_PROMPT)
    
    json_output = clean_json_response(ai_response)
    
    os.remove(file_path)
    
    return JSONResponse(content={
        "success": True,
        "filename": attachment.filename,
        "document_type": doc_type,
        "extraction_result": json_output
    })

@app.post("/upload_po")
async def upload_purchase_order(file: UploadFile = File(...)):
    file_path = validate_and_save_file(file)
    try:
        extracted = extract_document_content(str(file_path))
        ai_response = ask_azure_openai(extracted, SYSTEM_PROMPT)
        json_output = clean_json_response(ai_response)
        return JSONResponse(content={"jsonResult": json_output})
    finally:
        os.remove(file_path)

@app.post("/upload_invoice")
async def upload_invoice(file: UploadFile = File(...)):
    file_path = validate_and_save_file(file)
    try:
        extracted = extract_document_content_invoice_model(str(file_path))
        ai_response = ask_azure_openai(extracted, INVOICE_SYSTEM_PROMPT)
        json_output = clean_json_response(ai_response)
        return JSONResponse(content={"jsonResult": json_output})
    finally:
        os.remove(file_path)

@app.post("/upload_credit_memo")
async def upload_credit_memo(file: UploadFile = File(...)):
    file_path = validate_and_save_file(file)
    try:
        extracted = extract_document_content_invoice_model(str(file_path))
        ai_response = ask_azure_openai(extracted, CREDIT_MEMO_SYSTEM_PROMPT)
        json_output = clean_json_response(ai_response)
        return JSONResponse(content={"jsonResult": json_output})
    finally:
        os.remove(file_path)



