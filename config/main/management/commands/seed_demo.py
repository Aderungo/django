"""Демонстрационные данные варианта 16: 30+ блюд, 30+ заказов, загрузка кухни.

Запуск: python manage.py seed_demo
"""

import random
import shutil
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import (
    CateringOrder, ContactRequest, Dish, DishCategory, EventFormat, KitchenDay,
    MenuTemplate, OrderItem, Profile, Review, StaffShift, TablewareSet,
)
from main.services import STAFF_RATES, calculate_estimate, staff_breakdown

random.seed(16)

DISHES = [
    # slug, name, category, price, unit, output, popular, description, composition
    ('caesar', 'Салат «Цезарь»', 'Салаты', 320, 'portion', 180, True,
     'Классический салат с курицей, пармезаном и домашним соусом.',
     'Романо, куриное филе, пармезан, гренки, соус «Цезарь»'),
    ('tomato-salad', 'Салат с томатами и страчателлой', 'Салаты', 340, 'portion', 170, False,
     'Свежие томаты, страчателла и базиликовое масло.', 'Томаты, страчателла, базилик, оливковое масло'),
    ('greek-salad', 'Салат «Греческий»', 'Салаты', 290, 'portion', 170, False,
     'Овощи, фета и оливки с орегано.', 'Огурец, томат, перец, фета, оливки'),
    ('medallion', 'Медальон из говядины', 'Горячее', 540, 'portion', 220, True,
     'Медальон средней прожарки с соусом демиглас.', 'Говядина, тимьян, соус демиглас'),
    ('chicken-vegetables', 'Куриное филе с овощами', 'Горячее', 480, 'portion', 230, False,
     'Филе курицы на гриле, сезонные овощи.', 'Куриное филе, кабачок, перец, морковь'),
    ('pilaf', 'Плов с бараниной', 'Горячее', 520, 'portion', 250, False,
     'Рассыпчатый рис с бараниной и специями.', 'Рис, баранина, морковь, лук, зира'),
    ('grilled-vegetables', 'Овощи на гриле', 'Горячее', 390, 'portion', 200, False,
     'Кабачки, баклажаны и перец на гриле.', 'Кабачок, баклажан, перец, оливковое масло'),
    ('rustic-potatoes', 'Картофель по-деревенски', 'Горячее', 290, 'portion', 180, False,
     'Запечённый картофель с паприкой и розмарином.', 'Картофель, паприка, розмарин'),
    ('salmon-steak', 'Стейк из лосося', 'Горячее', 720, 'portion', 210, False,
     'Лосось на гриле с лимонным маслом.', 'Лосось, лимон, сливочное масло'),
    ('mashed-potatoes', 'Пюре картофельное', 'Горячее', 240, 'portion', 180, False,
     'Нежное пюре на сливках.', 'Картофель, сливки, сливочное масло'),
    ('bento', 'Бенто-торт', 'Десерты', 890, 'portion', 150, True,
     'Мини-торт с кремом и сезонными ягодами.', 'Бисквит, крем-чиз, ягоды'),
    ('dessert-table', 'Десертный стол', 'Десерты', 520, 'guest', 120, False,
     'Ассорти десертов и мини-пирожных на гостя.', 'Пирожные, тарты, маршмеллоу'),
    ('profiteroles', 'Профитроли', 'Десерты', 410, 'portion', 110, False,
     'Заварные профитроли с кремом.', 'Заварное тесто, крем, шоколад'),
    ('fruit-plate', 'Фруктовая тарелка', 'Десерты', 450, 'portion', 200, False,
     'Сезонные фрукты и ягоды.', 'Яблоко, виноград, апельсин, ягоды'),
    ('furshet-light', 'Фуршет «Лёгкий»', 'Фуршет', 690, 'guest', 420, True,
     'Готовый фуршетный сет на гостя.', 'Канапе, тарталетки, овощи, сыр'),
    ('furshet-premium', 'Фуршет «Премиум»', 'Фуршет', 1150, 'guest', 520, False,
     'Расширенный фуршет с роллами и морепродуктами.', 'Роллы, сыр, канапе, фрукты'),
    ('canapes', 'Канапе ассорти', 'Фуршет', 320, 'portion', 120, False,
     'Канапе с рыбой, сыром и овощами.', 'Хлеб, лосось, сыр, огурец'),
    ('sushi-set', 'Роллы ассорти', 'Фуршет', 640, 'portion', 180, False,
     'Роллы с лососем и огурцом.', 'Рис, нори, лосось, огурец'),
    ('tartlets', 'Тарталетки с лососем', 'Закуски', 280, 'portion', 90, False,
     'Тарталетки с лососем и сливочным сыром.', 'Тарталетка, лосось, крем-чиз'),
    ('vegetables', 'Овощная нарезка', 'Закуски', 240, 'portion', 150, False,
     'Свежие овощи с зеленью.', 'Огурец, томат, перец, зелень'),
    ('cheese-board', 'Сырная тарелка', 'Закуски', 760, 'portion', 180, False,
     'Сыры с медом, орехами и фруктами.', 'Пармезан, камамбер, чеддер, мед, орехи'),
    ('bruschetta', 'Брускетты ассорти', 'Закуски', 310, 'portion', 120, False,
     'Брускетты с томатами и сыром.', 'Хлеб, томаты, базилик, сыр'),
    ('business-coffee', 'Кофе-брейк', 'Напитки', 450, 'guest', 300, True,
     'Кофе, чай и мини-десерты на гостя.', 'Кофе, чай, пирожные, фрукты'),
    ('tea-station', 'Чайная станция', 'Напитки', 390, 'guest', 200, False,
     'Чай разных сортов с добавками.', 'Чай, лимон, мята, мёд'),
    ('lemonade', 'Лимонад «Цитрус»', 'Напитки', 180, 'item', 330, False,
     'Домашний лимонад с цитрусами.', 'Вода, лимон, апельсин, мята'),
    ('mors', 'Морс клюквенный', 'Напитки', 160, 'item', 350, False,
     'Клюквенный морс собственного приготовления.', 'Клюква, вода, сахар'),
    ('photo-zone', 'Оформление фотозоны', 'Оформление', 8000, 'item', 0, True,
     'Фотозона с текстилем, цветами и светом.', 'Текстиль, цветы, свет'),
    ('garlands', 'Гирлянды и свет', 'Оформление', 5400, 'item', 0, False,
     'Гирлянды и декоративный свет для зоны.', 'Гирлянды, лампы'),
    ('tableware-rent', 'Аренда посуды', 'Аренда', 1200, 'item', 0, False,
     'Комплект посуды на 10 персон.', 'Тарелки, бокалы, приборы'),
    ('textile-rent', 'Скатерти и текстиль', 'Аренда', 900, 'item', 0, False,
     'Комплект скатертей и салфеток.', 'Скатерти, салфетки'),
    ('waiter', 'Официант', 'Персонал', 4500, 'item', 0, False,
     'Смена официанта на мероприятии.', 'Работа официанта, 4 часа'),
    ('bartender', 'Бармен на выезде', 'Персонал', 6200, 'item', 0, False,
     'Бармен с оборудованием для коктейлей.', 'Работа бармена, 4 часа'),
]

