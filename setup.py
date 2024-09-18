import os

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup


def get_requirements():
    """Parse all packages mentioned in the 'requirements.txt' file."""
    with open("requirements.txt") as file_stream:
        return file_stream.read().splitlines()


setup(
    name="betka",
    version="0.7.15",
    packages=find_packages(exclude=["examples", "tests"]),
    url="https://github.com/sclorg/betka",
    license="GPLv3+",
    author="Petr Hracek",
    author_email="phracek@redhat.com",
    install_requires=get_requirements(),
    package_data={
        "betka": [
            os.path.join("data", "schemas", "*.json"),
            os.path.join("data", "conf.d", "*.yml"),
            os.path.join("data", "defaults", "*.yml"),
        ]
    },
)
