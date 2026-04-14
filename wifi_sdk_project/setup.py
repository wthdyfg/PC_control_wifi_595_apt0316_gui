from setuptools import setup
from Cython.Build import cythonize
import os

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

setup(
    name="wifi_sdk",
    ext_modules=cythonize(
        os.path.join(current_dir, "wifi_sdk.py"),
        compiler_directives={'language_level': "3"}
    ),
    zip_safe=False,
)