CATEGORIES = [
    ('Салаты', 'Свежие салаты и закуски'),
    ('Закуски', 'Холодные закуски и нарезки'),
    ('Горячее', 'Горячие блюда'),
    ('Фуршет', 'Фуршетные сеты и канапе'),
    ('Десерты', 'Десерты и сладкие столы'),
    ('Напитки', 'Напитки и кофе-брейки'),
    ('Оформление', 'Декор и фотозоны'),
    ('Аренда', 'Посуда, текстиль и мебель'),
    ('Персонал', 'Официанты, повара и бармены'),
]

FORMATS = [
    ('Фуршет', 'furshet', 690, 350, 4, 250,
     'Лёгкий формат с канапе и закусками: гости общаются стоя, подача порционная.'),
    ('Банкет', 'banket', 1200, 500, 5, 180,
     'Банкет за столами с полной подачей: салаты, горячее, десерт и напитки.'),
    ('Кофе-брейк', 'coffee', 450, 250, 2, 300,
     'Короткая пауза с кофе, чаем и мини-десертами для деловых встреч.'),
]

TEMPLATES = [
    ('Фуршет «Лёгкий»', 'furshet', ['tartlets', 'canapes', 'vegetables', 'cheese-board', 'bruschetta'],
     690, 'Проверенный фуршетный сет: пять закусок и 660 г выхода на гостя.'),
    ('Фуршет «Мини»', 'furshet', ['canapes', 'tartlets'],
     390, 'Короткий фуршет для встречи до двух часов: 210 г выхода на гостя.'),
    ('Банкет «Классический»', 'banket', ['caesar', 'medallion', 'rustic-potatoes',
                                         'grilled-vegetables', 'profiteroles', 'mors'],
     1200, 'Полный банкет: салат, горячее, гарнир, десерт и морс.'),
    ('Кофе-брейк «Деловой»', 'coffee', ['business-coffee', 'profiteroles', 'fruit-plate', 'tea-station'],
     450, 'Кофе, чай, мини-десерты и фрукты для рабочей встречи.'),
]

