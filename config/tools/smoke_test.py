"""Быстрый обход всех страниц и форм через тестовый клиент Django."""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from main.models import CateringOrder, Dish, EventFormat, MenuTemplate  # noqa: E402

ok = True


def check(label, response, expected=(200,)):
    global ok
    good = response.status_code in expected
    ok = ok and good
    print(f'{"OK " if good else "FAIL"} {label:42} {response.status_code}')
    if not good:
        body = response.content.decode('utf-8', 'replace')
        print(body[:1200])


public = Client()
for name in ['index', 'catalog', 'calculator', 'contacts', 'login', 'register']:
    check(name, public.get(reverse(f'main:{name}')))
check('catalog filter', public.get(reverse('main:catalog'),
                                   {'q': 'салат', 'category': 'salaty', 'sort': 'price'}))
check('catalog page 2', public.get(reverse('main:catalog'), {'page': 2}))
dish = Dish.objects.filter(is_active=True).first()
check('dish detail', public.get(dish.get_absolute_url()))
check('404', public.get('/no-such-page/'), (404,))
check('checkout redirect', public.get(reverse('main:checkout')), (302,))

check('api dishes', public.get(reverse('main:api_dishes'), {'q': 'сал'}))
fmt = EventFormat.objects.first()
check('api calculator', public.post(
    reverse('main:api_calculator'),
    data='{"event_format": %d, "event_date": "%s", "guests": 30, "decor_percent": 10}' % (
        fmt.pk, (timezone.localdate() + timedelta(days=30)).isoformat()),
    content_type='application/json',
))

customer = Client()
assert customer.login(username='ivan@example.com', password='ivan12345'), 'login ivan failed'
check('account', customer.get(reverse('main:account')))
order = CateringOrder.objects.filter(customer__username='ivan@example.com').first()
check('order detail', customer.get(reverse('main:order_detail', args=[order.pk])))
check('order print', customer.get(reverse('main:order_print', args=[order.pk])))
check('order edit', customer.get(reverse('main:order_edit', args=[order.pk])), (200, 302))
check('password change', customer.get(reverse('main:password_change')))
check('checkout', customer.get(reverse('main:checkout')))
check('checkout preset', customer.get(reverse('main:checkout') + '?format=furshet'))

foreign = CateringOrder.objects.exclude(customer__username='ivan@example.com').first()
check('foreign order 403', customer.get(reverse('main:order_detail', args=[foreign.pk])), (403,))
check('manager page 302', customer.get(reverse('main:manager_dashboard')), (302,))

manager = Client()
assert manager.login(username='manager@banket.example', password='manager12345'), 'login manager failed'
check('manager dashboard', manager.get(reverse('main:manager_dashboard')))
check('manager orders', manager.get(reverse('main:manager_orders')))
check('manager orders filter', manager.get(reverse('main:manager_orders'),
                                           {'status': 'confirmed', 'sort': '-total'}))
check('manager orders page 2', manager.get(reverse('main:manager_orders'), {'page': 2}))
check('csv export', manager.get(reverse('main:manager_orders_csv')))
check('dish create form', manager.get(reverse('main:dish_create')))
check('dish edit form', manager.get(reverse('main:dish_update', args=[dish.pk])))
check('dish delete form', manager.get(reverse('main:dish_delete', args=[dish.pk])))
check('manager can open any order', manager.get(reverse('main:order_detail', args=[foreign.pk])))

# POST: контактная форма
check('contact post', public.post(reverse('main:contacts'), {
    'name': 'Тест', 'email': 'test@example.com', 'phone': '+7 (900) 000-00-00',
    'message': 'Проверка формы обратной связи на пятнадцать символов.',
    'consent': 'on',
}, follow=True))

# POST: калькулятор
check('calculator post', public.post(reverse('main:calculator'), {
    'event_format': fmt.pk, 'menu_template': '',
    'event_date': (timezone.localdate() + timedelta(days=30)).isoformat(),
    'guests': 45, 'decor_percent': 10,
}, follow=True))

print('\nRESULT:', 'ALL OK' if ok else 'FAILURES')
sys.exit(0 if ok else 1)

