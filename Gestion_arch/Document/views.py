import os
from datetime import datetime
import meilisearch
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import Document
from .tools import extract_text_from_pdf
from .tools import extract_text_from_docx
from urllib.parse import urlparse, parse_qs


@login_required(login_url='login')
def home_view(request):
    return render(request, 'home.html')




def upload_document(request):

    if request.method == 'POST' and request.FILES.getlist('file'):
        file_list = request.FILES.getlist('file')
        
        fs = FileSystemStorage(location='media/archives/')
        try:
            client = meilisearch.Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_MASTER_KEY)
            index = client.index('documents')

            index.update_ranking_rules([
            "words",      
            "typo",
            "proximity",
            "attribute",
            "sort",
            "exactness"])

            index.update_sortable_attributes(['word_count'])
            index.update_filterable_attributes(['author', 'year', 'month'])
        except Exception as e:
            print(f"Meilisearch Error: {e}")
            return JsonResponse({'status': 'error', 'message': "Meilisearch connection failed."}, status=500)

        batch_payloads = []
        success_count = 0

        for file_obj in file_list:
            _, ext = os.path.splitext(file_obj.name)
            ext = ext.lower()
            
            if ext not in ['.pdf', '.docx']:
                continue  

            try:
                saved_name = fs.save(file_obj.name, file_obj)
                full_text_path = f"media/archives/{saved_name}"
                
                new_doc = Document.objects.create(
                    name=file_obj.name,
                    file_path=full_text_path,
                    staff=request.user
                )

                if ext == '.pdf':
                    document_text = extract_text_from_pdf(new_doc.file_path)
                elif ext == '.docx':
                    document_text = extract_text_from_docx(new_doc.file_path)
                else:
                    document_text = ""

                author_username = new_doc.staff.username if new_doc.staff else "Admin"

            
                batch_payloads.append({
                    'id': new_doc.id,
                    'title': new_doc.name,
                    'content': document_text, 
                    'file_url': f"/media/archives/{saved_name}",
                    'author': author_username,
                    'year': new_doc.upload_at.year if new_doc.upload_at else datetime.now().year,
                    'month': new_doc.upload_at.month if new_doc.upload_at else datetime.now().month,
                })
                
                success_count += 1

            except Exception as file_error:
                print(f"Error processing file {file_obj.name}: {file_error}")
                continue

        if batch_payloads:
            try:
                index.add_documents(batch_payloads)
            except Exception as meili_error:
                print(f"Meilisearch Indexing Error: {meili_error}")
                return JsonResponse({'status': 'error', 'message': "Indexing failed."}, status=500)
                
        if success_count > 0:
            return JsonResponse({
                'status': 'success', 
                'message': 'Batch processed and indexed successfully.',
                'processed_in_batch': success_count
            })
            
        return JsonResponse({'status': 'warning', 'message': 'Aucun fichier valide n\'a été traité.'}, status=400)
        
    return render(request, 'upload.html')




def search_documents(request):
    User = get_user_model()
    authors = User.objects.filter(document__isnull=False).distinct()
    return render(request, 'search.html', {'authors': authors})



def meilisearch_proxy_api(request):
    query = request.GET.get('q', '').strip()
    author_filter = request.GET.get('author', '').strip()
    year_filter = request.GET.get('year', '').strip()   
    month_filter = request.GET.get('month', '').strip() 

    if not query:
        return JsonResponse({'hits': []})
        
    try:
        client = meilisearch.Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_MASTER_KEY)
        index = client.index('documents')

        search_params = {
            'attributesToHighlight': ['content'],  
            'highlightPreTag': '<mark>',          
            'highlightPostTag': '</mark>',        
            'attributesToCrop': ['content'],       
            'cropLength': 25,                    
            'cropMarker': '...',
            'attributesToSearchOn': ['content'],
        }

        search_response = index.search(query, search_params)
        raw_hits = search_response['hits']
        
        raw_hits.sort(
            key=lambda hit: hit.get('content', '').lower().count(query.lower()), 
            reverse=True
        )
        
        refined_hits = []
        for hit in raw_hits:
            doc_id = hit.get('id')
            try:
                db_doc = Document.objects.select_related('staff').get(id=doc_id)
                
                if author_filter and db_doc.staff and db_doc.staff.username != author_filter: continue
                if year_filter and str(db_doc.upload_at.year) != year_filter: continue
                if month_filter and str(db_doc.upload_at.month) != month_filter: continue

                refined_hits.append({
                    'id': db_doc.id,
                    'title': db_doc.name,
                    'content': hit.get('content', ''),
                    '_formatted': hit.get('_formatted', {}),
                    'author': db_doc.staff.username ,
                    'year': db_doc.upload_at.year ,
                    'month': db_doc.upload_at.month,
                })
            except Document.DoesNotExist:
                continue

        return JsonResponse({'hits': refined_hits})
        
    except Exception as e:
        print(f"Meilisearch Proxy Error: {e}")
        return JsonResponse({'hits': [], 'error': "Service indisponible"}, status=503)