REVIEW_TEXTS = [
    'Всё организовали точно в срок, гости остались довольны.',
    'Отдельное спасибо официантам — быстро и незаметно.',
    'Меню рассчитали точно, еды хватило всем.',
    'Красивая фотозона, вкусные десерты.',
    'Кухня справилась с большим банкетом, подача по графику.',
]

ADDRESSES = [
    'г. Ульяновск, ул. Гончарова, 1',
    'г. Ульяновск, ул. Ленина, 45',
    'г. Ульяновск, пр-т Нариманова, 12',
    'г. Ульяновск, ул. Рябикова, 8',
    'г. Ульяновск, ул. Минаева, 3',
]


class Command(BaseCommand):
    help = 'Заполняет базу демонстрационными данными варианта 16'

    def handle(self, *args, **options):
        self.create_users()
        formats = self.create_formats()
        categories = self.create_categories()
        dishes = self.create_dishes(categories)
        self.create_templates(formats, dishes)
        self.create_tableware()
        self.create_kitchen()
        self.create_orders(dishes, formats)
        self.create_contacts()

        self.stdout.write(self.style.SUCCESS(
            'Готово: {} блюд, {} заказов, {} дат кухни.'.format(
                Dish.objects.count(), CateringOrder.objects.count(), KitchenDay.objects.count(),
            )
        ))
        self.stdout.write('Админ: admin@banket.example / admin12345')
        self.stdout.write('Менеджер: manager@banket.example / manager12345')
        self.stdout.write('Заказчик: ivan@example.com / ivan12345')

    # ------------------------------------------------------------------
    def create_users(self):
        group, _ = Group.objects.get_or_create(name='Менеджеры')
        users = [
            ('admin@banket.example', 'admin@banket.example', 'admin12345', True, True,
             'Администратор'),
            ('manager@banket.example', 'manager@banket.example', 'manager12345', True, False,
             'Леонид Менеджеров'),
            ('ivan@example.com', 'ivan@example.com', 'ivan12345', False, False, 'Иван Иванов'),
            ('anna@example.com', 'anna@example.com', 'anna12345', False, False, 'Анна Петрова'),
            ('petr@example.com', 'petr@example.com', 'petr12345', False, False, 'Пётр Смирнов'),
        ]
        for username, email, password, is_staff, is_super, full_name in users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': full_name.split()[0],
                    'last_name': ' '.join(full_name.split()[1:]),
                    'is_staff': is_staff,
                    'is_superuser': is_super,
                },
            )
            if created:
                user.set_password(password)
                user.save()
            else:
                user.is_staff = is_staff
                user.is_superuser = is_super
                user.email = email
                user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.full_name = full_name
            profile.phone = '+7 (900) 100-20-{}'.format(10 + user.pk)
            profile.save()
            if is_staff:
                user.groups.add(group)

    def create_formats(self):
        result = {}
        for order, (name, slug, price, norm, duration, limit, description) in enumerate(FORMATS):
            event_format, _ = EventFormat.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name, 'price_per_guest': Decimal(price),
                    'min_output_per_guest': norm, 'duration_hours': duration,
                    'kitchen_daily_limit': limit, 'description': description,
                    'sort_order': order, 'is_active': True,
                },
            )
            result[slug] = event_format
        return result

    def create_categories(self):
        result = {}
        for order, (name, description) in enumerate(CATEGORIES):
            category, _ = DishCategory.objects.update_or_create(
                name=name, defaults={'description': description, 'sort_order': order},
            )
            result[name] = category
        return result

    def create_dishes(self, categories):
        media_dir = settings.MEDIA_ROOT / 'dishes'
        media_dir.mkdir(parents=True, exist_ok=True)
        source_dir = settings.BASE_DIR / 'static' / 'img' / 'dishes'
        result = {}
        for slug, name, category, price, unit, output, popular, description, composition in DISHES:
            image_name = ''
            source = source_dir / f'{slug}.jpg'
            if source.exists():
                shutil.copyfile(source, media_dir / f'{slug}.jpg')
                image_name = f'dishes/{slug}.jpg'
            dish, _ = Dish.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name, 'category': categories[category],
                    'price': Decimal(price), 'unit': unit, 'output_grams': output,
                    'is_popular': popular, 'is_active': True,
                    'description': description, 'composition': composition,
                    'image': image_name,
                },
            )
            result[slug] = dish
        return result

    def create_templates(self, formats, dishes):
        for name, format_slug, dish_slugs, price, description in TEMPLATES:
            template, _ = MenuTemplate.objects.update_or_create(
                name=name,
                defaults={
                    'event_format': formats[format_slug],
                    'price_per_guest': Decimal(price),
                    'description': description,
                    'is_active': True,
                },
            )
            template.dishes.set([dishes[slug] for slug in dish_slugs])

    def create_tableware(self):
        rows = [
            ('Комплект посуды «Стандарт»', 'tableware', 1200, 12,
             'Тарелки, бокалы и приборы на 12 персон'),
            ('Комплект текстиля', 'textile', 900, 12, 'Скатерти и салфетки на 12 персон'),
            ('Комплект мебели', 'furniture', 2500, 10, 'Столы и стулья на 10 персон'),
        ]
        for name, kind, price, persons, description in rows:
            TablewareSet.objects.update_or_create(
                name=name,
                defaults={'kind': kind, 'price': Decimal(price),
                          'persons_per_set': persons, 'description': description},
            )

    def create_kitchen(self):
        CateringOrder.objects.all().delete()
        KitchenDay.objects.all().delete()
        today = timezone.localdate()
        for offset in range(-90, 91):
            day = today + timedelta(days=offset)
            capacity = 250 if day.weekday() != 6 else 300
            KitchenDay.objects.create(
                date=day,
                capacity_guests=capacity,
                booked_guests=0,
                is_closed=(day.weekday() == 6 and offset % 4 == 0),
                note='',
            )
        # дата почти под завязку: демонстрация отказа и подбора соседней даты
        near_full = today + timedelta(days=10)
        KitchenDay.objects.filter(date=near_full).update(
            booked_guests=245, note='Почти полная загрузка — тестовая дата',
        )

    def create_orders(self, dishes, formats):
        users = list(User.objects.filter(is_staff=False))
        templates = list(MenuTemplate.objects.filter(is_active=True))
        statuses_past = [CateringOrder.STATUS_DONE, CateringOrder.STATUS_DONE,
                         CateringOrder.STATUS_CANCELLED]
        statuses_future = [CateringOrder.STATUS_NEW, CateringOrder.STATUS_CONFIRMED,
                           CateringOrder.STATUS_CONFIRMED, CateringOrder.STATUS_COOKING]
        today = timezone.localdate()

        for index in range(36):
            user = users[index % len(users)]
            template = templates[index % len(templates)]
            offset = -80 + index * 4
            if index < 6:
                offset = 6 + index * 5
            event_date = today + timedelta(days=offset)
            guests = random.choice([20, 30, 35, 40, 50, 60, 75, 90, 110, 120, 150])
            status = random.choice(statuses_past if offset < 0 else statuses_future)
            if index == 0:
                event_date = today + timedelta(days=21)
                guests = 40
                status = CateringOrder.STATUS_CONFIRMED
                user = User.objects.get(username='ivan@example.com')
            if index == 1:
                event_date = today + timedelta(days=-30)
                guests = 35
                status = CateringOrder.STATUS_DONE
                user = User.objects.get(username='ivan@example.com')
            if index == 2:
                event_date = today + timedelta(days=12)
                guests = 60
                status = CateringOrder.STATUS_NEW
                user = User.objects.get(username='ivan@example.com')

            decor = random.choice([0, 10, 10, 25])
            estimate = calculate_estimate(template.event_format, guests, decor, template)
            order = CateringOrder.objects.create(
                customer=user,
                event_format=template.event_format,
                menu_template=template,
                event_date=event_date,
                guests=guests,
                address=random.choice(ADDRESSES),
                contact_name=user.get_full_name() or user.username,
                contact_phone=user.profile.phone,
                contact_email=user.email,
                decor_percent=decor,
                comment=random.choice(['', 'Нужна вегетарианская линия.', 'Ранний монтаж фотозоны.']),
                status=status,
                menu_total=estimate['menu_total'],
                decor_total=estimate['decor_total'],
                staff_total=estimate['staff_total'],
                tableware_total=estimate['tableware_total'],
                total=estimate['total'],
                output_per_guest=estimate['output_per_guest'],
            )
            OrderItem.objects.bulk_create([
                OrderItem(order=order, dish=dish, qty=guests, unit_price=dish.price)
                for dish in estimate['dishes']
            ])
            StaffShift.objects.bulk_create([
                StaffShift(order=order, role=role, people=people,
                           hours=template.event_format.duration_hours, rate=STAFF_RATES[role])
                for role, people in staff_breakdown(guests).items() if people
            ])

            created_at = timezone.now() - timedelta(days=random.randint(1, 100),
                                                    hours=random.randint(0, 20))
            CateringOrder.objects.filter(pk=order.pk).update(created_at=created_at)

            if status != CateringOrder.STATUS_CANCELLED:
                kitchen = KitchenDay.objects.filter(date=event_date).first()
                if kitchen:
                    KitchenDay.objects.filter(pk=kitchen.pk).update(
                        booked_guests=kitchen.booked_guests + guests,
                    )

            if status == CateringOrder.STATUS_DONE and random.random() < 0.7:
                Review.objects.create(
                    order=order, user=user, rating=random.choice([5, 5, 4, 4, 3]),
                    text=random.choice(REVIEW_TEXTS),
                )

    def create_contacts(self):
        ContactRequest.objects.all().delete()
        rows = [
            ('Мария', 'maria@example.com', 'Свадьба на 80 человек в августе, нужна фотозона.'),
            ('ООО «Волга»', 'office@volga.example', 'Интересует кофе-брейк на конференцию, 120 участников.'),
            ('Сергей', 'sergey@example.com', 'Подскажите, есть ли вегетарианское меню?'),
            ('Елена', 'elena@example.com', 'Нужен банкет на 40 человек с обслуживанием.'),
            ('Артём', 'artem@example.com', 'Хотим фуршет на открытии офиса, дата через месяц.'),
        ]
        for name, email, message in rows:
            ContactRequest.objects.create(
                name=name, email=email, phone='+7 (900) 111-22-33',
                message=message, consent=True,
            )
