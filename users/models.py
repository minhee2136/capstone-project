from django.db import models


class User(models.Model):
    id = models.AutoField(primary_key=True)
    nickname = models.CharField(max_length=100)
    gender = models.CharField(max_length=20)
    birth_year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nickname
