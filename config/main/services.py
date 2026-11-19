"""Серверная бизнес-логика: смета, проверка лимита кухни, транзакции."""

import math
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    CateringOrder, KitchenDay, OrderItem, StaffShift, TablewareSet,
)

WAITERS_PER_GUEST = 15
COOKS_PER_GUEST = 60
TABLEWARE_PERSONS = 12
DEFAULT_CAPACITY = 250
MIN_GUESTS = 10
MAX_GUESTS = 400
MIN_DAYS_AHEAD = 3

STAFF_RATES = {
    StaffShift.ROLE_WAITER: Decimal('4500'),
    StaffShift.ROLE_COOK: Decimal('6000'),
    StaffShift.ROLE_BARTENDER: Decimal('6200'),
}


class KitchenUnavailable(Exception):
    """На выбранную дату не хватает суточного лимита кухни."""

    def __init__(self, requested_date, nearest_date, free_guests=0):
        self.requested_date = requested_date
        self.nearest_date = nearest_date
        self.free_guests = free_guests
        super().__init__(
            f'На {requested_date:%d.%m.%Y} свободно только {free_guests} мест.'
        )


def money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def staff_breakdown(guests):
    """Количество персонала пропорционально числу гостей (1 официант на 15)."""
    return {
        StaffShift.ROLE_WAITER: max(1, math.ceil(guests / WAITERS_PER_GUEST)),
        StaffShift.ROLE_COOK: max(1, math.ceil(guests / COOKS_PER_GUEST)),
        StaffShift.ROLE_BARTENDER: 1 if guests >= 40 else 0,
    }


def tableware_breakdown(guests):
    """Комплекты посуды и текстиля: считаются от числа гостей."""
    result = []
    sets = TablewareSet.objects.filter(is_active=True)
    for item in sets:
        qty = max(1, math.ceil(guests / item.persons_per_set))
        result.append({
            'set': item,
            'qty': qty,
            'cost': money(item.price * qty),
        })
    return result


def calculate_estimate(event_format, guests, decor_percent=0, template=None):
    """Смета: меню + оформление + персонал + посуда. Выход еды в граммах на гостя."""
    if template is None:
        template = event_format.templates.filter(is_active=True).first()

    if template is not None:
        price_per_guest = template.price_per_guest
        dishes = list(template.dishes.all())
        output_per_guest = sum(d.output_grams for d in dishes)
    else:
        price_per_guest = event_format.price_per_guest
        dishes = []
        output_per_guest = 0

    menu_total = money(price_per_guest * guests)
    decor_total = money(menu_total * Decimal(decor_percent) / Decimal(100))

    staff = staff_breakdown(guests)
    staff_total = money(sum(STAFF_RATES[role] * count for role, count in staff.items()))

    tableware = tableware_breakdown(guests)
    tableware_total = money(sum(row['cost'] for row in tableware))

    total = money(menu_total + decor_total + staff_total + tableware_total)
    norm = event_format.min_output_per_guest

    return {
        'template': template,
        'dishes': dishes,
        'guests': guests,
        'decor_percent': int(decor_percent),
        'price_per_guest': money(price_per_guest),
        'menu_total': menu_total,
        'decor_total': decor_total,
        'staff': staff,
        'staff_total': staff_total,
        'tableware': tableware,
        'tableware_total': tableware_total,
        'total': total,
        'output_per_guest': output_per_guest,
        'norm': norm,
        'output_ok': output_per_guest >= norm,
        'deficit': max(0, norm - output_per_guest),
        'staff_needed': staff[StaffShift.ROLE_WAITER],
        'tableware_needed': sum(row['qty'] for row in tableware if row['set'].kind == 'tableware'),
    }


def nearest_free_date(guests, start_date=None, days=45):
    """Ближайшая дата, где суточный лимит кухни позволяет принять заказ."""
    start_date = start_date or timezone.localdate()
    days_map = {
        row.date: row
        for row in KitchenDay.objects.filter(
            date__gte=start_date, date__lte=start_date + timedelta(days=days)
        )
    }
    for offset in range(1, days + 1):
        current = start_date + timedelta(days=offset)
        row = days_map.get(current)
        if row is None:
            return current
        if not row.is_closed and row.capacity_guests - row.booked_guests >= guests:
            return current
    return None


def get_kitchen_day(day, event_format=None):
    """Строка загрузки кухни на дату; создаётся с лимитом формата при отсутствии."""
    capacity = event_format.kitchen_daily_limit if event_format else DEFAULT_CAPACITY
    row, _ = KitchenDay.objects.get_or_create(
        date=day, defaults={'capacity_guests': capacity},
    )
    return row


