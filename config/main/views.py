"""Представления сайта кейтеринга: каталог, калькулятор, заказы, панель менеджера."""

import csv
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    CalculatorForm, ContactForm, DishForm, LoginForm, OrderEditForm, OrderForm,
    PasswordChangeStyledForm, RegisterForm, ReviewForm, StatusForm,
)
from .models import (
    CateringOrder, ContactRequest, Dish, DishCategory, EventFormat, KitchenDay,
    MenuTemplate, Review,
)
from .services import (
    KitchenUnavailable, calculate_estimate, cancel_order, dashboard_stats,
    get_kitchen_day, nearest_free_date, order_summary, parse_decor, place_order,
    set_order_status, update_order,
)

SORT_OPTIONS = {
    'name': ('Название А–Я', 'name'),
    '-name': ('Название Я–А', '-name'),
    'price': ('Цена: сначала дешевле', 'price'),
    '-price': ('Цена: сначала дороже', '-price'),
    'output': ('Выход: больше', '-output_grams'),
}

ORDER_SORT_OPTIONS = {
    '-created': ('Сначала новые', '-created_at'),
    'event': ('По дате мероприятия', 'event_date'),
    '-total': ('По сумме', '-total'),
    'status': ('По статусу', 'status'),
}

CATALOG_PER_PAGE = 20


def is_manager(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


manager_required = user_passes_test(is_manager, login_url='main:login')


def _public_formats():
    return EventFormat.objects.filter(is_active=True).prefetch_related('templates')


def index(request):
    formats = _public_formats()
    popular = (
        Dish.objects.filter(is_active=True, is_popular=True)
        .select_related('category')[:6]
    )
    if not popular:
        popular = Dish.objects.filter(is_active=True).select_related('category')[:6]
    templates = MenuTemplate.objects.filter(is_active=True).select_related('event_format')
    return render(request, 'main/index.html', {
        'formats': formats,
        'popular': popular,
        'templates': templates,
        'stats': {
            'dishes': Dish.objects.filter(is_active=True).count(),
            'formats': formats.count(),
            'orders': CateringOrder.objects.exclude(
                status=CateringOrder.STATUS_CANCELLED).count(),
        },
    })


def catalog(request):
    qs = Dish.objects.filter(is_active=True).select_related('category')

    q = (request.GET.get('q') or '').strip()
    category = (request.GET.get('category') or '').strip()
    unit = (request.GET.get('unit') or '').strip()
    price_from = (request.GET.get('price_from') or '').strip()
    price_to = (request.GET.get('price_to') or '').strip()
    sort = request.GET.get('sort') or 'name'

    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
            | Q(composition__icontains=q) | Q(category__name__icontains=q)
        )
    if category:
        qs = qs.filter(category__slug=category)
    if unit:
        qs = qs.filter(unit=unit)
    if price_from.isdigit():
        qs = qs.filter(price__gte=int(price_from))
    if price_to.isdigit():
        qs = qs.filter(price__lte=int(price_to))

    ordering = SORT_OPTIONS.get(sort, SORT_OPTIONS['name'])[1]
    qs = qs.order_by(ordering)

    paginator = Paginator(qs, CATALOG_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'main/catalog.html', {
        'page_obj': page_obj,
        'total': paginator.count,
        'categories': DishCategory.objects.all(),
        'units': Dish.UNIT_CHOICES,
        'sort_options': SORT_OPTIONS,
        'current': {
            'q': q, 'category': category, 'unit': unit,
            'price_from': price_from, 'price_to': price_to, 'sort': sort,
        },
        'active_filters': sum(bool(x) for x in (q, category, unit, price_from or price_to)),
    })


def dish_detail(request, slug):
    dish = get_object_or_404(Dish.objects.select_related('category'), slug=slug, is_active=True)
    similar = (
        Dish.objects.filter(is_active=True, category=dish.category)
        .exclude(pk=dish.pk)[:4]
    )
    return render(request, 'main/dish_detail.html', {
        'dish': dish,
        'similar': similar,
    })


