from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('artifacts', '0008_alter_artifact_image_url_alter_artifact_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='artifact',
            name='keyword',
            field=models.TextField(blank=True),
        ),
    ]
