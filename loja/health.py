from django.db import connection
from django.http import JsonResponse


def healthcheck(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
        return JsonResponse({'status': 'ok'})
    except Exception as erro:
        return JsonResponse({'status': 'erro', 'detalhe': str(erro)}, status=500)
