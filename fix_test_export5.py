import sys
with open("tests/unit/pipeline/test_export.py", "r") as f:
    content = f.read()

# Add a mock for sklearn.impute
content = """import sys
from unittest.mock import MagicMock
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.impute'] = MagicMock()

""" + content

with open("tests/unit/pipeline/test_export.py", "w") as f:
    f.write(content)

with open("tests/unit/pipeline/test_schema.py", "r") as f:
    content = f.read()
content = """import sys
from unittest.mock import MagicMock
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.impute'] = MagicMock()

""" + content
with open("tests/unit/pipeline/test_schema.py", "w") as f:
    f.write(content)

with open("tests/unit/pipeline/test_writer.py", "r") as f:
    content = f.read()
content = """import sys
from unittest.mock import MagicMock
sys.modules['sklearn'] = MagicMock()
sys.modules['sklearn.cluster'] = MagicMock()
sys.modules['sklearn.preprocessing'] = MagicMock()
sys.modules['sklearn.impute'] = MagicMock()

""" + content
with open("tests/unit/pipeline/test_writer.py", "w") as f:
    f.write(content)
