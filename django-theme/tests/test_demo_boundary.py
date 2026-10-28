"""The demo must remain local even with forged Host/forwarded headers."""
from unittest.mock import Mock

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.local_demo import LoopbackOnlyMiddleware


@override_settings(NOVA_DEMO_LOOPBACK_ONLY=True)
class DemoBoundaryTests(SimpleTestCase):
    def test_only_loopback_peers_reach_the_application(self):
        downstream = Mock(return_value=HttpResponse())
        middleware = LoopbackOnlyMiddleware(downstream)
        for peer in ('127.0.0.1', '::1'):
            self.assertEqual(middleware(RequestFactory().get('/', REMOTE_ADDR=peer)).status_code, 200)
        for peer in ('192.0.2.1', '0.0.0.0', '', 'invalid'):
            with self.subTest(peer=peer):
                request = RequestFactory().get('/', REMOTE_ADDR=peer, HTTP_HOST='localhost', HTTP_X_FORWARDED_FOR='127.0.0.1')
                self.assertEqual(middleware(request).status_code, 403)
        self.assertEqual(downstream.call_count, 2)
