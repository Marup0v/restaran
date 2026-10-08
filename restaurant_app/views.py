from decimal import Decimal
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.http import Http404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Cart, CartItem, Category, Customer, Dish, Order, OrderItem, OrderStatusLog
from .permissions import IsAdminUser, IsChefUser
from .serializers import (
    CartSerializer,
    CategorySerializer,
    CustomerSerializer,
    DailyReportSerializer,
    DishSerializer,
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    OrderStatusSerializer,
    TelegramLoginSerializer,
    TopDishesSerializer,
)


User = get_user_model()


class LargeResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class JWTLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'detail': 'Username va password majburiy.'}, status=400)
        user = User.objects.filter(username=username).first()
        if user is None or not user.check_password(password):
            return Response({'detail': 'Login yoki parol noto‘g‘ri.'}, status=401)
        refresh = RefreshToken.for_user(user)
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh)})


class CustomerAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TelegramLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        customer, _ = Customer.objects.get_or_create(telegram_id=data['telegram_id'])
        customer.ism = data.get('ism', customer.ism)
        customer.username = data.get('username', '')
        customer.save()
        user = customer.user
        if user is None:
            user = User.objects.create_user(username=f'user_{customer.telegram_id}', password=str(customer.telegram_id))
            customer.user = user
            customer.save(update_fields=['user'])
        refresh = RefreshToken.for_user(user)
        return Response({'token': str(refresh.access_token), 'refresh': str(refresh)})


class KitchenTelegramAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        customer = Customer.objects.select_related('user').filter(telegram_id=telegram_id).first()
        user = customer.user if customer else None
        if not user or not (user.is_staff or user.groups.filter(name='Oshpaz').exists()):
            return Response({'detail': 'Siz oshpaz sifatida ro‘yxatdan o‘tmagansiz.'}, status=403)
        refresh = RefreshToken.for_user(user)
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh)})


