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

    def test_input_accessibility(self):
        """Verify that all interactive inputs have an associated label or aria-label."""
        interactive_elements = self.soup.find_all(['input', 'select', 'textarea'])
        self.assertTrue(len(interactive_elements) > 0, "No interactive elements found to test")
        for el in interactive_elements:
            # Skip hidden inputs
            if el.name == 'input' and el.get('type') == 'hidden':
                continue

            has_aria_label = bool(el.get('aria-label', '').strip()) or bool(el.get('aria-labelledby', '').strip())
            has_title = bool(el.get('title', '').strip())

            # Button-like inputs can take name from 'value' or 'alt'
            has_value = False
            has_alt = False
            if el.name == 'input':
                type_attr = el.get('type', '').lower()
                if type_attr in ('submit', 'button', 'reset'):
                    has_value = bool(el.get('value', '').strip())
                elif type_attr == 'image':
                    has_alt = bool(el.get('alt', '').strip())

            # Check if it has an associated <label for="...">
            has_explicit_label = False
            if el.has_attr('id'):
                label = self.soup.find('label', attrs={'for': el['id']})
                if label:
                    has_explicit_label = True

            # Check if it is nested inside a <label>
            has_implicit_label = False
            parent = el.parent
            while parent is not None and parent.name != 'body':
                if parent.name == 'label':
                    has_implicit_label = True
                    break
                parent = parent.parent

            self.assertTrue(
                has_aria_label or has_title or has_value or has_alt or has_explicit_label or has_implicit_label,
                f"Interactive element {el.name} (id='{el.get('id')}') is missing an accessible label"
            )

    def test_button_accessibility(self):
        """Verify that all buttons have accessible names (text, aria-label, aria-labelledby, or title)."""
        buttons = self.soup.find_all('button')
        self.assertTrue(len(buttons) > 0, "No buttons found to test")
        for btn in buttons:
            label = btn.get('aria-label', '').strip() or btn.get('title', '').strip() or btn.get_text(strip=True)

            has_valid_labelledby = False
            labelledby = btn.get('aria-labelledby', '').strip()
            if labelledby:
                # Need to check if id exists
                target = self.soup.find(id=labelledby)
                if target:
                    has_valid_labelledby = True

            self.assertTrue(
                bool(label) or has_valid_labelledby,
                f"Button {btn.get('id') or btn} is missing an accessible name"
            )

    def test_empty_error_loading_states_have_aria_live(self):
        """Verify that dynamic status elements (empty, error, loading) have aria-live or role=status."""
        # Elements like range-status, aimOffsetBanner, ocrStatusText, globalPttStatusText, demHeightBadge

        status_elements = [
            'rangeStatus',
            'aimOffsetBanner',
            'ocrStatusText',
            'globalPttStatusText',
            'voiceStatus',
            'demHeightBadge'
        ]

        for element_id in status_elements:
            el = self.soup.find(id=element_id)
            if el:
                has_aria_live = el.has_attr('aria-live')
                has_role_status = el.get('role') == 'status'
                has_role_alert = el.get('role') == 'alert'
                has_role_log = el.get('role') == 'log'

                # Check parents up to 3 levels for aria-live
                parent_has_live = False
                parent = el.parent
                for _ in range(3):
                    if parent and parent.has_attr('aria-live'):
                        parent_has_live = True
                        break
                    if parent:
                        parent = parent.parent

                self.assertTrue(
                    has_aria_live or has_role_status or has_role_alert or has_role_log or parent_has_live,
                    f"Dynamic status element '{element_id}' is missing accessibility attributes (aria-live or role=status/alert)"
                )
