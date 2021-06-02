"""
A setuptools based setup module.
"""

from setuptools import setup, find_packages
from os import path
import re

# Get the long description from the README file
here = path.abspath(path.dirname(__file__))
with open(path.join(here, "README.md")) as f:
    long_description = f.read()


def find_version(*file_paths):
    """
    Reads out software version from provided path(s).
    """
    version_file = open("/".join(file_paths), 'r').read()
    lookup = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                       version_file, re.M)

    if lookup:
        return lookup.group(1)

    raise RuntimeError("Unable to find version string.")


setup(
    name="AssetsStore",
    version=find_version("assetsstore", "assets", "__init__.py"),
    description="Python package storing files to selected storage like AWS S3 or just Instance of a linux server via SSH",
    long_description=long_description,
    url="",
    packages=find_packages(exclude=["doc"]),
    include_package_data=True,
    namespace_packages=["assetsstore"],
    author="Nebojsa Mrkic",
    author_email="mrkic.nebojsa@gmail.com",
    license="Apache 2.0",
    install_requires=[
        "overrides>=1.8",
        "boto3==1.9.228",
        "boto==2.49.0",
        "azure-storage-blob==2.1.0",
        "paramiko==2.6.0",
        "requests>=2.25.0",
        "urllib3==1.26.5"
    ],
    dependency_links=[
    ],
    setup_requires=["pytest-runner"],
    tests_require=[
        "pytest",
        "mock",
    ],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
    ],
)
