from setuptools import setup, find_packages


# Assuming your README is in Markdown
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='tetris_ballistic',
    version='1.2.3',
    packages=find_packages(),
    # entry_points={
    #     'console_scripts': [
    #         'tetrisBD=tetris_ballistic.cli.main:cli',
    #     ],
    # },
    # include any other necessary setup options here
    long_description=long_description,
    long_description_content_type="text/markdown",
)
