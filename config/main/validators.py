"""Валидаторы загружаемых файлов: проверка расширения и размера."""

import os

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_upload_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            'Допустимые форматы: PNG, JPG, WEBP, PDF. '
            f'Вы загрузили файл с расширением «{ext or "без расширения"}».'
        )


def validate_upload_size(value):
    if value.size > settings.MAX_UPLOAD_SIZE:
        raise ValidationError('Размер файла не должен превышать 5 МБ.')
