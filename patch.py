import re
with open("tests/test_dom_a11y.py", "r") as f:
    content = f.read()

# Make the close button lookup robust (don't rely strictly on type="submit" if it has class action-btn, or we can check for type submit explicitly since we know it has type="submit")
# Actually, the feedback says: "The close-button lookup requires an explicit type="submit", which wrongly fails buttons that rely on the default submit type."

new_test = """    def test_how_to_use_modal_accessibility_and_escape(self):
        \"\"\"Verify native <dialog> Escape regression test and accessibility for How-To-Use modal.\"\"\"
        dialog = self.soup.find('dialog', id='howToUseModal')
        self.assertIsNotNone(dialog, "howToUseModal dialog not found")

        # Verify accessible name
        has_label = dialog.has_attr('aria-label')
        has_labelledby = dialog.has_attr('aria-labelledby')
        self.assertTrue(has_label or has_labelledby, "Dialog missing accessible name")

        # Verify aria-labelledby references
        if has_labelledby:
            label_ids = dialog['aria-labelledby'].split()
            for label_id in label_ids:
                label_element = self.soup.find(id=label_id)
                self.assertIsNotNone(label_element, f"Dialog labelledby element {label_id} not found")
                self.assertTrue(bool(label_element.get_text(strip=True)), f"Dialog label element {label_id} is empty")

        # Verify close control
        # Find any button in a form method="dialog"
        form = dialog.find('form', attrs={'method': lambda x: x and x.lower() == 'dialog'})
        self.assertIsNotNone(form, "Form with method='dialog' not found in dialog")

        # Default button type is submit. We find a button that is either type submit or has no type.
        close_btn = None
        for btn in form.find_all('button'):
            btn_type = btn.get('type', 'submit').lower()
            if btn_type == 'submit':
                close_btn = btn
                break

        self.assertIsNotNone(close_btn, "Close button not found in dialog")
        btn_label = close_btn.get('aria-label', '').strip() or close_btn.get('title', '').strip() or close_btn.get_text(strip=True)
        self.assertTrue(bool(btn_label), "Close button missing accessible name")

        # Verify no custom keydown handler (regression guard for native Escape reliance)
        self.assertFalse(dialog.has_attr('onkeydown'), "Dialog should not have a custom onkeydown handler")
"""

content = re.sub(
    r"    def test_how_to_use_modal_accessibility_and_escape\(self\):.*",
    new_test,
    content,
    flags=re.DOTALL
)

with open("tests/test_dom_a11y.py", "w") as f:
    f.write(content)
