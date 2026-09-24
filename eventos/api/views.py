from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Evento, Subtarea
from .serializers import EventoSerializer, SubtareaSerializer

class EventoViewSet(viewsets.ModelViewSet):
    queryset = Evento.objects.all()
    serializer_class = EventoSerializer

    # Este decorador crea automáticamente la ruta GET/POST /api/eventos/<id>/subtareas/
    @action(detail=True, methods=['get', 'post'])
    def subtareas(self, request, pk=None):
        evento = self.get_object() # Busca el evento por el ID que está en la URL

        if request.method == 'GET':
            # Devuelve todas las subtareas que pertenecen a este evento específico
            subtareas = evento.subtareas.all()
            serializer = SubtareaSerializer(subtareas, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Toma los datos que envía React y le inyecta automáticamente el ID del evento actual
            datos = request.data.copy()
            datos['evento'] = evento.id
            
            serializer = SubtareaSerializer(data=datos)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
