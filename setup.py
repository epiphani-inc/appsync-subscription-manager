from setuptools import setup
from os import path
from io import open

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='epiphani-appsync-subscription-manager',
    version='0.1.1',
    license='MIT',
    install_requires=[
        'enum34;python_version<"3.4"',
        'future',
        'six',
        'warrant>=0.6.1',
        'websocket-client>=0.57.0'
    ],
    python_requires='>=2.7',
    author='Praveen Madhav',
    author_email='praveen@epiphani.io',
    url='https://github.com/epiphani-inc/appsync-subscription-manager',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['appsync_subscription_manager'],
    include_package_data=True,
    description="Appsync python client for consuming the graphql endpoint",
)
