from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="autopod",
    version="0.1.0",
    author="Raymond Wolt",
    author_email="rjwolt@gmail.com",
    description="A lightweight CLI controller for automating ComfyUI workflows on RunPod instances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rwolt/autopod",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=[
        "rich>=13.0.0",
        "requests>=2.31.0",
        "websocket-client>=1.6.0",
        "paramiko>=3.3.0",
        "runpod>=1.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "autopod=autopod.cli:main",
        ],
    },
)
