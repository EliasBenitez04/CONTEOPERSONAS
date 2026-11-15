import sys
import types
import unittest
from unittest.mock import Mock, patch

try:
    import cv2
except ModuleNotFoundError:
    sys.modules.setdefault('cv2', types.ModuleType('cv2'))

from app.camera.rtsp import RTSPCamera


class FreshFrameTests(unittest.TestCase):
    def test_same_image_is_not_yielded_twice_even_when_copying(self):
        first, second = Mock(), Mock()
        with patch('app.camera.rtsp.Camera') as camera_type, patch('app.camera.rtsp.time.sleep'):
            camera = camera_type.return_value
            camera.is_connected.return_value = True
            camera.read.side_effect = [(True, first), (True, first), (True, second)]
            stream = RTSPCamera('unused', copy_frame=True)
            generator = stream.start()
            self.assertIs(next(generator), first.copy.return_value)
            self.assertIs(next(generator), second.copy.return_value)
            self.assertEqual(camera.read.call_count, 3)
            first.copy.assert_called_once()
            second.copy.assert_called_once()
            stream.stop()
            generator.close()

    def test_reconnect_changes_generation(self):
        with patch('app.camera.rtsp.Camera') as camera_type, patch('app.camera.rtsp.time.sleep'):
            camera = camera_type.return_value
            camera.is_connected.side_effect = [False, True, False]
            camera.connect.return_value = True
            camera.read.side_effect = [(True, object()), (False, None), (True, object())]
            stream = RTSPCamera('unused', copy_frame=False)
            generator = stream.start()
            next(generator)
            self.assertEqual(stream.connection_generation, 1)
            next(generator)
            self.assertEqual(stream.connection_generation, 2)
            stream.stop()
            generator.close()
