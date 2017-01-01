# -*- coding: utf-8 -*-

# To deploy:
# rm -rf dist && python3 setup.py sdist && twine upload dist/*

import sys
from setuptools import setup, find_packages
from codecs import open

setup(
	name='exclusiveprocess',
	version='0.9.1',

	description='Exclusive process locking to ensure that your code does not execute concurrently, using POSIX file locking.',
	long_description=open("README.rst", encoding='utf-8').read(),
	url='https://github.com/JoshData/exclusiveprocess',

	author=u'Joshua Tauberer',
	author_email=u'jt@occams.info',
	license='CC0 (copyright waived)',

	# See https://pypi.python.org/pypi?%3Aaction=list_classifiers
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',

		'Intended Audience :: Developers',
		'Topic :: Software Development :: Libraries :: Python Modules',

		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: 3.6',
	],

	keywords="exclusive process POSIX lock pid concurrent global system",

	packages=find_packages(),
)
