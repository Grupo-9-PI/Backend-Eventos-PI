from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def eliminar_eventos_sin_propietario(apps, schema_editor):
    # Los eventos creados antes del login local no tienen organizador y no hay
    # datos que conservar de ese sprint: se eliminan junto con sus gestiones (CASCADE).
    Evento = apps.get_model('api', 'Evento')
    Evento.objects.filter(propietario__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('api', '0003_actualizacion_modelos'),
    ]

    operations = [
        # 1. Se agrega permitiendo nulos para no romper bases que ya tienen eventos.
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
        # 2. Se limpian los eventos huérfanos del sprint anterior.
        migrations.RunPython(eliminar_eventos_sin_propietario, migrations.RunPython.noop),
        # 3. Ahora sí, el dueño pasa a ser obligatorio.
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
