with open("ocr_sniff.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'error": "OCR extraction failed",' in line:
        new_lines.append('            "error": "OCR extraction failed",\n')
        # Add a print statement before return to log the error as requested by the audit
        new_lines.insert(-1, '        print(f"[WinOCR Warning] Extraction failed: {e}")\n')
    else:
        new_lines.append(line)
