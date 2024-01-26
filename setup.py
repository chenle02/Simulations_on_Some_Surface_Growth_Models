from setuptools import setup, find_packages

setup(
    name='tetris_ballistic/',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'tetrisBD=tetris_ballistic.cli.main:main',
        ],
    },
    # include any other necessary setup options here
)