@transaction.atomic
def place_order(*, user, event_format, event_date, guests, address,
                contact_name, contact_phone, contact_email,
                decor_percent, comment='', sketch=None, template=None):
    """Создание заказа: проверка кухни, заказ, позиции, смены и загрузка — в одной транзакции."""
    kitchen = get_kitchen_day(event_date, event_format)
    kitchen = KitchenDay.objects.select_for_update().get(pk=kitchen.pk)

    if kitchen.is_closed or kitchen.free_guests < guests:
        raise KitchenUnavailable(
            event_date,
            nearest_free_date(guests, event_date),
            kitchen.free_guests,
        )

    estimate = calculate_estimate(event_format, guests, decor_percent, template)
    template = estimate['template']

    order = CateringOrder(
        customer=user,
        event_format=event_format,
        menu_template=template,
        event_date=event_date,
        guests=guests,
        address=address,
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        decor_percent=decor_percent,
        comment=comment,
        status=CateringOrder.STATUS_NEW,
        menu_total=estimate['menu_total'],
        decor_total=estimate['decor_total'],
        staff_total=estimate['staff_total'],
        tableware_total=estimate['tableware_total'],
        total=estimate['total'],
        output_per_guest=estimate['output_per_guest'],
    )
    if sketch:
        order.sketch = sketch
    order.save()

    items = []
    for dish in estimate['dishes']:
        items.append(OrderItem(
            order=order, dish=dish, qty=guests, unit_price=dish.price,
        ))
    OrderItem.objects.bulk_create(items)

    shifts = []
    for role, people in estimate['staff'].items():
        if people:
            shifts.append(StaffShift(
                order=order, role=role, people=people,
                hours=event_format.duration_hours, rate=STAFF_RATES[role],
            ))
    StaffShift.objects.bulk_create(shifts)

    KitchenDay.objects.filter(pk=kitchen.pk).update(
        booked_guests=F('booked_guests') + guests,
    )

    notify_order_created(order)
    return order


@transaction.atomic
def update_order(order, *, event_date=None, guests=None, address=None, comment=None, sketch=None):
    """Изменение заказа с пересчётом сметы и корректировкой загрузки кухни."""
    old_guests, old_date = order.guests, order.event_date
    new_guests = guests or old_guests
    new_date = event_date or old_date

    old_kitchen = KitchenDay.objects.select_for_update().filter(date=old_date).first()
    if old_kitchen and new_date == old_date:
        free = old_kitchen.capacity_guests - old_kitchen.booked_guests + old_guests
        if new_guests > free:
            raise KitchenUnavailable(old_date, nearest_free_date(new_guests, old_date), free)
        old_kitchen.booked_guests = old_kitchen.booked_guests - old_guests + new_guests
        old_kitchen.save(update_fields=['booked_guests'])
    elif new_date != old_date:
        if old_kitchen:
            old_kitchen.booked_guests = max(0, old_kitchen.booked_guests - old_guests)
            old_kitchen.save(update_fields=['booked_guests'])
        new_kitchen = get_kitchen_day(new_date, order.event_format)
        new_kitchen = KitchenDay.objects.select_for_update().get(pk=new_kitchen.pk)
        if new_kitchen.is_closed or new_kitchen.free_guests < new_guests:
            raise KitchenUnavailable(new_date, nearest_free_date(new_guests, new_date),
                                     new_kitchen.free_guests)
        new_kitchen.booked_guests += new_guests
        new_kitchen.save(update_fields=['booked_guests'])

    estimate = calculate_estimate(event_format, new_guests, order.decor_percent, order.menu_template)
    order.event_date = new_date
    order.guests = new_guests
    if address:
        order.address = address
    if comment is not None:
        order.comment = comment
    if sketch:
        order.sketch = sketch
    order.menu_total = estimate['menu_total']
    order.decor_total = estimate['decor_total']
    order.staff_total = estimate['staff_total']
    order.tableware_total = estimate['tableware_total']
    order.total = estimate['total']
    order.output_per_guest = estimate['output_per_guest']
    order.save()

    order.items.all().delete()
    OrderItem.objects.bulk_create([
        OrderItem(order=order, dish=d, qty=new_guests, unit_price=d.price)
        for d in estimate['dishes']
    ])
    order.shifts.all().delete()
    StaffShift.objects.bulk_create([
        StaffShift(order=order, role=role, people=people,
                   hours=order.event_format.duration_hours, rate=STAFF_RATES[role])
        for role, people in estimate['staff'].items() if people
    ])
    return order


