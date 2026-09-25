from django.db import models

# Create your models here.

from django.db import models

class Evento(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del evento")
    lugar = models.CharField(max_length=255, verbose_name="Lugar")
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_final = models.DateField(verbose_name="Fecha final")
    hora = models.TimeField(verbose_name="Hora del evento")
    duracion_horas = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Duración del evento (horas)")
    limite_diario_horas = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Límite diario de trabajo (horas)")
    notas_produccion = models.TextField(blank=True, null=True, verbose_name="Notas de producción")

    def __str__(self):
        return self.nombre

    

class Subtarea(models.Model):
    # Esta es la pieza clave que conecta la tarea con un evento existente
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='subtareas')
    
    gestion = models.CharField(max_length=255, verbose_name="Nueva gestión")
    
    # Opciones de categorías (puedes editar los nombres según las que ustedes tengan definidas)
    OPCIONES_CATEGORIA = [
        ('SALON', 'Salón'),
        ('INVITACIONES', 'Invitaciones'),
        ('CATERING', 'Catering'),
        ('PROVEEDORES', 'Proveedores'),
        ('OTRO', 'Otro')
    ]
    categoria = models.CharField(max_length=50, choices=OPCIONES_CATEGORIA, verbose_name="Categoría")
    
    estimacion_horas = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Estimación (horas)")
    plazo = models.DateField(verbose_name="Plazo (fecha)")
    hora_limite = models.TimeField(verbose_name="Hora límite")

    def __str__(self):
        return f"{self.gestion} - {self.evento.nombre}"