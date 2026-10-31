from setuptools import setup, find_packages


# Assuming your README is in Markdown
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='tetris_ballistic',
    version='1.2.8',
    packages=find_packages(include=["tetris_ballistic", "tetris_ballistic.*"]),
    python_requires=">=3.9",
    install_requires=[
        "numpy",
        "matplotlib",
        "scipy",
        "imageio",
        "pyyaml",
        "joblib",
    ],
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
