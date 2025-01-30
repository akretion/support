import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo8-addons-akretion-support",
    description="Meta package for akretion-support Odoo addons",
    version=version,
    install_requires=[
        'odoo8-addon-project_api_client',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 8.0',
    ]
)
