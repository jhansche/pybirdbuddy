#!/bin/python
from os import path

import setuptools

this_directory = path.abspath(path.dirname(__file__))

with open(path.join(this_directory, "README.md"), "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pybirdbuddy",
    version="0.0.20",
    author="jhansche",
    author_email="madcoder@gmail.com",
    description="A library to query data about a Bird Buddy smart bird feeder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jhansche/pybirdbuddy",
    packages=setuptools.find_packages(),
    python_requires='>=3.10',
    install_requires=[
        "python-graphql-client",
        "langcodes",
    ],
)
