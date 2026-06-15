from django.test import TestCase

# Create your tests here.



import os
import meilisearch
from django.conf import settings
from Document.models import Document


try:

    client = meilisearch.Client(settings.MEILISEARCH_HOST, settings.MEILISEARCH_MASTER_KEY)

    index = client.index('documents')

    index.delete_all_documents()

    print("done")

except Exception as meili_error:

    print(f"failed {meili_error}")




documents = Document.objects.all()

deleted_files_count = 0

for doc in documents:

    if doc.file_path and os.path.exists(doc.file_path):

        os.remove(doc.file_path)

        deleted_files_count += 1

        print(f"File deleted: {doc.file_path}")



if documents.exists():
    documents.delete()

    print(f"done :{deleted_files_count})

else:

    print("thre is no document ")



print("\n Fin")