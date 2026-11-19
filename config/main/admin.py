from django.contrib import admin

from .models import (
    CateringOrder, ContactRequest, Dish, DishCategory, EventFormat, KitchenDay,
    MenuTemplate, OrderItem, Profile, Review, StaffShift, TablewareSet,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class StaffShiftInline(admin.TabularInline):
    model = StaffShift
    extra = 0


@admin.register(CateringOrder)
class CateringOrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'event_date', 'contact_name', 'event_format',
                    'guests', 'status', 'total')
    list_filter = ('status', 'event_format', 'event_date')
    search_fields = ('number', 'contact_name', 'contact_phone', 'address')
    inlines = [OrderItemInline, StaffShiftInline]
    readonly_fields = ('number', 'menu_total', 'decor_total', 'staff_total',
                       'tableware_total', 'total', 'output_per_guest')


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'unit', 'output_grams', 'is_active')
    list_filter = ('category', 'unit', 'is_active', 'is_popular')
    search_fields = ('name', 'description', 'composition')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(MenuTemplate)
class MenuTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_format', 'price_per_guest', 'is_active')
    list_filter = ('event_format', 'is_active')
    filter_horizontal = ('dishes',)


@admin.register(KitchenDay)
class KitchenDayAdmin(admin.ModelAdmin):
    list_display = ('date', 'capacity_guests', 'booked_guests', 'is_closed', 'note')
    list_filter = ('is_closed',)
    ordering = ('date',)


for model in (EventFormat, DishCategory, TablewareSet, Review, ContactRequest, Profile):
    admin.site.register(model)
