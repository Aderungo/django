"""Модели предметной области «кейтеринг и выездные банкеты» (вариант 16).

Сущности: формат мероприятия, категория блюда, блюдо, готовый сет (M2M),
загрузка кухни по суткам, заказ кейтеринга, позиция заказа, комплект посуды,
смена персонала, отзыв, обращение, профиль заказчика.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .validators import validate_upload_extension, validate_upload_size


def ru_slug(value):
    """Slug для кириллицы: транслитерация не нужна, оставляем читаемый адрес."""
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    prepared = ''.join(table.get(ch.lower(), ch) if ch.lower() in table else ch for ch in value)
    return slugify(prepared) or slugify(str(timezone.now().timestamp()).replace('.', ''))


class EventFormat(models.Model):
    """Формат мероприятия: фуршет, банкет, кофе-брейк."""

    name = models.CharField('Название', max_length=80, unique=True)
    slug = models.SlugField('Слаг', max_length=80, unique=True, blank=True)
    description = models.TextField('Описание', blank=True)
    price_per_guest = models.DecimalField('Цена за гостя, ₽', max_digits=10, decimal_places=2)
    min_output_per_guest = models.PositiveIntegerField('Рекомендуемая норма выхода, г/чел.')
    duration_hours = models.PositiveSmallIntegerField('Длительность, ч', default=4)
    kitchen_daily_limit = models.PositiveIntegerField('Суточный лимит кухни, гостей', default=250)
    is_active = models.BooleanField('Активен', default=True)
    sort_order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Формат мероприятия'
        verbose_name_plural = 'Форматы мероприятий'
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ru_slug(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('main:catalog') + f'?format={self.slug}'


class DishCategory(models.Model):
    name = models.CharField('Название', max_length=80, unique=True)
    slug = models.SlugField('Слаг', max_length=80, unique=True, blank=True)
    description = models.CharField('Описание', max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Категория блюда'
        verbose_name_plural = 'Категории блюд'
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ru_slug(self.name)
        super().save(*args, **kwargs)


class Dish(models.Model):
    """Блюдо или услуга меню. Цена — за порцию, гостя или штуку."""

    UNIT_PORTION = 'portion'
    UNIT_GUEST = 'guest'
    UNIT_ITEM = 'item'
    UNIT_CHOICES = (
        (UNIT_PORTION, 'порция'),
        (UNIT_GUEST, 'гость'),
        (UNIT_ITEM, 'шт.'),
    )

    category = models.ForeignKey(
        DishCategory, verbose_name='Категория', on_delete=models.PROTECT,
        related_name='dishes',
    )
    name = models.CharField('Название', max_length=120)
    slug = models.SlugField('Слаг', max_length=140, unique=True, blank=True)
    description = models.TextField('Описание', blank=True)
    composition = models.CharField('Состав', max_length=250, blank=True)
    price = models.DecimalField('Цена, ₽', max_digits=10, decimal_places=2)
    unit = models.CharField('Единица', max_length=10, choices=UNIT_CHOICES, default=UNIT_PORTION)
    output_grams = models.PositiveIntegerField('Выход, г', default=0)
    image = models.FileField(
        'Фото', upload_to='dishes/', blank=True,
        validators=[validate_upload_extension, validate_upload_size],
    )
    is_active = models.BooleanField('Доступно', default=True)
    is_popular = models.BooleanField('Популярное', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Блюдо'
        verbose_name_plural = 'Блюда'
        ordering = ('category__sort_order', 'name')
        indexes = [models.Index(fields=['is_active', 'category'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ru_slug(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('main:dish_detail', args=[self.slug])

    @property
    def price_display(self):
        return f'{self.price:,.0f}'.replace(',', ' ')


class MenuTemplate(models.Model):
    """Готовый сет: связь «многие ко многим» с блюдами."""

    name = models.CharField('Название сета', max_length=120, unique=True)
    slug = models.SlugField('Слаг', max_length=140, unique=True, blank=True)
    event_format = models.ForeignKey(
        EventFormat, verbose_name='Формат', on_delete=models.CASCADE,
        related_name='templates',
    )
    description = models.TextField('Описание', blank=True)
    dishes = models.ManyToManyField(Dish, verbose_name='Блюда', related_name='templates')
    price_per_guest = models.DecimalField('Цена за гостя, ₽', max_digits=10, decimal_places=2)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Готовый сет'
        verbose_name_plural = 'Готовые сеты'
        ordering = ('event_format__sort_order', 'name')

    def __str__(self):
        return f'{self.name} ({self.event_format.name})'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ru_slug(self.name)
        super().save(*args, **kwargs)

    def output_per_guest(self):
        """Суммарный выход сета в граммах на одного гостя."""
        return sum(d.output_grams for d in self.dishes.all())


class KitchenDay(models.Model):
    """Загрузка кухни на конкретные сутки: лимит и уже занятые гости."""

    date = models.DateField('Дата', unique=True)
    capacity_guests = models.PositiveIntegerField('Лимит гостей', default=250)
    booked_guests = models.PositiveIntegerField('Забронировано гостей', default=0)
    is_closed = models.BooleanField('Кухня закрыта', default=False)
    note = models.CharField('Примечание', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Загрузка кухни'
        verbose_name_plural = 'Загрузка кухни'
        ordering = ('date',)

    def __str__(self):
        return f'{self.date:%d.%m.%Y} — {self.booked_guests}/{self.capacity_guests}'

    @property
    def free_guests(self):
        if self.is_closed:
            return 0
        return max(0, self.capacity_guests - self.booked_guests)

    @property
    def load_percent(self):
        if not self.capacity_guests:
            return 100
        return min(100, round(self.booked_guests * 100 / self.capacity_guests))


class CateringOrder(models.Model):
    STATUS_NEW = 'new'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COOKING = 'cooking'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_NEW, 'Новая'),
        (STATUS_CONFIRMED, 'Подтверждён'),
        (STATUS_COOKING, 'Готовится'),
        (STATUS_DONE, 'Завершён'),
        (STATUS_CANCELLED, 'Отменён'),
    )

    DECOR_CHOICES = (
        (0, 'Без оформления'),
        (10, 'Стандарт (+10 %)'),
        (25, 'Сложное (+25 %)'),
    )

    number = models.CharField('Номер заказа', max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Заказчик', on_delete=models.CASCADE,
        related_name='orders',
    )
    event_format = models.ForeignKey(
        EventFormat, verbose_name='Формат', on_delete=models.PROTECT,
        related_name='orders',
    )
    menu_template = models.ForeignKey(
        MenuTemplate, verbose_name='Готовый сет', on_delete=models.SET_NULL,
        related_name='orders', null=True, blank=True,
    )
    event_date = models.DateField('Дата мероприятия')
    guests = models.PositiveIntegerField('Гостей')
    address = models.CharField('Адрес', max_length=250)
    contact_name = models.CharField('Контактное лицо', max_length=120)
    contact_phone = models.CharField('Телефон', max_length=24)
    contact_email = models.EmailField('E-mail')
    decor_percent = models.PositiveSmallIntegerField('Оформление, %', choices=DECOR_CHOICES, default=10)
    comment = models.TextField('Комментарий', blank=True)
    sketch = models.FileField(
        'Эскиз оформления', upload_to='sketches/', blank=True,
        validators=[validate_upload_extension, validate_upload_size],
    )
    status = models.CharField('Статус', max_length=12, choices=STATUS_CHOICES, default=STATUS_NEW)
    menu_total = models.DecimalField('Меню, ₽', max_digits=12, decimal_places=2, default=0)
    decor_total = models.DecimalField('Оформление, ₽', max_digits=12, decimal_places=2, default=0)
    staff_total = models.DecimalField('Персонал, ₽', max_digits=12, decimal_places=2, default=0)
    tableware_total = models.DecimalField('Посуда, ₽', max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField('Итого, ₽', max_digits=12, decimal_places=2, default=0)
    output_per_guest = models.PositiveIntegerField('Выход, г/чел.', default=0)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Заказ кейтеринга'
        verbose_name_plural = 'Заказы кейтеринга'
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['event_date', 'status'])]

    def __str__(self):
        return f'{self.number} · {self.contact_name}'

    def save(self, *args, **kwargs):
        if not self.number:
            stamp = timezone.localdate().strftime('%y%m')
            last = CateringOrder.objects.filter(number__startswith=f'BR-{stamp}').count() + 1
            self.number = f'BR-{stamp}-{last:03d}'
            while CateringOrder.objects.filter(number=self.number).exists():
                last += 1
                self.number = f'BR-{stamp}-{last:03d}'
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('main:order_detail', args=[self.pk])

    @property
    def status_css(self):
        return {
            self.STATUS_NEW: 'badge-warning',
            self.STATUS_CONFIRMED: 'badge-success',
            self.STATUS_COOKING: 'badge-neutral',
            self.STATUS_DONE: 'badge-neutral',
            self.STATUS_CANCELLED: 'badge-error',
        }.get(self.status, 'badge-neutral')

    @property
    def can_edit(self):
        """Менять заказ можно не позднее чем за 48 часов и пока он не отменён."""
        if self.status == self.STATUS_CANCELLED:
            return False
        return (self.event_date - timezone.localdate()).days >= 2

    @property
    def sketch_is_image(self):
        name = (self.sketch.name or '').lower()
        return name.endswith(('.png', '.jpg', '.jpeg', '.webp'))


class OrderItem(models.Model):
    order = models.ForeignKey(
        CateringOrder, verbose_name='Заказ', on_delete=models.CASCADE,
        related_name='items',
    )
    dish = models.ForeignKey(Dish, verbose_name='Блюдо', on_delete=models.PROTECT)
    qty = models.PositiveIntegerField('Количество', default=1)
    unit_price = models.DecimalField('Цена за единицу, ₽', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
        ordering = ('dish__category__sort_order', 'dish__name')

    def __str__(self):
        return f'{self.dish.name} × {self.qty}'

    @property
    def total(self):
        return self.unit_price * self.qty


class TablewareSet(models.Model):
    KIND_CHOICES = (
        ('tableware', 'Посуда'),
        ('textile', 'Текстиль'),
        ('furniture', 'Мебель'),
    )
    name = models.CharField('Название', max_length=120, unique=True)
    kind = models.CharField('Тип', max_length=12, choices=KIND_CHOICES, default='tableware')
    description = models.CharField('Описание', max_length=200, blank=True)
    price = models.DecimalField('Цена комплекта, ₽', max_digits=10, decimal_places=2)
    persons_per_set = models.PositiveIntegerField('Гостей на комплект', default=12)
    is_active = models.BooleanField('Доступен', default=True)

    class Meta:
        verbose_name = 'Комплект посуды и текстиля'
        verbose_name_plural = 'Комплекты посуды и текстиля'
        ordering = ('kind', 'name')

    def __str__(self):
        return f'{self.name} ({self.persons_per_set} чел.)'


class StaffShift(models.Model):
    ROLE_WAITER = 'waiter'
    ROLE_COOK = 'cook'
    ROLE_BARTENDER = 'bartender'
    ROLE_CHOICES = (
        (ROLE_WAITER, 'Официант'),
        (ROLE_COOK, 'Повар'),
        (ROLE_BARTENDER, 'Бармен'),
    )

    order = models.ForeignKey(
        CateringOrder, verbose_name='Заказ', on_delete=models.CASCADE,
        related_name='shifts',
    )
    role = models.CharField('Роль', max_length=12, choices=ROLE_CHOICES)
    people = models.PositiveSmallIntegerField('Человек', default=1)
    hours = models.PositiveSmallIntegerField('Часов', default=4)
    rate = models.DecimalField('Ставка за смену, ₽', max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Смена персонала'
        verbose_name_plural = 'Смены персонала'
        ordering = ('role',)

    def __str__(self):
        return f'{self.get_role_display()} × {self.people}'

    @property
    def cost(self):
        return self.rate * self.people


class Review(models.Model):
    order = models.ForeignKey(
        CateringOrder, verbose_name='Заказ', on_delete=models.CASCADE,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Автор', on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField('Оценка', default=5)
    text = models.TextField('Текст отзыва')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=['order', 'user'], name='unique_review_per_order'),
        ]

    def __str__(self):
        return f'{self.order.number} — {self.rating}/5'


class ContactRequest(models.Model):
    name = models.CharField('Имя', max_length=120)
    email = models.EmailField('E-mail')
    phone = models.CharField('Телефон', max_length=24, blank=True)
    message = models.TextField('Сообщение')
    consent = models.BooleanField('Согласие на обработку данных', default=False)
    processed = models.BooleanField('Обработано', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Обращение'
        verbose_name_plural = 'Обращения'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.name} · {self.created_at:%d.%m.%Y}'


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name='Пользователь', on_delete=models.CASCADE,
        related_name='profile',
    )
    phone = models.CharField('Телефон', max_length=24, blank=True)
    full_name = models.CharField('Имя и фамилия', max_length=120, blank=True)
    consent = models.BooleanField('Согласие на обработку данных', default=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return self.full_name or self.user.username
