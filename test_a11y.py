import re
import os

for root, _, files in os.walk('src/phids/api/templates'):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r') as f:
                content = f.read()
                buttons = re.finditer(r'<button([^>]*)>(.*?)</button>', content, re.DOTALL | re.IGNORECASE)
                for match in buttons:
                    attrs = match.group(1)
                    inner_html = match.group(2).strip()
                    if 'aria-label' not in attrs.lower() and ('<' not in inner_html and inner_html.strip() == '' or len(inner_html.strip()) < 3 and not inner_html.strip().isalnum()):
                        print(f"Missing aria-label in {filepath}: {attrs} - inner HTML: {inner_html}")
