from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    Category,
    Customer,
    Dish,
    Order,
    OrderItem,
    OrderStatusLog,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'ism', 'username', 'telefon', 'bloklangan', 'yaratildi')
    search_fields = ('ism', 'username', 'telefon', 'telegram_id')
    list_filter = ('bloklangan', 'yaratildi')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('nom', 'slug', 'tartib', 'faolmi')
    search_fields = ('nom', 'slug')
    list_filter = ('faolmi',)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('nom', 'kategoriya', 'narx', 'tayyorlanish_vaqti', 'faolmi')
    search_fields = ('nom', 'tavsif')
    list_filter = ('kategoriya', 'faolmi')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('mijoz', 'faolmi', 'yaratilgan', 'yangilangan')
    list_filter = ('faolmi',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('savat', 'taom', 'miqdor', 'qoshilgan')
    search_fields = ('taom__nom',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('raqam', 'mijoz', 'holat', 'yetkazish_turi', 'jami_summa', 'yaratilgan')
    search_fields = ('raqam', 'mijoz__ism', 'telefon', 'manzil')
    list_filter = ('holat', 'yetkazish_turi', 'yaratilgan')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('buyurtma', 'taom_nomi', 'narx', 'miqdor', 'summa')
    search_fields = ('taom_nomi',)


@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ('buyurtma', 'eski_holat', 'yangi_holat', 'kim', 'vaqt')
    search_fields = ('buyurtma__raqam',)
    list_filter = ('yangi_holat', 'vaqt')
    readonly_fields = ('buyurtma', 'eski_holat', 'yangi_holat', 'kim', 'vaqt')
