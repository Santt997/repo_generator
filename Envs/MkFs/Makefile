SHELL := /bin/bash

ENV_NAME := repo_generator
YML_FILE := ../YMLs/$(ENV_NAME).yml

TARGET ?= $(PWD)

.PHONY: create update remove run debug test info list clean deep-clean
create:
	micromamba env create -f $(YML_FILE) -y

update:
	micromamba env update -f $(YML_FILE) --prune -y

remove:
	micromamba env remove -n $(ENV_NAME) -y

run:
	@eval "$$(micromamba shell hook --shell bash)" && \
	micromamba activate $(ENV_NAME) && \
	python ../../repo_generator/generator.py "$(TARGET)"

debug:
	@echo "ENV_NAME=$(ENV_NAME)"
	@echo "YML_FILE=$(YML_FILE)"
	@echo "TARGET=$(TARGET)"
	@echo "PWD=$$(pwd)"

test:
	@eval "$$(micromamba shell hook --shell bash)" && \
	micromamba activate $(ENV_NAME) && \
	python -c "import repo_generator; print('repo_generator import OK')"

info:
	@micromamba env list

list:
	@eval "$$(micromamba shell hook --shell bash)" && \
	micromamba activate $(ENV_NAME) && \
	pip list

clean:
	@echo "Nothing to clean"

deep-clean:
	-micromamba env remove -n $(ENV_NAME) -y
	@micromamba clean --all -y
