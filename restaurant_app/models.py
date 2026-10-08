from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Customer(models.Model):
    id = models.BigAutoField(primary_key=True)
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    ism = models.CharField(max_length=100)
    username = models.CharField(max_length=64, blank=True)
    telefon = models.CharField(max_length=20, blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='customer')
    bloklangan = models.BooleanField(default=False)
    yaratildi = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-yaratildi']

    def __str__(self):
        return self.ism or str(self.telegram_id)


class Category(models.Model):
    nom = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    tartib = models.PositiveSmallIntegerField(default=0)
    faolmi = models.BooleanField(default=True)

    class Meta:
        ordering = ['tartib', 'nom']

    def __str__(self):
        return self.nom


class Dish(models.Model):
    kategoriya = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='taomlar')
    nom = models.CharField(max_length=120)
    tavsif = models.TextField(blank=True)
    narx = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    rasm = models.ImageField(upload_to='taomlar/', null=True, blank=True)
    tayyorlanish_vaqti = models.PositiveSmallIntegerField(default=15)
    faolmi = models.BooleanField(default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['kategoriya', 'nom'], name='unique_dish_per_category'),
            models.CheckConstraint(condition=Q(narx__gt=0), name='dish_narx_positive'),
        ]
        ordering = ['kategoriya__tartib', 'nom']

    def __str__(self):
        return self.nom


class Cart(models.Model):
    mijoz = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='savatlar')
    faolmi = models.BooleanField(default=True)
    yaratilgan = models.DateTimeField(auto_now_add=True)
    yangilangan = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['mijoz'], condition=Q(faolmi=True), name='bitta_faol_savat'),
        ]
        ordering = ['-yangilangan']

    def __str__(self):
        return f'{self.mijoz} savati'


class CartItem(models.Model):
    savat = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='qatorlar')
    taom = models.ForeignKey(Dish, on_delete=models.CASCADE)
    miqdor = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(50)])
    qoshilgan = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['savat', 'taom'], name='unique_cart_item_per_dish'),
        ]
        ordering = ['qoshilgan']

    def __str__(self):
        return f'{self.savat} / {self.taom} x{self.miqdor}'


class Order(models.Model):
    HOLATLAR = [
        ('yangi', 'Yangi'),
        ('tayyorlanmoqda', 'Tayyorlanmoqda'),
        ('tayyor', 'Tayyor'),
        ('berildi', 'Berildi'),
        ('yetkazildi', 'Yetkazildi'),
        ('bekor_qilindi', 'Bekor qilindi'),
    ]
    YETKAZISH_TURLARI = [
        ('stol', 'Stolda'),
        ('manzil', 'Yetkazib berish'),
    ]

    raqam = models.CharField(max_length=16, unique=True, db_index=True)
    mijoz = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='buyurtmalar')
    holat = models.CharField(max_length=20, choices=HOLATLAR, default='yangi', db_index=True)
    yetkazish_turi = models.CharField(max_length=10, choices=YETKAZISH_TURLARI)
    stol_raqami = models.PositiveSmallIntegerField(null=True, blank=True)
    manzil = models.CharField(max_length=255, blank=True)
    telefon = models.CharField(max_length=20)
    izoh = models.TextField(blank=True)
    jami_summa = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    yetkazish_narxi = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    yaratilgan = models.DateTimeField(auto_now_add=True, db_index=True)
    tayyor_vaqti = models.DateTimeField(null=True, blank=True)
    yopilgan_vaqti = models.DateTimeField(null=True, blank=True)
    bekor_sababi = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-yaratilgan']

    def __str__(self):
        return self.raqam


class OrderItem(models.Model):
    buyurtma = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='qatorlar')
    taom = models.ForeignKey(Dish, null=True, blank=True, on_delete=models.SET_NULL, related_name='buyurtma_qatorlari')
    taom_nomi = models.CharField(max_length=120)
    narx = models.DecimalField(max_digits=10, decimal_places=2)
    miqdor = models.PositiveSmallIntegerField()
    summa = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.buyurtma.raqam}: {self.taom_nomi} x{self.miqdor}'


class OrderStatusLog(models.Model):
    buyurtma = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tarix')
    eski_holat = models.CharField(max_length=20)
    yangi_holat = models.CharField(max_length=20)
    kim = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    vaqt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['vaqt']

    def __str__(self):
        return f'{self.buyurtma.raqam}: {self.eski_holat} -> {self.yangi_holat}'
