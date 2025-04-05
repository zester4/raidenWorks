# Placeholder for Sphinx configuration
project = "Raiden Agent"
author = "Seyyid Annan / Team"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",  # Automatically include docstrings
    "sphinx.ext.napoleon",  # Support for Google and NumPy style docstrings
    "sphinx.ext.viewcode",  # Add links to highlighted source code
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]

# Add project-specific configurations if needed
# e.g., intersphinx_mapping, autodoc_default_options, etc.
