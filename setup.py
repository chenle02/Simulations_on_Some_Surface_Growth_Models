from setuptools import setup, find_packages


# Assuming your README is in Markdown
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='tetris_ballistic',
    version='1.2.7',
    packages=find_packages(),
    # Runtime dependencies
    install_requires=[
        'numpy>=1.19.0',
        'PyYAML>=5.3',
        'scipy>=1.5.0',
        'matplotlib>=3.0.0',
        'imageio>=2.0.0',
        'joblib>=0.14.0',
        'pandas>=1.0.0',
    ],
    # Optional development dependencies
    extras_require={
        'dev': ['pytest>=6.0'],
    },
    # entry_points={
    #     'console_scripts': [
    #         'tetrisBD=tetris_ballistic.cli.main:cli',
    #     ],
    # },
    # include any other necessary setup options here
    package_data={
        "tetris_ballistic": ["configs/*.yaml", "data/*.png"],
    },
    long_description=long_description,
    long_description_content_type="text/markdown",
)
