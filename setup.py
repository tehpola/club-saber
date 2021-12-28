from setuptools import setup, find_packages
import re

try:
    import py2exe
except ImportError:
    # No Windows executables to build here
    pass


def get_version(filename):
    content = open(filename).read()
    metadata = dict(re.findall("__([a-z]+)__ = '([^']+)'", content))
    return metadata['version']


setup(
    name='club-saber',
    version=get_version('clubsaber/__init__.py'),
    url='https://git.slegeir.com/mike/wiz-saber',
    license='Apache License, Version 2.0',
    author='Mike Slegeir',
    author_email='tehpola@gmail.com',
    description='A Beat Saber service which controls smart lights based on map data',
    long_description=open('README.md').read(),
    packages=find_packages(exclude=['tests', 'tests.*']),
    zip_safe=False,
    install_requires=[
        'setuptools',
        'appdirs',
        'pywizlight',
        'websockets',
    ],
    entry_points={
        'console_scripts': [
            'club_saber = clubsaber.main:main',
        ],
    },
    options={
        'py2exe': {
            'bundle_files': 1,
            'compressed': True,
            'includes': ['websockets.legacy', 'websockets.legacy.client'],
        },
    },
    console=[{
        'script': 'clubsaber/main.py',
    }],
    zipfile=None,
    classifiers=[
        'Environment :: Plugins',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Games/Entertainment :: Arcade',
    ],
)