def view_document_text(request, doc_id):
    try:
        db_doc = get_object_or_404(Document, id=doc_id)
        doc_name = db_doc.name
        
        raw_path = db_doc.file_path.strip().lstrip('/')
        file_url = f"/media/{raw_path}" if not raw_path.startswith('media/') else f"/{raw_path}"
        
        _, ext = os.path.splitext(doc_name)
        ext = ext.lower()
        file_type = 'pdf' if ext == '.pdf' else 'docx'
        
        full_text = ""
        try:
            import meilisearch
            client = meilisearch.Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_MASTER_KEY)
            index = client.index('documents')
            meili_doc = index.get_document(str(doc_id))
        
            full_text = meili_doc.get('content', '') if isinstance(meili_doc, dict) else getattr(meili_doc, 'content', '')
        except Exception:
            if ext == '.pdf':
                from .tools import extract_text_from_pdf
                full_text = extract_text_from_pdf(db_doc.file_path)
            elif ext == '.docx':
                from .tools import extract_text_from_docx
                full_text = extract_text_from_docx(db_doc.file_path)

        from django.utils.html import escapejs
        full_text_safe = escapejs(full_text)

        search_keyword = request.GET.get('q', '')
        if not search_keyword:
            referer = request.META.get('HTTP_REFERER', '')
            if 'q=' in referer:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(referer)
                params = parse_qs(parsed.query)
                search_keyword = params.get('q', [''])[0]

        context = {
            'doc_name': doc_name,
            'file_url': file_url,
            'file_type': file_type,
            'doc_id': doc_id,
            'search_keyword': search_keyword,
            'full_text': full_text,          
            'full_text_safe':full_text_safe 
        }
        return render(request, 'view_text.html', context)

    except Exception as e:
        return HttpResponse(f"Erreur: {str(e)}", status=404)



def download_document(request, doc_id):
    document = get_object_or_404(Document, id=doc_id)
    if document.file_path and os.path.exists(document.file_path):
        return FileResponse(open(document.file_path, 'rb'), as_attachment=True)
    else:
        raise Http404("Le fichier physique n'existe pas sur le serveur.")


# @login_required(login_url='login')
# def reindex_all_documents(request):
#     try:
#         client = meilisearch.Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_MASTER_KEY)
#         index = client.index('documents')
#         index.update_filterable_attributes(['author', 'year', 'month'])
        
#         all_docs = Document.objects.all()
#         refresh_payloads = []
        
#         for doc in all_docs:
#             _, ext = os.path.splitext(doc.name)
#             ext = ext.lower()
#             document_text = ""
            
#             if os.path.exists(doc.file_path):
#                 if ext == '.pdf':
#                     document_text = extract_text_from_pdf(doc.file_path)
#                 elif ext == '.docx':
#                     document_text = extract_text_from_docx(doc.file_path)

#             author_username = doc.staff.username if doc.staff else "Admin"

#             refresh_payloads.append({
#                 'id': doc.id,
#                 'title': doc.name,
#                 'content': document_text,
#                 'file_url': f"/{doc.file_path}",
#                 'author': author_username,  
#                 'year': doc.upload_at.year if doc.upload_at else datetime.now().year,
#                 'month': doc.upload_at.month if doc.upload_at else datetime.now().month,
#             })
            
#         if refresh_payloads:
#             index.add_documents(refresh_payloads)
            
#         return HttpResponse("Félicitations! Re-indexation réussie avec成功.")
#     except Exception as e:
#         return HttpResponse(f"Erreur: {str(e)}", status=500)