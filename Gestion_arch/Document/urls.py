from django.urls import path 
from . import views

urlpatterns = [
    
    path('home/', views.home_view, name='home'),
    path('upload/', views.upload_document, name='upload_page'), 
    path('search/', views.search_documents, name='search_page'),
    path('document/<int:doc_id>/text/', views.view_document_text, name='view_document_text'),
    path('api/search-instant/', views.meilisearch_proxy_api, name='search_instant_api'),
    path('document/<int:doc_id>/download/', views.download_document, name='download_document'),
    # path('maintenance/reindex-all/', views.reindex_all_documents, name='reindex_all_documents'),
]


  