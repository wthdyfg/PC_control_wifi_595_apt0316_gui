from setuptools import setup
from Cython.Build import cythonize
import os

# 编译命令: python setup.py build_ext --inplace

setup(
    name='uart_sdk',
    ext_modules=cythonize("uart_sdk.py", language_level="3"),
    zip_safe=False,
)
