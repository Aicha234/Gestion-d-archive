import os
import fitz  # PyMuPDF
import meilisearch
from django.conf import settings

def extract_text_from_pdf(file_path):

    if not os.path.exists(file_path):
        return ""
        
    extracted_text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            page_text = page.get_text()
            if page_text:
                extracted_text += page_text + "\n"
        doc.close()
    except Exception as e:
        print(f"Error reading PDF with PyMuPDF at {file_path}: {str(e)}")
        return ""
        
    return extracted_text.strip()


# def index_document_in_meilisearch(doc_id, doc_name, doc_text):
   
#     try:
#         client = meilisearch.Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_MASTER_KEY)
#         index = client.index('documents')
#         document_payload = {
#             'id': doc_id,         
#             'name': doc_name,      
#             'text': doc_text       
#         }
        
#         index.add_documents([document_payload])
#         return True
#     except Exception as e:
#         print(f"Meilisearch Indexing Error: {str(e)}")
#         return False


from docx import Document as DocxReader

def extract_text_from_docx(file_path):
   
    text = ""
    try:
        doc = DocxReader(file_path)
        
        for paragraph in doc.paragraphs:
            if paragraph.text:
                text += paragraph.text + "\n"
                
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text += cell.text.strip() + " "
                text += "\n"
                
    except Exception as e:
        print(f"Erreur d'extraction DOCX: {e}")
        
    return text.strip()