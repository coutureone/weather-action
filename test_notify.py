import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from notify import send_tink


class TinkRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.url = 'https://tink.example.com/api/v1/messages'
        self.payload = {'title': '测试', 'devices': ['mac-one', 'mac-two'], 'bark_devices': ['phone']}
        self.saved = {'code': 0, 'data': {'id': 42, 'dispatched_tink': 0, 'dispatched_bark': 1}}

    @patch('notify.request_json')
    def test_offline_desktops_do_not_block_phone(self, request):
        request.return_value = self.saved
        self.assertEqual(send_tink(self.url, 'test-key', self.payload), self.saved)
        self.assertEqual(request.call_count, 1)

    @patch('notify.request_json')
    def test_missing_device_registry_is_restored_then_same_notification_sent(self, request):
        error = urllib.error.HTTPError(self.url, 404, 'missing', {}, io.BytesIO(
            json.dumps({'message': 'device mac-one not found'}).encode()))
        request.side_effect = [error, {'code': 0, 'data': []}, {'code': 0}, {'code': 0}, self.saved]
        self.assertEqual(send_tink(self.url, 'test-key', self.payload), self.saved)
        calls = request.call_args_list
        self.assertEqual(calls[2].args[2]['id'], 'mac-one')
        self.assertEqual(calls[3].args[2]['id'], 'mac-two')
        self.assertEqual(calls[0].args, calls[-1].args)

    @patch('notify.request_json')
    def test_endpoint_404_does_not_register_devices(self, request):
        request.side_effect = urllib.error.HTTPError(self.url, 404, 'missing', {}, io.BytesIO(
            json.dumps({'message': 'endpoint not found'}).encode()))
        with self.assertRaises(urllib.error.HTTPError):
            send_tink(self.url, 'test-key', self.payload)
        self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
