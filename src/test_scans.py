import io
from pathlib import Path
import tempfile
import unittest
from PIL import Image
import pymupdf
from scan_view import read_scan

class ScanTests(unittest.TestCase):
    def test_image_and_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path=Path(tmp)/'scan.jpg'
            Image.new('RGB',(100,140),'white').save(image_path)
            image,data,pages=read_scan(str(image_path))
            self.assertEqual((100,140),image.size)
            self.assertIsNone(data)
            pdf_path=Path(tmp)/'scan.pdf'
            with pymupdf.open() as document:
                document.new_page();document.new_page();document.save(pdf_path)
            image,data,pages=read_scan(str(pdf_path))
            self.assertEqual(2,pages)
            self.assertTrue(data.startswith(b'%PDF'))

    def test_html_is_not_mistaken_for_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'portal.html'
            path.write_text('<html>Login</html>')
            with self.assertRaisesRegex(ValueError,'direkte Bild-URL'):
                read_scan(str(path))

if __name__=='__main__':unittest.main()
