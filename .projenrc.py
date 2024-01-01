from projen.python import PythonProject
from projen import TextFile


AUTHORS = [
    "Jacob Petterle",
]
PROJECT = PythonProject(
    author_email="jacobpetterle@tai-tutor.team",
    author_name=AUTHORS[0],
    module_name="pinecone_constructs",
    name="pinecone_constructs",
    version="0.0.0",
    description="description",
    poetry=True,
    deps=[
        "python@^3.8",
        "pydantic@^2.4",
        "pydantic-settings@^2.0",
    ],
    dev_deps=[
        "projen@<=0.72.0",
        "aws-cdk-lib@^2.69",
        "crhelper@^2.0",
        "aws-cdk.aws-lambda-python-alpha@^2.69.0a0",
        "pinecone-client@^2.0",
        "aws-lambda-powertools@^2.0",
    ],
)
PROJECT.add_git_ignore("**/cdk.out")
PROJECT.add_git_ignore("**/.venv*")

MAKEFILE_CONTENTS = """\
install:
    npm install -g projen aws-cdk
    curl -sSL https://install.python-poetry.org | python3 -
	poetry install
    poetry shell

synth:
	projen --post false

update-deps:
\tpoetry update

docker-start:
\tsudo systemctl start docker

cdk-deploy-all:
\tcdk deploy --all --require-approval never --app "python pinecone_constructs/examples/aws/app.py"
"""

MAKEFILE = TextFile(
    PROJECT,
    "Makefile",
    lines=MAKEFILE_CONTENTS.splitlines(),
    committed=True,
    readonly=True,
)
CONFIGURE_GITHUB_CREDS_CONTENTS = """\
#!/bin/bash

# Check if the correct number of parameters are passed
if [ "$#" -ne 2 ]; then
    echo "Usage: ./setupGitCLI.sh [email] [name]"
    exit 1
fi

# Setup git cli with provided email and name
git config --global user.email "$1"
git config --global user.name "$2"
projen
echo "Git has been configured with Email: $1 and Name: $2"
"""
CONFIGURE_GITHUB_CREDS = TextFile(
    PROJECT,
    "configureGitCLI.sh",
    lines=CONFIGURE_GITHUB_CREDS_CONTENTS.splitlines(),
    committed=True,
    readonly=True,
)


PROJECT.synth()