def _calculator_context(data=None):
    formats = EventFormat.objects.filter(is_active=True).prefetch_related('templates__dishes')
    default_format = formats.first()
    default_template = None
    if default_format:
        default_template = default_format.templates.filter(is_active=True).first()
    initial = data or {
        'event_format': default_format,
        'menu_template': default_template,
        'event_date': timezone.localdate() + timedelta(days=30),
        'guests': 30,
        'decor_percent': 10,
    }
    return formats, initial


def calculator(request):
    formats, initial = _calculator_context()
    estimate = None

    if request.method == 'POST':
        form = CalculatorForm(request.POST)
        if form.is_valid():
            event_format = form.cleaned_data['event_format']
            estimate = calculate_estimate(
                event_format, form.cleaned_data['guests'],
                parse_decor(form.cleaned_data.get('decor_percent')),
                form.cleaned_data.get('menu_template'),
            )
            initial = form.cleaned_data
            messages.success(request, 'Смета пересчитана на сервере.')
        else:
            messages.error(request, 'Проверьте параметры расчёта.')
    else:
        form = CalculatorForm(initial=initial)
        event_format = initial.get('event_format')
        if event_format:
            estimate = calculate_estimate(
                event_format, initial['guests'], parse_decor(initial.get('decor_percent')),
                initial.get('menu_template'),
            )

    templates_json = [
        {
            'id': template.pk,
            'name': template.name,
            'format': template.event_format_id,
            'price': float(template.price_per_guest),
            'output': template.output_per_guest(),
        }
        for template in MenuTemplate.objects.filter(is_active=True).select_related('event_format')
    ]

    return render(request, 'main/calculator.html', {
        'form': form,
        'formats': formats,
        'estimate': estimate,
        'templates_json': templates_json,
        'min_date': timezone.localdate() + timedelta(days=3),
    })


@login_required
def checkout(request):
    preset = EventFormat.objects.filter(
        is_active=True, slug=request.GET.get('format', ''),
    ).first()

    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            try:
                order = place_order(
                    user=request.user,
                    event_format=data['event_format'],
                    event_date=data['event_date'],
                    guests=data['guests'],
                    address=data['address'],
                    contact_name=data['contact_name'],
                    contact_phone=data['contact_phone'],
                    contact_email=data['contact_email'],
                    decor_percent=data['decor_percent'],
                    comment=data['comment'],
                    sketch=data.get('sketch'),
                    template=data.get('menu_template'),
                )
            except KitchenUnavailable as exc:
                nearest = (
                    f' Ближайшая свободная дата — {exc.nearest_date:%d.%m.%Y}.'
                    if exc.nearest_date else ''
                )
                form.add_error(
                    None,
                    f'На {exc.requested_date:%d.%m.%Y} суточный лимит кухни исчерпан '
                    f'(свободно {exc.free_guests} мест).{nearest}',
                )
            else:
                messages.success(
                    request,
                    f'Заявка {order.number} принята. Менеджер проверит загрузку кухни.',
                )
                return redirect('main:order_detail', pk=order.pk)
        else:
            messages.error(request, 'Заявка не отправлена. Проверьте выделенные поля.')
    else:
        initial = {}
        if preset:
            initial['event_format'] = preset
            preset_template = preset.templates.filter(is_active=True).first()
            if preset_template:
                initial['menu_template'] = preset_template
        form = OrderForm(initial=initial, user=request.user)

    estimate = None
    selected_format = preset
    selected_template = None
    guests = 30
    if request.method == 'POST':
        selected_format = EventFormat.objects.filter(
            pk=request.POST.get('event_format') or 0).first() or preset
        raw_guests = request.POST.get('guests') or '30'
        guests = int(raw_guests) if raw_guests.isdigit() else 30
        selected_template = MenuTemplate.objects.filter(
            pk=request.POST.get('menu_template') or 0).first()
    if selected_format is None:
        selected_format = EventFormat.objects.filter(is_active=True).first()
    if selected_template is None and selected_format:
        selected_template = selected_format.templates.filter(is_active=True).first()
    if selected_format:
        estimate = calculate_estimate(selected_format, max(10, min(400, guests)),
                                      parse_decor(request.POST.get('decor_percent', 10)),
                                      selected_template)

    templates_json = [
        {
            'id': template.pk,
            'name': template.name,
            'format': template.event_format_id,
            'price': float(template.price_per_guest),
            'output': template.output_per_guest(),
        }
        for template in MenuTemplate.objects.filter(is_active=True)
    ]

    return render(request, 'main/checkout.html', {
        'form': form,
        'estimate': estimate,
        'selected_format': selected_format,
        'templates_json': templates_json,
        'min_date': timezone.localdate() + timedelta(days=3),
    })


