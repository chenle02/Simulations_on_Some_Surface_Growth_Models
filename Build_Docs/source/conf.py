# Configuration file for the Sphinx documentation builder.
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#

import os
import sys
# from datetime import datetime

# import your_package

# version = your_package.__version__
# release = version

# The short X.Y version.
version = '1.2.2'

# The full version, including alpha/beta/rc tags.
release = '1.2.2'

sys.path.insert(0, os.path.abspath('../../'))
sys.path.insert(0, os.path.abspath('../../../'))
sys.path.insert(0, os.path.abspath('../../tetris_ballistic'))
sys.path.insert(0, os.path.abspath('../../tetris_ballistic/cli'))


# -- Project information -----------------------------------------------------

project = 'Surface Growth with Random Tetris Pieces'
copyright = '2023, Le Chen, Mauricio Montes, Ian Ruau'
author = 'Le Chen, Mauricio Montes, Ian Ruau'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
    'myst_parser',
    'sphinxcontrib.bibtex',
]

napoleon_google_docstring = True
napoleon_numpy_docstring = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# Some of the popular built-in themes include 'alabaster', 'classic', 'sphinx_rtd_theme' (Read the Docs theme), 'nature', and 'pyramid'.

# html_theme = 'alabaster'
# html_theme = 'nature'
# html_theme = 'pyramid'
# html_theme = 'classic'
# html_theme = 'groundwork'
html_theme = 'press'


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

myst_enable_extensions = [
    'colon_fence',
    'amsmath',
    'dollarmath',
    # ... other extensions
]

bibtex_bibfiles = ['doc_rst/All.bib']
math_numfig = True

latex_elements = {
    'preamble': r'''
    \usepackage{amsmath}
    % \numberwithin{equation}{section}
    '''
}

# html_footer = "This project is partially supported by the National Science Foundation under Grant No. 2246850 and the collaboration/travel award from the Simons foundation under Award No. 959981."

# html_footer = '''
# <div class="custom-footer">
#     <p>This work is supported by the National Science Foundation under Grant No. <a href="https://www.nsf.gov/awardsearch/showAward?AWD_ID=2246850">2246850</a> and the collaboration/travel award from the Simons foundation under Award No. 959981.</p>
#     <p>&copy; {year} All rights reserved.</p>
# </div>
# '''.format(year=datetime.now().year)
