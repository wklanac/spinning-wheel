from setuptools import find_packages, setup

setup(
    name="spinning_wheel",
    version="1.0.0",
    author="wklanac",
    packages=find_packages(exclude=["tests"]),
    install_requires=[
        "gitpython",
    ],
    extras_require={
        "test": ["pytest"]
    }
)
