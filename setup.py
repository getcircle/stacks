from setuptools import setup, find_packages

import blueprints

setup(
    name='blueprints',
    version=blueprints.__version__,
    author='Michael Hahn',
    author_email='michael@lunohq.com',
    url='https://github.com/getcircle/stacks.git',
    description='Stacker blueprints',
    packages=find_packages(),
)
