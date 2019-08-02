from setuptools import setup

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

with open('README.md') as f:
    readme = f.read()

setup(
    name='har2swagger',
    version='0.0.1',
    description='convert har to swagger',
    long_description=readme,
    author='hugo',
    author_email='hugoxia@126.com',
    url='https://github.com/hugoxia/har2swagger',
    license='MIT',
    install_requires=requirements,
    classifiers=[
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='swagger',
    entry_points={
        'console_scripts': [
            'har2swagger = har2swagger:main',
        ]
    },
    packages=['har2swagger']
)
