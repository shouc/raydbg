from setuptools import setup, find_packages

setup(
    name='raydbg',  # This is the name people will use to install your package, i.e., pip3 install raydbg
    version='0.1.0',
    author='Chaofan Shou',
    author_email='shou@berkeley.edu',
    description='A tool for debugging Ray programs',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url='https://github.com/shouc/raydbg',
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "wget==3.2",
        "retry==0.9.2",
        "openai==0.28.0",
        "ray",
    ],
    entry_points={
        'console_scripts': [
            'raydbg=raydbg.cli:main'
        ],
    },
)