def _order_queryset():
    return CateringOrder.objects.select_related('customer', 'event_format').prefetch_related(
        'items__dish__category', 'shifts', 'reviews',
    )


def _get_order(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
    if order.customer_id != request.user.pk and not is_manager(request.user):
        raise PermissionDenied('Это заказ другого пользователя.')
    return order


@login_required
def order_detail(request, pk):
    order = _get_order(request, pk)
    review_form = ReviewForm()
    review = order.reviews.filter(user=request.user).first()
    return render(request, 'main/order_detail.html', {
        'order': order,
        'estimate': order_summary(order),
        'review_form': review_form,
        'review': review,
        'can_edit': order.can_edit,
    })


@login_required
def order_edit(request, pk):
    order = _get_order(request, pk)
    if order.customer_id != request.user.pk:
        raise PermissionDenied('Изменять заказ может только его владелец.')
    if not order.can_edit:
        messages.error(request, 'Изменить заказ нельзя: до мероприятия меньше 48 часов.')
        return redirect('main:order_detail', pk=order.pk)

    if request.method == 'POST':
        form = OrderEditForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            data = form.cleaned_data
            try:
                update_order(
                    order,
                    event_date=data['event_date'],
                    guests=data['guests'],
                    address=data['address'],
                    comment=data['comment'],
                    sketch=data.get('sketch'),
                )
            except KitchenUnavailable as exc:
                nearest = (
                    f' Ближайшая свободная дата — {exc.nearest_date:%d.%m.%Y}.'
                    if exc.nearest_date else ''
                )
                form.add_error(None, f'Недостаточно мест на кухне.{nearest}')
            else:
                messages.success(request, 'Изменения сохранены, смета пересчитана.')
                return redirect('main:order_detail', pk=order.pk)
    else:
        form = OrderEditForm(instance=order)

    return render(request, 'main/order_edit.html', {'order': order, 'form': form})


@login_required
@require_POST
def order_cancel(request, pk):
    order = _get_order(request, pk)
    if order.customer_id != request.user.pk:
        raise PermissionDenied('Отменить заказ может только его владелец.')
    if not order.can_edit:
        messages.error(request, 'Отмена недоступна: до мероприятия меньше 48 часов.')
    elif order.status in (CateringOrder.STATUS_DONE, CateringOrder.STATUS_CANCELLED):
        messages.error(request, 'Этот заказ уже нельзя отменить.')
    else:
        cancel_order(order)
        messages.success(request, f'Заказ {order.number} отменён, места на кухне освобождены.')
    return redirect('main:order_detail', pk=order.pk)


@login_required
def order_print(request, pk):
    order = _get_order(request, pk)
    return render(request, 'main/order_print.html', {'order': order})


@login_required
def account(request):
    orders = (
        CateringOrder.objects.filter(customer=request.user)
        .select_related('event_format')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    profile = getattr(request.user, 'profile', None)
    return render(request, 'main/account.html', {
        'orders': orders,
        'profile': profile,
        'orders_count': orders.count(),
        'active_count': orders.exclude(
            status__in=[CateringOrder.STATUS_DONE, CateringOrder.STATUS_CANCELLED]
        ).count(),
        'reviews_count': Review.objects.filter(user=request.user).count(),
    })


def register(request):
    if request.user.is_authenticated:
        return redirect('main:account')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Аккаунт создан. Добро пожаловать!')
            return redirect('main:account')
        messages.error(request, 'Не удалось создать аккаунт. Проверьте поля.')
    else:
        form = RegisterForm()
    return render(request, 'main/register.html', {'form': form})


class SiteLoginView(LoginView):
    template_name = 'main/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, 'Вы вошли в личный кабинет.')
        return super().form_valid(form)


def contacts(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            messages.success(
                request,
                'Сообщение отправлено. Менеджер ответит в течение рабочего дня.',
            )
            from django.conf import settings
            from django.core.mail import send_mail
            send_mail(
                'Новое обращение с сайта',
                f'{contact.name} <{contact.email}>\n\n{contact.message}',
                settings.DEFAULT_FROM_EMAIL, [settings.MANAGER_EMAIL],
                fail_silently=True,
            )
            return redirect('main:contacts')
        messages.error(request, 'Проверьте поля формы.')
    else:
        form = ContactForm()
    return render(request, 'main/contacts.html', {'form': form})


@login_required
@require_POST
def review_create(request, pk):
    order = _get_order(request, pk)
    if order.customer_id != request.user.pk:
        raise PermissionDenied('Оставить отзыв может только заказчик.')
    if order.status != CateringOrder.STATUS_DONE:
        messages.error(request, 'Отзыв можно оставить после завершения мероприятия.')
        return redirect('main:order_detail', pk=order.pk)
    if order.reviews.filter(user=request.user).exists():
        messages.error(request, 'Вы уже оставили отзыв по этому заказу.')
        return redirect('main:order_detail', pk=order.pk)
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.order = order
        review.user = request.user
        review.save()
        messages.success(request, 'Спасибо за отзыв!')
    else:
        messages.error(request, 'Отзыв не сохранён: проверьте текст и оценку.')
    return redirect('main:order_detail', pk=order.pk)


# ---------------------------------------------------------------- менеджер

@manager_required
def manager_dashboard(request):
    stats = dashboard_stats()
    recent = (
        CateringOrder.objects.select_related('event_format', 'customer')[:8]
    )
    kitchen = KitchenDay.objects.filter(
        date__gte=timezone.localdate(), date__lte=timezone.localdate() + timedelta(days=9),
    )
    active = CateringOrder.objects.exclude(
        status__in=[CateringOrder.STATUS_DONE, CateringOrder.STATUS_CANCELLED]
    ).select_related('event_format')
    return render(request, 'main/manager/dashboard.html', {
        'stats': stats,
        'recent': recent,
        'kitchen': kitchen,
        'active': active,
    })


@manager_required
def manager_orders(request):
    qs = CateringOrder.objects.select_related('event_format', 'customer')
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    event_format = (request.GET.get('format') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    sort = request.GET.get('sort') or '-created'

    if q:
        qs = qs.filter(
            Q(number__icontains=q) | Q(contact_name__icontains=q)
            | Q(contact_phone__icontains=q) | Q(address__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if event_format:
        qs = qs.filter(event_format__slug=event_format)
    if date_from:
        qs = qs.filter(event_date__gte=date_from)
    if date_to:
        qs = qs.filter(event_date__lte=date_to)

    qs = qs.order_by(ORDER_SORT_OPTIONS.get(sort, ORDER_SORT_OPTIONS['-created'])[1])
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'main/manager/orders.html', {
        'page_obj': page_obj,
        'total': paginator.count,
        'statuses': CateringOrder.STATUS_CHOICES,
        'formats': EventFormat.objects.all(),
        'sort_options': ORDER_SORT_OPTIONS,
        'current': {
            'q': q, 'status': status, 'format': event_format,
            'date_from': date_from, 'date_to': date_to, 'sort': sort,
        },
        'query_string': request.GET.urlencode(),
    })


@manager_required
@require_POST
def manager_order_status(request, pk):
    order = get_object_or_404(CateringOrder, pk=pk)
    form = StatusForm(request.POST)
    if form.is_valid():
        set_order_status(order, form.cleaned_data['status'])
        messages.success(request, f'Статус заказа {order.number} обновлён.')
    else:
        messages.error(request, 'Не удалось изменить статус.')
    return redirect(request.POST.get('next') or reverse('main:manager_orders'))


@manager_required
def manager_orders_csv(request):
    qs = CateringOrder.objects.select_related('event_format', 'customer').order_by('-created_at')
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="catering-orders.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Номер', 'Дата мероприятия', 'Заказчик', 'Телефон', 'Формат',
        'Гостей', 'Статус', 'Сумма, ₽', 'Создан',
    ])
    for order in qs:
        writer.writerow([
            order.number,
            order.event_date.strftime('%d.%m.%Y'),
            order.contact_name,
            order.contact_phone,
            order.event_format.name,
            order.guests,
            order.get_status_display(),
            f'{order.total:.2f}'.replace('.', ','),
            order.created_at.strftime('%d.%m.%Y %H:%M'),
        ])
    return response


@manager_required
def dish_create(request):
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES)
        if form.is_valid():
            dish = form.save()
            messages.success(request, f'Блюдо «{dish.name}» добавлено в каталог.')
            return redirect('main:dish_detail', slug=dish.slug)
        messages.error(request, 'Не удалось сохранить блюдо. Проверьте поля.')
    else:
        form = DishForm()
    return render(request, 'main/manager/dish_form.html', {
        'form': form, 'title': 'Новое блюдо', 'mode': 'create',
    })


@manager_required
def dish_update(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES, instance=dish)
        if form.is_valid():
            dish = form.save()
            messages.success(request, f'Блюдо «{dish.name}» обновлено.')
            return redirect('main:dish_detail', slug=dish.slug)
        messages.error(request, 'Не удалось сохранить изменения.')
    else:
        form = DishForm(instance=dish)
    return render(request, 'main/manager/dish_form.html', {
        'form': form, 'dish': dish, 'title': 'Редактирование блюда', 'mode': 'update',
    })


@manager_required
def dish_delete(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == 'POST':
        name = dish.name
        dish.delete()
        messages.success(request, f'Блюдо «{name}» удалено.')
        return redirect('main:catalog')
    return render(request, 'main/manager/dish_confirm_delete.html', {'dish': dish})


# ---------------------------------------------------------------- JSON API

@require_GET
def api_dishes(request):
    qs = Dish.objects.filter(is_active=True).select_related('category')
    q = (request.GET.get('q') or '').strip()
    category = (request.GET.get('category') or '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category__slug=category)
    data = [
        {
            'id': dish.pk,
            'name': dish.name,
            'price': float(dish.price),
            'unit': dish.get_unit_display(),
            'output': dish.output_grams,
            'category': dish.category.name,
            'url': dish.get_absolute_url(),
        }
        for dish in qs.order_by('name')[:8]
    ]
    return JsonResponse({'results': data, 'count': len(data)})


@require_POST
def api_calculator(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Некорректный JSON.']}}, status=400)

    form = CalculatorForm(payload)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors.get_json_data()}, status=400)

    event_format = form.cleaned_data['event_format']
    event_date = form.cleaned_data['event_date']
    guests = form.cleaned_data['guests']
    decor = parse_decor(form.cleaned_data.get('decor_percent'))
    estimate = calculate_estimate(event_format, guests, decor, form.cleaned_data.get('menu_template'))

    kitchen = get_kitchen_day(event_date, event_format)
    available = not kitchen.is_closed and kitchen.free_guests >= guests
    nearest = None if available else nearest_free_date(guests, event_date)

    return JsonResponse({
        'ok': True,
        'guests': guests,
        'format': event_format.name,
        'template': estimate['template'].name if estimate['template'] else '',
        'price_per_guest': float(estimate['price_per_guest']),
        'menu_total': float(estimate['menu_total']),
        'decor_percent': decor,
        'decor_total': float(estimate['decor_total']),
        'staff_total': float(estimate['staff_total']),
        'tableware_total': float(estimate['tableware_total']),
        'total': float(estimate['total']),
        'output_per_guest': estimate['output_per_guest'],
        'norm': estimate['norm'],
        'output_ok': estimate['output_ok'],
        'deficit': estimate['deficit'],
        'waiters': estimate['staff_needed'],
        'tableware_sets': estimate['tableware_needed'],
        'kitchen_available': available,
        'kitchen_free': kitchen.free_guests,
        'kitchen_load': kitchen.load_percent,
        'nearest_date': nearest.strftime('%d.%m.%Y') if nearest else None,
        'date': event_date.strftime('%d.%m.%Y'),
    })


def handler403(request, exception=None):
    return render(request, '403.html', status=403)


def handler404(request, exception=None):
    return render(request, '404.html', status=404)
