from django.db import models

# Create your models here.
class Courses(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    duration = models.CharField(max_length=50)
    is_paid = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=6, decimal_places=2,default=0.00)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    thumbnail  = models.ImageField(upload_to='courses/thumbnails/',blank=True,null=True)
    intro_video = models.FileField(upload_to='courses/videos/',blank=True,null=True)
    attachment  = models.FileField(upload_to='courses/attachments/',blank=True,null=True)

    def __str__(self):
        return self.title