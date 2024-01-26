from setuptools import setup, find_packages

setup(
    name='tetris_ballistic',
    version='1.2.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'tetrisBD=tetris_ballistic.cli.main:cli',
        ],
    },
    # include any other necessary setup options here
)
