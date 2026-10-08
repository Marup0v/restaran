from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.db import transaction
from rest_framework import serializers

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


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'telegram_id', 'ism', 'username', 'telefon', 'bloklangan', 'yaratildi']
        read_only_fields = ['id', 'yaratildi']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'nom', 'slug', 'tartib', 'faolmi']


class DishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = ['id', 'kategoriya', 'nom', 'tavsif', 'narx', 'rasm', 'tayyorlanish_vaqti', 'faolmi', 'yaratilgan', 'yangilangan']
        read_only_fields = ['id', 'yaratilgan', 'yangilangan']

    def validate_narx(self, value):
        if value <= 0:
            raise serializers.ValidationError("Narx 0 dan katta bo'lishi kerak.")
        return value


class CartItemSerializer(serializers.ModelSerializer):
    taom = serializers.PrimaryKeyRelatedField(queryset=Dish.objects.filter(faolmi=True))

    class Meta:
        model = CartItem
        fields = ['id', 'taom', 'miqdor', 'qoshilgan']
        read_only_fields = ['id', 'qoshilgan']

    def validate_miqdor(self, value):
        if not 1 <= value <= 50:
            raise serializers.ValidationError("Miqdor 1 dan 50 gacha bo'lishi kerak.")
        return value


class CartSerializer(serializers.ModelSerializer):
    qatorlar = CartItemSerializer(many=True, read_only=True)
    jami_summa = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'mijoz', 'faolmi', 'qatorlar', 'jami_summa', 'yaratilgan', 'yangilangan']
        read_only_fields = ['id', 'mijoz', 'faolmi', 'yaratilgan', 'yangilangan']

    def get_jami_summa(self, obj):
        total = Decimal('0')
        for item in obj.qatorlar.select_related('taom').all():
            total += item.taom.narx * item.miqdor
        return total.quantize(Decimal('0.01'))


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'taom', 'taom_nomi', 'narx', 'miqdor', 'summa']
        read_only_fields = ['id', 'taom', 'taom_nomi', 'narx', 'summa']


class OrderSerializer(serializers.ModelSerializer):
    qatorlar = OrderItemSerializer(many=True, read_only=True)
    tarix = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'raqam', 'mijoz', 'holat', 'yetkazish_turi', 'stol_raqami', 'manzil', 'telefon', 'izoh', 'jami_summa', 'yetkazish_narxi', 'yaratilgan', 'tayyor_vaqti', 'yopilgan_vaqti', 'bekor_sababi', 'qatorlar', 'tarix']
        read_only_fields = ['id', 'raqam', 'mijoz', 'jami_summa', 'yetkazish_narxi', 'yaratilgan', 'tayyor_vaqti', 'yopilgan_vaqti', 'bekor_sababi', 'qatorlar', 'tarix']

    def get_tarix(self, obj):
        return [
            {'eski_holat': log.eski_holat, 'yangi_holat': log.yangi_holat, 'kim': log.kim.username if log.kim else None, 'vaqt': log.vaqt.isoformat()}
            for log in obj.tarix.all()
        ]


class OrderCreateSerializer(serializers.Serializer):
    yetkazish_turi = serializers.ChoiceField(choices=['stol', 'manzil'])
    stol_raqami = serializers.IntegerField(required=False, allow_null=True)
    manzil = serializers.CharField(required=False, allow_blank=True, max_length=255)
    telefon = serializers.CharField(max_length=20, required=False, allow_blank=True)
    izoh = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['yetkazish_turi'] == 'stol':
            if not attrs.get('stol_raqami'):
                raise serializers.ValidationError({'stol_raqami': 'Stol raqami majburiy.'})
            attrs['manzil'] = ''
        else:
            if not attrs.get('manzil') or len(attrs['manzil']) < 10:
                raise serializers.ValidationError({'manzil': 'Manzil 10 belgidan uzun bo\'lishi kerak.'})
            attrs['stol_raqami'] = None
        if not attrs.get('telefon'):
            attrs['telefon'] = self.context['request'].user.customer.telefon or ''
        return attrs


class OrderStatusSerializer(serializers.Serializer):
    holat = serializers.ChoiceField(choices=[choice[0] for choice in Order.HOLATLAR if choice[0] not in ('bekor_qilindi',)])


class OrderCancelSerializer(serializers.Serializer):
    sabab = serializers.CharField(max_length=255)


class DailyReportSerializer(serializers.Serializer):
    sana = serializers.DateField()


class TopDishesSerializer(serializers.Serializer):
    kun = serializers.IntegerField(min_value=1)


class TelegramLoginSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    ism = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=64, required=False, allow_blank=True)


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'is_staff']


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']
