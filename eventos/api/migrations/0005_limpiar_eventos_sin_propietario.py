from django.db import migrations


def eliminar_eventos_sin_propietario(apps, schema_editor):
    # Los eventos creados antes del login local no tienen organizador y no hay
    # datos que conservar de ese sprint: se eliminan junto con sus gestiones (CASCADE).
    Evento = apps.get_model('api', 'Evento')
    Evento.objects.filter(propietario__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_evento_propietario'),
    ]

    operations = [
        # En su propia migración: el commit de este borrado resuelve los triggers
        # pendientes antes de que 0006 altere la tabla (requisito de PostgreSQL).
        migrations.RunPython(eliminar_eventos_sin_propietario, migrations.RunPython.noop),
    ]
