#!/usr/bin/env python
#
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

import ez_setup


ez_setup.use_setuptools()


__version__ = '0.2.1'

from setuptools import setup

setup(
    name='shelltoolbox',
    version=__version__,
    packages=['shelltoolbox'],
    include_package_data=True,
    zip_safe=False,
    maintainer='Launchpad Yellow',
    description=('Helper functions for interacting with shell commands'),
    license='GPL v3',
    url='https://launchpad.net/python-shell-toolbox',
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
    ],
)
