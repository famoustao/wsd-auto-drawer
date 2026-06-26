from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="wsd-auto-drawer",
    version="1.0.0",
    author="WSD Auto Drawer Team",
    description="SVG to WSD converter and auto-drawing tool for EduEditor",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/famoustao/wsd-auto-drawer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Topic :: Education",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "wsd-drawer=main:main",
            "wsd-gui=gui:main",
            "wsd-web=web_ui:main",
        ],
    },
)
