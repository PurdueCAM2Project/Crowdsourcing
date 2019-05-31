# Generated by Django 2.1.7 on 2019-05-30 17:38

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Phase',
            fields=[
                ('phase', models.CharField(max_length=10, primary_key=True, serialize=False)),
                ('get', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=list, size=None)),
                ('post', django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=list, size=None)),
            ],
        ),
    ]
