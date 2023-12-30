install:
	npm install -g projen aws-cdk
	curl -sSL https://install.python-poetry.org | python3 -
	poetry install
	poetry shell

synth:
	projen --post false

update-deps:
	poetry update

docker-start:
	sudo systemctl start docker

cdk-deploy-all:
	cdk deploy --all --require-approval never --app "python pinecone_constructs/examples/aws/app.py"