from django.db import models
from django.conf import settings 

class Document(models.Model):
    name=models.CharField(max_length=200)
    upload_at=models.DateTimeField(auto_now_add=True)
    file_path=models.CharField(max_length=200)
    staff=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

def __str__(self):
    return self.name



