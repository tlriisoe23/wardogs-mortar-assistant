import os
import unittest
from bs4 import BeautifulSoup

class TestIndexHtmlA11y(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'index.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            cls.html = f.read()
        cls.soup = BeautifulSoup(cls.html, 'html.parser')

    def test_dialog_accessibility(self):
        """Verify that all <dialog> elements have valid accessible names."""
        dialogs = self.soup.find_all('dialog')
        self.assertTrue(len(dialogs) > 0, "No dialogs found to test")
        for dialog in dialogs:
            has_label = dialog.has_attr('aria-label')
            has_labelledby = dialog.has_attr('aria-labelledby')
            self.assertTrue(has_label or has_labelledby, f"Dialog {dialog.get('id')} missing accessibility label")

            if has_labelledby:
                label_id = dialog['aria-labelledby']
                label_element = self.soup.find(id=label_id)
                self.assertIsNotNone(label_element, f"Dialog labelledby element {label_id} not found")

    def test_tab_accessibility(self):
        """Verify that all tabs have the correct ARIA attributes."""
        tabs = self.soup.find_all(role='tab')
        self.assertTrue(len(tabs) > 0, "No tabs found to test")
        for tab in tabs:
            self.assertTrue(tab.has_attr('aria-controls'))
            self.assertTrue(tab.has_attr('aria-selected'))
            self.assertTrue(tab.has_attr('tabindex'))

            controls_id = tab['aria-controls']
            panel = self.soup.find(id=controls_id)
            self.assertIsNotNone(panel, f"Tabpanel {controls_id} not found")
            self.assertEqual(panel.get('role'), 'tabpanel')

    def test_tabpanel_accessibility(self):
        """Verify that all tabpanels have valid aria-labelledby attributes."""
        panels = self.soup.find_all(role='tabpanel')
        self.assertTrue(len(panels) > 0, "No tabpanels found to test")
        for panel in panels:
            self.assertTrue(panel.has_attr('aria-labelledby'))
            label_id = panel['aria-labelledby']
            label = self.soup.find(id=label_id)
            self.assertIsNotNone(label, f"Tab label {label_id} not found")
            self.assertEqual(label.get('role'), 'tab')
