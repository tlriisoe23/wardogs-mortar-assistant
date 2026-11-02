import os
import re
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
            self.assertTrue(dialog.has_attr('aria-modal') and dialog['aria-modal'] == 'true', f"Dialog {dialog.get('id')} missing aria-modal='true'")
            self.assertTrue(has_label or has_labelledby, f"Dialog {dialog.get('id')} missing accessibility label")

            if has_labelledby:
                label_id = dialog['aria-labelledby']
                label_element = self.soup.find(id=label_id)
                self.assertIsNotNone(label_element, f"Dialog labelledby element {label_id} not found")

    def test_native_dialog_escape_key_handling(self):
        """Verify that native HTML <dialog> elements rely on built-in Escape key handling."""
        # Instead of generic regex, ensure the specific fallback dialog script doesn't bind a redundant keydown listener.
        dialog_scripts = self.soup.find_all('script')
        has_keydown_listener = False
        found_fallback_script = False
        for script in dialog_scripts:
            script_content = script.string
            if script_content and 'initHowToUseDialogFallback' in script_content:
                found_fallback_script = True

                # Extract the function body
                idx = script_content.find('initHowToUseDialogFallback')
                if idx != -1:
                    # find the next function or the end of the script
                    next_func_idx = script_content.find('function ', idx + 26)
                    if next_func_idx == -1:
                        next_func_idx = len(script_content)

                    func_body = script_content[idx:next_func_idx]
                    if re.search(r"addEventListener\(\s*['\"]keydown['\"][^;]{0,400}?Escape", func_body, re.IGNORECASE | re.DOTALL):
                        has_keydown_listener = True

        self.assertTrue(found_fallback_script, 'initHowToUseDialogFallback script not found')

        self.assertFalse(
            has_keydown_listener,
            "Redundant keydown listener for Escape found in dialog fallback initialization script. "
            "Native <dialog> elements should rely on built-in Escape handling."
        )

        # Verify that the dialog elements exist to be tested
        self.assertTrue(len(self.soup.find_all('dialog')) > 0, "No dialogs found to verify")

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

    def test_recon_close_button_has_aria_label(self):
        """Verify that the close PIP window button has an explicit aria-label."""
        recon_html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'recon.html')
        with open(recon_html_path, 'r', encoding='utf-8') as f:
            recon_html = f.read()
        recon_soup = BeautifulSoup(recon_html, 'html.parser')
        close_btn = recon_soup.find('button', class_='btn-close')
        self.assertIsNotNone(close_btn, "Close PIP button not found")
        self.assertTrue(bool(close_btn.get('aria-label', '').strip()), "Close PIP button is missing aria-label")

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

    def test_simplified_single_screen_ergonomics_and_pruned_bloat(self):
        """Verify AIS-487 feature pruning and single-screen zero-friction controls."""
        self.assertIsNotNone(self.soup.find(id='topPttToggleBtn'))
        self.assertIsNotNone(self.soup.find(id='topOcrToggleBtn'))
        self.assertIsNotNone(self.soup.find(id='quickCoordInput'))
        self.assertIsNotNone(self.soup.find(id='solutionHeroBar'))
        self.assertIn('parseDualCoordLineJs', self.html)
        self.assertIsNone(self.soup.find(id='tabPythBtn'))
        self.assertIsNone(self.soup.find(id='pythagorasViewContainer'))
        self.assertIsNone(self.soup.find(id='customRangeAdj'))
        self.assertIsNone(self.soup.find(id='mapBarLockMortarBtn'))

    def test_high_resolution_4k_base_maps_and_16k_tile_pyramid_streaming(self):
        """Verify 4096x4096 base maps and Level 3/4/5 (up to 16384x16384, 1m/px) tile pyramid streaming."""
        from PIL import Image
        self.assertIn("https://cdn.wardogshub.gg/bakurani/v2", self.html)
        self.assertIn("https://cdn.wardogshub.gg/europe/v1", self.html)
        self.assertIn("https://cdn.wardogshub.gg/north-america/v1", self.html)
        self.assertIn("buildFallbackMirrorTileUrl", self.html)
        self.assertIn("ctx.imageSmoothingQuality = 'high'", self.html)

        repo_root = os.path.dirname(os.path.dirname(__file__))
        for map_file in ("bakurani.webp", "ozeti.webp", "zestafona.webp"):
            p = os.path.join(repo_root, "maps", map_file)
            with Image.open(p) as im:
                self.assertEqual(im.size, (4096, 4096), f"{map_file} should be 4096x4096 (Level 3)")