class CategoriesAPIView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsPagination

    def get_queryset(self):
        qs = Category.objects.all()
        if not self.request.user.is_staff and not self.request.user.groups.filter(name='Oshpaz').exists():
            qs = qs.filter(faolmi=True)
        return qs.order_by('tartib', 'nom')

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Faqat administrator kategoriya qo‘sha oladi.'}, status=403)
        return super().post(request, *args, **kwargs)

    def patch(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Faqat administrator kategoriya tahrirlay oladi.'}, status=403)
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Faqat administrator kategoriya o‘chira oladi.'}, status=403)
        category = self.get_object()
        if category.taomlar.exists():
            return Response({'detail': 'Taomlari bor kategoriyani o‘chirib bo‘lmaydi.'}, status=409)
        category.delete()
        return Response(status=204)


class DishAPIView(generics.ListCreateAPIView):
    serializer_class = DishSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LargeResultsPagination

    def get_queryset(self):
        queryset = Dish.objects.select_related('kategoriya')
        if self.request.query_params.get('kategoriya'):
            queryset = queryset.filter(kategoriya_id=self.request.query_params['kategoriya'])
        if self.request.query_params.get('faolmi') is not None:
            queryset = queryset.filter(faolmi=self.request.query_params['faolmi'].lower() == 'true')
        q = self.request.query_params.get('qidiruv')
        if q:
            queryset = queryset.filter(nom__icontains=q)
        return queryset.order_by('kategoriya__tartib', 'nom')

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({'detail': 'Administrator ruxsati kerak.'}, status=403)
        return super().post(request, *args, **kwargs)

    def patch(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Faqat administrator taomni tahrirlay oladi.'}, status=403)
        dish = self.get_object()
        serializer = self.get_serializer(dish, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Faqat administrator taomni o‘chira oladi.'}, status=403)
        dish = self.get_object()
        dish.faolmi = False
        dish.save(update_fields=['faolmi'])
        return Response({'detail': 'Taom vaqtincha o‘chirildi.'})


class MenuAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        if pk:
            item = Dish.objects.select_related('kategoriya').filter(faolmi=True, kategoriya__faolmi=True, id=pk).first()
            if not item:
                raise Http404('Taom topilmadi.')
            return Response({
                'id': item.id,
                'nom': item.nom,
                'name': item.nom,
                'tavsif': item.tavsif,
                'description': item.tavsif,
                'narx': str(item.narx),
                'price': float(item.narx),
                'tayyorlanish_vaqti': item.tayyorlanish_vaqti,
                'kategoriya': item.kategoriya.nom,
                'category': item.kategoriya.nom,
                'slug': item.kategoriya.slug,
                'rasm': item.rasm.url if item.rasm else '',
                'image': item.rasm.url if item.rasm else '',
            })
        rows = Dish.objects.select_related('kategoriya').filter(faolmi=True, kategoriya__faolmi=True).order_by('kategoriya__tartib', 'nom')
        grouped = {}
        all_items = []
        for item in rows:
            grouped.setdefault(item.kategoriya.slug, {
                'nom': item.kategoriya.nom,
                'slug': item.kategoriya.slug,
                'taomlar': []
            })
            dish_dict = {
                'id': item.id,
                'nom': item.nom,
                'name': item.nom,
                'tavsif': item.tavsif,
                'description': item.tavsif,
                'narx': str(item.narx),
                'price': float(item.narx),
                'tayyorlanish_vaqti': item.tayyorlanish_vaqti,
                'kategoriya': item.kategoriya.nom,
                'category': item.kategoriya.nom,
                'category_slug': item.kategoriya.slug,
                'rasm': item.rasm.url if item.rasm else '',
                'image': item.rasm.url if item.rasm else '',
            }
            grouped[item.kategoriya.slug]['taomlar'].append(dish_dict)
            all_items.append(dish_dict)
        return Response({'categories': list(grouped.values()), 'items': all_items})


class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer = self._get_customer(request)
        cart, _ = Cart.objects.get_or_create(mijoz=customer, faolmi=True)
        cart_items = CartItem.objects.filter(savat=cart).select_related('taom')
        data = []
        total = Decimal('0')
        for item in cart_items:
            price = item.taom.narx if item.taom and item.taom.faolmi else Decimal('0')
            item_total = price * item.miqdor
            total += item_total
            data.append({
                'id': item.id,
                'taom': item.taom_id,
                'nom': item.taom.nom if item.taom else 'Mavjud emas',
                'miqdor': item.miqdor,
                'narx': str(price),
                'jami': str(item_total),
                'faolmi': bool(item.taom and item.taom.faolmi),
            })
        return Response({'items': data, 'jami_summa': str(total.quantize(Decimal('0.01')))})

    def delete(self, request):
        customer = self._get_customer(request)
        Cart.objects.filter(mijoz=customer, faolmi=True).update(faolmi=False)
        return Response({'detail': 'Savat tozalandi.'}, status=200)

    def _get_customer(self, request):
        customer = getattr(request.user, 'customer', None)
        if not customer:
            raise Http404('Mijoz topilmadi.')
        return customer


class CartItemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return self._get_cart(request)

    def post(self, request):
        customer = self._get_customer(request)
        cart, _ = Cart.objects.get_or_create(mijoz=customer, faolmi=True)
        taom_id = request.data.get('taom')
        try:
            miqdor = int(request.data.get('miqdor', 1))
        except (TypeError, ValueError):
            return Response({'detail': 'Miqdor butun son bo‘lishi kerak.'}, status=400)
        if not 1 <= miqdor <= 50:
            return Response({'detail': 'Miqdor 1 dan 50 gacha bo‘lishi kerak.'}, status=400)
        try:
            taom = Dish.objects.get(pk=taom_id)
        except Dish.DoesNotExist:
            return Response({'detail': 'Bunday taom yo‘q.'}, status=404)
        if not taom.faolmi:
            return Response({'detail': f'{taom.nom} hozir mavjud emas.'}, status=400)
        item, created = CartItem.objects.get_or_create(savat=cart, taom=taom)
        if not created:
            item.miqdor = min(50, item.miqdor + miqdor)
        else:
            item.miqdor = miqdor
        item.save()
        return Response({'detail': 'Savatga qo‘shildi.', 'count': cart.qatorlar.count()}, status=201)

    def patch(self, request, pk=None):
        item = CartItem.objects.select_related('savat', 'taom').get(id=pk, savat__mijoz=self._get_customer(request), savat__faolmi=True)
        miqdor = int(request.data.get('miqdor', item.miqdor))
        if miqdor <= 0:
            item.delete()
            return Response({'detail': 'Qator o‘chirildi.'}, status=200)
        item.miqdor = min(50, miqdor)
        item.save(update_fields=['miqdor'])
        return Response({'detail': 'Miqdor yangilandi.'}, status=200)

    def delete(self, request, pk=None):
        item = CartItem.objects.filter(id=pk, savat__mijoz=self._get_customer(request), savat__faolmi=True).first()
        if not item:
            return Response({'detail': 'Qator topilmadi.'}, status=404)
        item.delete()
        return Response({'detail': 'Qator o‘chirildi.'}, status=200)

    def _get_customer(self, request):
        customer = getattr(request.user, 'customer', None)
        if not customer:
            raise Http404('Mijoz topilmadi.')
        return customer

    def _get_cart(self, request):
        customer = self._get_customer(request)
        cart = Cart.objects.filter(mijoz=customer, faolmi=True).first()
        if not cart:
            return Response({'items': [], 'jami_summa': '0.00'})
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class OrderListAPIView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer
    pagination_class = LargeResultsPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.groups.filter(name='Oshpaz').exists():
            qs = Order.objects.select_related('mijoz').prefetch_related('qatorlar', 'tarix')
        else:
            qs = Order.objects.select_related('mijoz').filter(mijoz=getattr(user, 'customer', None)).prefetch_related('qatorlar', 'tarix')
        holat = self.request.query_params.get('holat')
        if holat:
            qs = qs.filter(holat=holat)
        return qs.order_by('-yaratilgan')

    def post(self, request, *args, **kwargs):
        customer = getattr(request.user, 'customer', None)
        if not customer:
            return Response({'detail': 'Mijoz profili topilmadi.'}, status=400)
        if customer.bloklangan:
            return Response({'detail': 'Siz bloklangansiz. Buyurtma bera olmaysiz.'}, status=403)
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            cart = Cart.objects.select_for_update().select_related('mijoz').filter(mijoz=customer, faolmi=True).first()
            return self._create_from_cart(request, serializer, customer, cart)

    def _create_from_cart(self, request, serializer, customer, cart):
        if not cart or not cart.qatorlar.exists():
            return Response({'detail': 'Bo‘sh savatdan buyurtma berib bo‘lmaydi.'}, status=400)
        invalid = cart.qatorlar.filter(taom__faolmi=False)
        if invalid.exists():
            names = ', '.join(item.taom.nom for item in invalid if item.taom)
            return Response({'detail': f'Hozir mavjud bo‘lmagan taomlar: {names}'}, status=400)

        delivery_fee = settings.DELIVERY_FEE if serializer.validated_data['yetkazish_turi'] == 'manzil' else Decimal('0.00')
        with transaction.atomic():
            order = Order.objects.create(
                mijoz=customer,
                yetkazish_turi=serializer.validated_data['yetkazish_turi'],
                stol_raqami=serializer.validated_data.get('stol_raqami'),
                manzil=serializer.validated_data.get('manzil', ''),
                telefon=serializer.validated_data.get('telefon') or customer.telefon,
                izoh=serializer.validated_data.get('izoh', ''),
                jami_summa=Decimal('0'),
                yetkazish_narxi=delivery_fee,
            )
            date_part = timezone.now().strftime('%Y%m%d')
            last = Order.objects.filter(raqam__startswith=f'B-{date_part}-').count() + 1
            order.raqam = f'B-{date_part}-{last:04d}'
            order.save(update_fields=['raqam'])
            items = []
            total = Decimal('0')
            for item in cart.qatorlar.select_related('taom').all():
                nm = item.taom.nom
                price = item.taom.narx
                qty = item.miqdor
                sub_total = price * qty
                order_item = OrderItem(
                    buyurtma=order,
                    taom=item.taom,
                    taom_nomi=nm,
                    narx=price,
                    miqdor=qty,
                    summa=sub_total,
                )
                items.append(order_item)
                total += sub_total
            OrderItem.objects.bulk_create(items)
            order.jami_summa = (total + delivery_fee).quantize(Decimal('0.01'))
            order.save(update_fields=['jami_summa'])
            cart.faolmi = False
            cart.save(update_fields=['faolmi'])
            OrderStatusLog.objects.create(buyurtma=order, eski_holat='yangi', yangi_holat='yangi', kim=None)
        return Response({'detail': 'Buyurtma yaratildi.', 'order_id': order.id, 'raqam': order.raqam, 'jami_summa': str(order.jami_summa)}, status=201)


class OrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.groups.filter(name='Oshpaz').exists():
            return Order.objects.select_related('mijoz').prefetch_related('qatorlar', 'tarix')
        return Order.objects.select_related('mijoz').filter(mijoz=getattr(user, 'customer', None)).prefetch_related('qatorlar', 'tarix')


class OrderStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = Order.objects.select_related('mijoz').get(pk=pk)
        if not self._can_manage(request.user, order):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=403)
        serializer = OrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['holat']
        current = order.holat
        if current == 'bekor_qilindi':
            return Response({'detail': 'Bekor qilingan buyurtma holatini o‘zgartirib bo‘lmaydi.'}, status=400)
        if new_status == 'yangi':
            return Response({'detail': 'yangi holatidan yangi ga qaytib bo‘lmaydi'}, status=400)
        allowed = {
            'yangi': ['tayyorlanmoqda'],
            'tayyorlanmoqda': ['tayyor'],
            'tayyor': ['berildi', 'yetkazildi'] if order.yetkazish_turi == 'manzil' else ['berildi'],
        }
        if current not in allowed or new_status not in allowed.get(current, []):
            return Response({'detail': f'{current} holatidan {new_status} ga o‘tish ruhsat etilmagan.'}, status=400)
        if request.user.is_staff and new_status in ['berildi', 'yetkazildi']:
            pass
        elif request.user.groups.filter(name='Oshpaz').exists() and new_status not in ['tayyorlanmoqda', 'tayyor']:
            return Response({'detail': 'Oshpaz faqat tayyorlanmoqda va tayyor holatlarini o‘zgartirishi mumkin.'}, status=403)

        old = order.holat
        order.holat = new_status
        order.tayyor_vaqti = timezone.now() if new_status == 'tayyor' else order.tayyor_vaqti
        order.yopilgan_vaqti = timezone.now() if new_status in ['berildi', 'yetkazildi', 'bekor_qilindi'] else None
        order.save(update_fields=['holat', 'tayyor_vaqti', 'yopilgan_vaqti'])
        OrderStatusLog.objects.create(buyurtma=order, eski_holat=old, yangi_holat=new_status, kim=request.user)
        return Response({
            'detail': f'Buyurtma holati {new_status} ga o‘zgartirildi.',
            'holat': new_status,
            'telegram_id': order.mijoz.telegram_id,
            'raqam': order.raqam,
        })

    def _can_manage(self, user, order):
        if user.is_staff:
            return True
        if user.groups.filter(name='Oshpaz').exists():
            return order.holat in ['yangi', 'tayyorlanmoqda', 'tayyor']
        return False


class OrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        customer = getattr(request.user, 'customer', None)
        if request.user.is_staff:
            order = Order.objects.filter(pk=pk).first()
        else:
            order = Order.objects.filter(pk=pk, mijoz=customer).first()
        if not order:
            return Response({'detail': 'Buyurtma topilmadi.'}, status=404)
        if not request.user.is_staff and order.holat not in ('yangi', 'tayyorlanmoqda'):
            return Response({'detail': 'Faqat yangi yoki tayyorlanayotgan buyurtmani bekor qilish mumkin.'}, status=400)
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_status = order.holat
        order.holat = 'bekor_qilindi'
        order.bekor_sababi = serializer.validated_data['sabab']
        order.yopilgan_vaqti = timezone.now()
        order.save(update_fields=['holat', 'bekor_sababi', 'yopilgan_vaqti'])
        OrderStatusLog.objects.create(
            buyurtma=order,
            eski_holat=old_status,
            yangi_holat='bekor_qilindi',
            kim=request.user,
        )
        return Response({'detail': 'Buyurtma bekor qilindi.', 'holat': order.holat})


class KitchenQueueView(APIView):
    permission_classes = [IsAuthenticated, IsChefUser]

    def get(self, request):
        orders = Order.objects.select_related('mijoz').prefetch_related('qatorlar').filter(holat__in=['yangi', 'tayyorlanmoqda']).order_by('yaratilgan')
        return Response({'orders': [{
            'id': order.id,
            'raqam': order.raqam,
            'holat': order.holat,
            'yaratilgan': order.yaratilgan.isoformat(),
            'yetkazish_turi': order.yetkazish_turi,
            'telefon': order.telefon,
            'telegram_id': order.mijoz.telegram_id,
            'jami_summa': str(order.jami_summa),
            'izoh': order.izoh,
            'kutish_daqiqasi': max(0, int((timezone.now() - order.yaratilgan).total_seconds() // 60)),
            'qatorlar': [
                {'nom': item.taom_nomi, 'miqdor': item.miqdor, 'narx': str(item.narx), 'summa': str(item.summa)}
                for item in order.qatorlar.all()
            ],
        } for order in orders]})


class ReportDailyAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        sana = request.query_params.get('sana')
        if not sana:
            return Response({'detail': 'Sana ko‘rsatilishi kerak.'}, status=400)
        try:
            day = datetime.strptime(sana, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'Sana formati noto‘g‘ri (YYYY-MM-DD).'}, status=400)
        orders = Order.objects.filter(yaratilgan__date=day)
        total = orders.aggregate(total=Sum('jami_summa'))['total'] or Decimal('0')
        return Response({'sana': str(day), 'buyurtmalar_soni': orders.count(), 'jami_tushum': str(total.quantize(Decimal('0.01'))), 'ortacha_chek': str((total / orders.count()).quantize(Decimal('0.01')) if orders.count() else Decimal('0'))})


class TopDishesAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        kun = int(request.query_params.get('kun', 7))
        from_date = timezone.now() - timezone.timedelta(days=kun)
        items = OrderItem.objects.filter(buyurtma__yaratilgan__gte=from_date).values('taom_nomi').annotate(total=Sum('miqdor')).order_by('-total')[:10]
        return Response({'items': list(items)})
