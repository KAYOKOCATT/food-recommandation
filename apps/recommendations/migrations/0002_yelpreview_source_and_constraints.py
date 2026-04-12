from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recommendations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="yelpreview",
            name="source",
            field=models.CharField(db_index=True, default="yelp", max_length=20),
        ),
    ]