@transaction.atomic
def cancel_order(order):
    """Отмена заказа освобождает места на кухне в той же транзакции."""
    if order.status == CateringOrder.STATUS_CANCELLED:
        return order
    kitchen = KitchenDay.objects.select_for_update().filter(date=order.event_date).first()
    if kitchen:
        kitchen.booked_guests = max(0, kitchen.booked_guests - order.guests)
        kitchen.save(update_fields=['booked_guests'])
    order.status = CateringOrder.STATUS_CANCELLED
    order.save(update_fields=['status', 'updated_at'])
    notify_status_changed(order)
    return order


@transaction.atomic
def set_order_status(order, status):
    """Смена статуса менеджером; отмена возвращает места на кухню."""
    previous = order.status
    if status == CateringOrder.STATUS_CANCELLED and previous != CateringOrder.STATUS_CANCELLED:
        kitchen = KitchenDay.objects.select_for_update().filter(date=order.event_date).first()
        if kitchen:
            kitchen.booked_guests = max(0, kitchen.booked_guests - order.guests)
            kitchen.save(update_fields=['booked_guests'])
    order.status = status
    order.save(update_fields=['status', 'updated_at'])
    if previous != status:
        notify_status_changed(order)
    return order


def order_summary(order):
    template = order.menu_template or order.event_format.templates.filter(is_active=True).first()
    return calculate_estimate(order.event_format, order.guests, order.decor_percent, template)


def notify_order_created(order):
    subject = f'Заказ {order.number} принят — Банкетные решения'
    message = (
        f'Здравствуйте, {order.contact_name}!\n\n'
        f'Ваш заказ {order.number} на {order.event_date:%d.%m.%Y} принят.\n'
        f'Формат: {order.event_format.name}, гостей: {order.guests}.\n'
        f'Смета: {order.total} ₽.\n\n'
        'Менеджер проверит загрузку кухни и свяжется с вами.'
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
              [order.contact_email], fail_silently=True)


def notify_status_changed(order):
    subject = f'Статус заказа {order.number}: {order.get_status_display()}'
    message = (
        f'Статус вашего заказа {order.number} изменён на «{order.get_status_display()}».\n'
        f'Дата мероприятия: {order.event_date:%d.%m.%Y}, гостей: {order.guests}.\n'
        f'Сумма: {order.total} ₽.'
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
              [order.contact_email], fail_silently=True)


def dashboard_stats():
    """Сводные показатели для панели менеджера (агрегатные запросы ORM)."""
    from django.db.models import Avg, Count, Q, Sum

    base = CateringOrder.objects.exclude(status=CateringOrder.STATUS_CANCELLED)
    aggregates = base.aggregate(
        orders_count=Count('id'),
        revenue=Sum('total'),
        avg_check=Avg('total'),
        guests=Sum('guests'),
    )
    total_all = CateringOrder.objects.count()
    confirmed = CateringOrder.objects.filter(
        status__in=[CateringOrder.STATUS_CONFIRMED, CateringOrder.STATUS_COOKING,
                    CateringOrder.STATUS_DONE]
    ).count()
    cancelled = CateringOrder.objects.filter(status=CateringOrder.STATUS_CANCELLED).count()

    by_format = (
        CateringOrder.objects.values('event_format__name')
        .annotate(cnt=Count('id'), revenue=Sum('total'))
        .order_by('-cnt')
    )
    max_cnt = max([row['cnt'] for row in by_format], default=1) or 1
    chart = []
    for index, row in enumerate(by_format):
        height = max(8, round(row['cnt'] * 140 / max_cnt))
        chart.append({
            'label': row['event_format__name'],
            'count': row['cnt'],
            'revenue': row['revenue'] or 0,
            'percent': round(row['cnt'] * 100 / max_cnt),
            'x': 30 + index * 90,
            'y': 180 - height,
            'h': height,
            'label_x': 30 + index * 90 + 30,
        })

    return {
        'orders_count': aggregates['orders_count'] or 0,
        'revenue': aggregates['revenue'] or 0,
        'avg_check': aggregates['avg_check'] or 0,
        'guests': aggregates['guests'] or 0,
        'total_all': total_all,
        'confirmed': confirmed,
        'cancelled': cancelled,
        'confirmed_share': round(confirmed * 100 / total_all) if total_all else 0,
        'chart': chart,
    }


def parse_decor(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return value if value in (0, 10, 25) else 0
