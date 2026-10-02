from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_limpiar_eventos_sin_propietario'),
    ]

    operations = [
        # Ya sin eventos huérfanos, el organizador pasa a ser obligatorio.
        migrations.AlterField(
            model_name='evento',
            name='propietario',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='eventos',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Organizador',
            ),
        ),
    ]
