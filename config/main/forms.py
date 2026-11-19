"""Формы: регистрация, вход, заказ, блюдо, отзыв, обращение, калькулятор."""

import re
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    CateringOrder, ContactRequest, Dish, DishCategory, EventFormat, MenuTemplate, Review,
)
from .services import MAX_GUESTS, MIN_DAYS_AHEAD, MIN_GUESTS

PHONE_RE = re.compile(r'^\+?[0-9\s\-()]{10,20}$')


class StyledFormMixin:
    """Единые CSS-классы для полей, чтобы не писать стили в шаблонах."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'checkbox-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'select')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'textarea')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'file-input')
            else:
                widget.attrs.setdefault('class', 'input')


class RegisterForm(StyledFormMixin, UserCreationForm):
    full_name = forms.CharField(
        label='Имя и фамилия', max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'Иван Иванов', 'autocomplete': 'name'}),
    )
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
    )
    phone = forms.CharField(
        label='Телефон', max_length=24,
        widget=forms.TextInput(attrs={'placeholder': '+7 (900) 000-00-00', 'autocomplete': 'tel'}),
    )
    consent = forms.BooleanField(
        label='Согласен на обработку персональных данных',
        error_messages={'required': 'Подтвердите согласие на обработку данных.'},
    )

    class Meta:
        model = User
        fields = ('full_name', 'phone', 'email')

    def clean_full_name(self):
        value = self.cleaned_data['full_name'].strip()
        if len(value.split()) < 2:
            raise ValidationError('Укажите имя и фамилию — минимум два слова.')
        if len(value) < 3:
            raise ValidationError('Слишком короткое имя.')
        return value

    def clean_phone(self):
        value = self.cleaned_data['phone'].strip()
        if not PHONE_RE.match(value):
            raise ValidationError('Введите телефон в формате +7 (900) 000-00-00.')
        return value

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Пользователь с таким e-mail уже зарегистрирован.')
        if User.objects.filter(username__iexact=email).exists():
            raise ValidationError('Пользователь с таким e-mail уже зарегистрирован.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        parts = self.cleaned_data['full_name'].split()
        user.first_name = parts[0][:150]
        user.last_name = ' '.join(parts[1:])[:150]
        if commit:
            user.save()
            user.profile.phone = self.cleaned_data['phone']
            user.profile.full_name = self.cleaned_data['full_name']
            user.profile.save()
        return user


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'placeholder': 'Не короче 8 символов',
                                          'autocomplete': 'current-password'}),
    )

    error_messages = {
        'invalid_login': 'Неверный e-mail или пароль.',
        'inactive': 'Аккаунт отключён.',
    }


class OrderForm(StyledFormMixin, forms.ModelForm):
    consent = forms.BooleanField(
        label='Согласен на обработку персональных данных и принимаю условия заказа',
        error_messages={'required': 'Подтвердите согласие на обработку данных.'},
    )

    class Meta:
        model = CateringOrder
        fields = (
            'event_format', 'menu_template', 'event_date', 'guests', 'address', 'contact_name',
            'contact_phone', 'contact_email', 'decor_percent', 'comment', 'sketch',
        )
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'guests': forms.NumberInput(attrs={'min': MIN_GUESTS, 'max': MAX_GUESTS,
                                               'inputmode': 'numeric'}),
            'address': forms.TextInput(attrs={'placeholder': 'г. Ульяновск, ул. Гончарова, 1'}),
            'contact_name': forms.TextInput(attrs={'placeholder': 'Иванов Иван',
                                                   'autocomplete': 'name'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': '+7 (900) 000-00-00',
                                                    'inputmode': 'tel'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'comment': forms.Textarea(attrs={'rows': 3,
                                             'placeholder': 'Пожелания по меню и подаче'}),
            'sketch': forms.ClearableFileInput(attrs={'accept': '.png,.jpg,.jpeg,.webp,.pdf'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['event_format'].queryset = EventFormat.objects.filter(is_active=True)
        self.fields['event_format'].empty_label = 'Выберите формат'
        self.fields['menu_template'].queryset = MenuTemplate.objects.filter(is_active=True)
        self.fields['menu_template'].label = 'Готовый сет'
        self.fields['menu_template'].empty_label = 'Сет по умолчанию'
        min_date = timezone.localdate() + timedelta(days=MIN_DAYS_AHEAD)
        self.fields['event_date'].widget.attrs['min'] = min_date.isoformat()
        self.fields['sketch'].required = False
        if self.user is not None and not self.is_bound:
            profile = getattr(self.user, 'profile', None)
            self.fields['contact_name'].initial = (
                (profile.full_name if profile else '') or self.user.get_full_name()
            )
            self.fields['contact_phone'].initial = profile.phone if profile else ''
            self.fields['contact_email'].initial = self.user.email

    def clean_event_date(self):
        value = self.cleaned_data['event_date']
        min_date = timezone.localdate() + timedelta(days=MIN_DAYS_AHEAD)
        if value < min_date:
            raise ValidationError(
                f'Выберите дату не раньше {min_date:%d.%m.%Y} — '
                f'кухне нужно {MIN_DAYS_AHEAD} дня на подготовку.'
            )
        return value

    def clean_guests(self):
        value = self.cleaned_data['guests']
        if value < MIN_GUESTS or value > MAX_GUESTS:
            raise ValidationError(f'Введите число гостей от {MIN_GUESTS} до {MAX_GUESTS}.')
        return value

    def clean_contact_phone(self):
        value = self.cleaned_data['contact_phone'].strip()
        if not PHONE_RE.match(value):
            raise ValidationError('Введите телефон в формате +7 (900) 000-00-00.')
        return value

    def clean(self):
        data = super().clean()
        event_format = data.get('event_format')
        template = data.get('menu_template')
        if template and event_format and template.event_format_id != event_format.pk:
            self.add_error('menu_template',
                           'Выбранный сет не относится к этому формату мероприятия.')
        return data


class OrderEditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CateringOrder
        fields = ('event_date', 'guests', 'address', 'comment', 'sketch')
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'guests': forms.NumberInput(attrs={'min': MIN_GUESTS, 'max': MAX_GUESTS}),
            'address': forms.TextInput(),
            'comment': forms.Textarea(attrs={'rows': 3}),
            'sketch': forms.ClearableFileInput(attrs={'accept': '.png,.jpg,.jpeg,.webp,.pdf'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        min_date = timezone.localdate() + timedelta(days=MIN_DAYS_AHEAD)
        self.fields['event_date'].widget.attrs['min'] = min_date.isoformat()
        self.fields['sketch'].required = False

    def clean_event_date(self):
        value = self.cleaned_data['event_date']
        min_date = timezone.localdate() + timedelta(days=MIN_DAYS_AHEAD)
        if value < min_date:
            raise ValidationError(f'Дата должна быть не раньше {min_date:%d.%m.%Y}.')
        return value

    def clean_guests(self):
        value = self.cleaned_data['guests']
        if value < MIN_GUESTS or value > MAX_GUESTS:
            raise ValidationError(f'Введите число гостей от {MIN_GUESTS} до {MAX_GUESTS}.')
        return value


class DishForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Dish
        fields = ('category', 'name', 'description', 'composition', 'price',
                  'unit', 'output_grams', 'image', 'is_active', 'is_popular')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'accept': '.png,.jpg,.jpeg,.webp'}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'output_grams': forms.NumberInput(attrs={'min': 0, 'max': 5000}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = DishCategory.objects.all()
        self.fields['image'].required = False
        self.fields['image'].help_text = 'PNG, JPG или WEBP, не больше 5 МБ.'


class ContactForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ContactRequest
        fields = ('name', 'email', 'phone', 'message', 'consent')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Как к вам обращаться'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+7 (900) 000-00-00'}),
            'message': forms.Textarea(attrs={'rows': 4, 'data-minlength': 15,
                                             'placeholder': 'Дата, число гостей, формат мероприятия'}),
        }

    def clean_message(self):
        value = self.cleaned_data['message'].strip()
        if len(value) < 15:
            raise ValidationError('Напишите сообщение — хотя бы 15 символов.')
        return value

    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        if value and not PHONE_RE.match(value):
            raise ValidationError('Введите телефон в формате +7 (900) 000-00-00.')
        return value


class ReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'text')
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} из 5') for i in range(5, 0, -1)]),
            'text': forms.Textarea(attrs={'rows': 4, 'data-minlength': 10,
                                          'placeholder': 'Расскажите, как прошло мероприятие'}),
        }

    def clean_text(self):
        value = self.cleaned_data['text'].strip()
        if len(value) < 10:
            raise ValidationError('Отзыв должен содержать хотя бы 10 символов.')
        if len(value) > 1000:
            raise ValidationError('Сократите отзыв до 1000 символов.')
        return value


class CalculatorForm(StyledFormMixin, forms.Form):
    event_format = forms.ModelChoiceField(
        label='Формат', queryset=EventFormat.objects.none(), empty_label=None,
    )
    menu_template = forms.ModelChoiceField(
        label='Готовый сет', queryset=MenuTemplate.objects.none(), required=False,
        empty_label='Сет по умолчанию',
    )
    event_date = forms.DateField(
        label='Дата мероприятия',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    guests = forms.IntegerField(
        label='Количество гостей', min_value=MIN_GUESTS, max_value=MAX_GUESTS,
        widget=forms.NumberInput(attrs={'min': MIN_GUESTS, 'max': MAX_GUESTS,
                                        'inputmode': 'numeric'}),
    )
    decor_percent = forms.TypedChoiceField(
        label='Сложность оформления', coerce=int, required=False, initial=10,
        choices=CateringOrder.DECOR_CHOICES,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event_format'].queryset = EventFormat.objects.filter(is_active=True)
        self.fields['menu_template'].queryset = MenuTemplate.objects.filter(is_active=True)
        min_date = timezone.localdate() + timedelta(days=MIN_DAYS_AHEAD)
        self.fields['event_date'].widget.attrs['min'] = min_date.isoformat()

    def clean_event_date(self):
        value = self.cleaned_data['event_date']
        min_date = timezone.localdate() + timedelta(days=MIN_DAYS_AHEAD)
        if value < min_date:
            raise ValidationError(f'Выберите дату не раньше {min_date:%d.%m.%Y}.')
        return value

    def clean(self):
        data = super().clean()
        event_format = data.get('event_format')
        template = data.get('menu_template')
        if template and event_format and template.event_format_id != event_format.pk:
            self.add_error('menu_template',
                           'Выбранный сет не относится к этому формату мероприятия.')
        return data


class StatusForm(forms.Form):
    status = forms.ChoiceField(label='Статус', choices=CateringOrder.STATUS_CHOICES)


class PasswordChangeStyledForm(StyledFormMixin, PasswordChangeForm):
    pass
