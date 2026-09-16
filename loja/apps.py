from django.apps import AppConfig


class LojaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loja'
    verbose_name = 'Loja (E-commerce)'  # nome amigável mostrado no admin
