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
    version="0.0.1",
    packages=find_packages(exclude=["examples"]),
    url="https://github.com/sclorg/betka",
    license="GPLv3+",
    author="Petr Hracek",
    author_email="phracek@redhat.com",
    install_requires=get_requirements(),
)
