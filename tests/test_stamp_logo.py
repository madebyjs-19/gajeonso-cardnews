import tempfile
from pathlib import Path
import unittest

try:
    import numpy as np
    from PIL import Image
    from stamp_logo import stamp, logo_navy, with_badge, NAVY, ICE
    HAS_IMAGES = True
except ImportError:
    HAS_IMAGES = False


@unittest.skipUnless(HAS_IMAGES, 'Pillow and numpy required for logo tests')
class LogoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'card1.png'

    def test_white_and_navy_covers_emit_png_and_jpg(self):
        for color in ((255, 255, 255), NAVY):
            Image.new('RGB', (1080, 1350), color).save(self.path)
            self.assertEqual(stamp(str(self.path)), 0)
            for suffix in ('.png', '.jpg'):
                with Image.open(self.path.with_suffix(suffix)) as image:
                    self.assertEqual(image.size, (1080, 1350))
            colors = np.asarray(Image.open(self.path))
            self.assertTrue(np.any(np.all(colors == NAVY, axis=2)))
            if color == NAVY:
                self.assertTrue(np.any(np.all(colors == ICE, axis=2)))

    def test_occupied_cover_is_not_overwritten(self):
        image = Image.new('RGB', (1080, 1350), 'red')
        # Nonuniform candidate regions, with white reference pixel.
        image.putpixel((540, 24), (255, 255, 255))
        image.save(self.path)
        before = self.path.read_bytes()
        self.assertEqual(stamp(str(self.path)), 2)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.path.with_suffix('.jpg').exists())

    def test_invalid_dimensions_and_empty_logo(self):
        Image.new('RGB', (100, 100), 'white').save(self.path)
        with self.assertRaises(ValueError):
            stamp(str(self.path))
        with self.assertRaises(ValueError):
            logo_navy(str(self.path))


if __name__ == '__main__':
    unittest.main()
