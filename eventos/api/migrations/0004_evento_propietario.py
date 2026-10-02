from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0003_actualizacion_modelos'),
    ]

    operations = [
        # Se agrega permitiendo nulos para no romper bases con eventos previos al login.
        # La limpieza y el paso a obligatorio viven en 0005 y 0006.
        migrations.AddField(
            model_name='evento',
            name='propietario',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='eventos',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Organizador',
            ),
        ),
    ]
