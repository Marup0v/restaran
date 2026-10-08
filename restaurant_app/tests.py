from rest_framework.test import APITestCase
from django.urls import reverse


class WebCartAPITests(APITestCase):
    def test_addition_updates_session_cart(self):
        url = reverse('web_cart')

        first_response = self.client.post(
            url,
            {'product_id': 'grilled-ribeye'},
            format='json',
        )
        second_response = self.client.post(
            url,
            {'product_id': 'grilled-ribeye', 'quantity': 2},
            format='json',
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertEqual(second_response.data['count'], 3)
        self.assertEqual(second_response.data['total'], 114)
        self.assertEqual(second_response.data['items'][0]['quantity'], 3)

    def test_cart_is_isolated_between_sessions(self):
        self.client.post(
            reverse('web_cart'),
            {'product_id': 'truffle-pasta'},
            format='json',
        )

        other_client = self.client_class()
        response = other_client.get(reverse('web_cart'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'items': [], 'count': 0, 'total': 0})

    def test_unknown_product_and_invalid_quantity_are_rejected(self):
        url = reverse('web_cart')

        unknown_response = self.client.post(
            url,
            {'product_id': 'unknown'},
            format='json',
        )
        invalid_quantity_response = self.client.post(
            url,
            {'product_id': 'truffle-pasta', 'quantity': 51},
            format='json',
        )

        self.assertEqual(unknown_response.status_code, 404)
        self.assertEqual(invalid_quantity_response.status_code, 400)
        self.assertEqual(self.client.get(url).data['items'], [])

    def test_delete_clears_session_cart(self):
        url = reverse('web_cart')
        self.client.post(url, {'product_id': 'burrata-tomato'}, format='json')

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'items': [], 'count': 0, 'total': 0})

    def test_delete_can_remove_one_product_without_clearing_other_items(self):
        url = reverse('web_cart')
        self.client.post(url, {'product_id': 'burrata-tomato'}, format='json')
        self.client.post(url, {'product_id': 'truffle-pasta'}, format='json')

        response = self.client.delete(
            url,
            {'product_id': 'burrata-tomato'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['items'][0]['product_id'], 'truffle-pasta')
