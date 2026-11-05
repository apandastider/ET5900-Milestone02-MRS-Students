
import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'mrs_milestone2'


def get_files(directory):
    """Return regular files only, excluding Python cache files."""
    return [
        path
        for path in glob(os.path.join(directory, '*'))
        if os.path.isfile(path)
        and not path.endswith(('.pyc', '.pyo'))
    ]


setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test', 'tests']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        (
            'share/' + package_name,
            ['package.xml'],
        ),
        (
            'share/' + package_name + '/launch',
            get_files('launch'),
        ),
        (
            'share/' + package_name + '/worlds',
            get_files('worlds'),
        ),
        (
            'share/' + package_name + '/config',
            get_files('config'),
        ),
        (
            'share/' + package_name + '/scripts',
            get_files('scripts'),
        ),
        (
            'share/' + package_name + '/docs',
            get_files('docs'),
        ),
    ],
    install_requires=[
        'setuptools',
        'PyYAML',
    ],
    zip_safe=True,
    maintainer='apan',
    maintainer_email='apan@example.com',
    description='ROS 2 multi-robot coordination simulation and FSM',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'milestone2_init_amcl = mrs_milestone2.fsm_initialize_amcl:main',
        ],
    },
)
