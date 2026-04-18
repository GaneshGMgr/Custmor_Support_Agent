from setuptools import find_packages, setup


def _read_requirements(file_path: str) -> list[str]:
    raw = open(file_path, "rb").read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-16")

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "-e", "--"))
    ]


# Read requirements from requirements.txt
requirements = _read_requirements("requirements.txt")

setup(
    name="customerSupportBot",
    version="0.0.1",
    author="Customer Support AI Team",
    author_email="supportbot@example.com",
    packages=find_packages(),  # All Python packages in the project tree
    include_package_data=True,  # Include templates/static files
    package_data={
        "core": ["../../client_side/templates/*.html"],  # include your HTML templates
    },
    install_requires=requirements,  # Install everything in requirements.txt
    entry_points={
        "console_scripts": [
            "customerSupportBot=server_side.api.main:main",  # Command-line tool
        ],
    },
)

# customerSupportBot: CLI command to start the Customer Support Agent server — no need to type the full "uvicorn server_side.api.main:app --reload" command; just run customerSupportBot.
# python setup.py install
# uv pip install -e .