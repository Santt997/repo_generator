#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ast
import os
import shutil
import sys
import subprocess
from pathlib import Path

# CommonImports 2PyPI packages mapping
PYPI_MAPPING : dict[str, str] = {
    'PIL': 'Pillow',
    'Image': 'Pillow',
    'yaml': 'PyYAML',
    'bs4': 'beautifulsoup4',
    'sklearn': 'scikit-learn',
    'cv2': 'opencv-python',
    'surya': 'surya-ocr',
    'torch': 'torch',
    'torchvision': 'torchvision',
    'numpy': 'numpy',
    'requests': 'requests',
    'pandas': 'pandas',
    'matplotlib': 'matplotlib',
    'scipy': 'scipy',
    'jinja2': 'Jinja2',
    'click': 'click',
    'pytest': 'pytest',
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
}

# Std python std library modules (4filtering)
if sys.version_info >= (3, 10):
    STD_LIBS = sys.stdlib_module_names
else:
    # Fallback list 4older Python versions
    STD_LIBS : set[str] = {
        'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections', 'contextlib',
        'csv', 'datetime', 'decimal', 'enum', 'fnmatch', 'functools', 'glob',
        'hashlib', 'html', 'http', 'importlib', 'inspect', 'io', 'json', 'logging',
        'math', 'multiprocessing', 'os', 'pathlib', 'pickle', 'pprint', 'queue',
        'random', 're', 'select', 'shutil', 'signal', 'socket', 'sqlite3', 'ssl',
        'string', 'subprocess', 'sys', 'tempfile', 'threading', 'time', 'traceback',
        'types', 'typing', 'unittest', 'urllib', 'uuid', 'warnings', 'weakref', 'xml'
    }


def parse_dependencies_and_entrypoint(src_dir: Path) -> tuple[set[str], str | None]:
    '''
    Parses all python fs in src_dir using AST 2extract external dependencies
    & find the file containing the __main__ entrypoint block.
    '''
    dependencies : set[str] = set()
    entry_file = None
    py_files = sorted(src_dir.glob('*.py'))

    for py_file in py_files:
        try:
            content = py_file.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            # Check 4__main__ block
            # looking 4: if __name__ == '__main__':
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    # Check if test cond is: name == '__main__'
                    if isinstance(node.test, ast.Compare):
                        left = node.test.left
                        if isinstance(left, ast.Name) and left.id == "__name__":
                            for op, comparator in zip(node.test.ops, node.test.comparators):
                                if isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                                    entry_file = py_file.name
                                elif isinstance(op, ast.Eq) and isinstance(comparator, ast.Str) and comparator.s == "__main__":
                                    # Fallback 4python < 3.8
                                    entry_file = py_file.name

            # ExtractImports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base_module = alias.name.split('.')[0]
                        if base_module not in STD_LIBS:
                            dependencies.add(base_module)
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:  # Absolute import
                        base_module = node.module.split('.')[0]
                        if base_module not in STD_LIBS:
                            dependencies.add(base_module)
        except Exception as e:
            print(f'Warning: Failed 2parse {py_file.name} 4imports/entrypoint: {e}')

    # Map imports 2std PyPI distr names
    pypi_deps : set[str] = set()
    for dep in dependencies:
        pypi_deps.add(PYPI_MAPPING.get(dep, dep))

    # If no entry file is found but we have .pys, choose the alphabetical first | main.py / _.py if it exists
    if not entry_file and py_files:
        file_names = [f.name for f in py_files]
        if '_.py' in file_names:
            entry_file = '_.py'
        elif 'main.py' in file_names:
            entry_file = 'main.py'
        else:
            entry_file = file_names[0]

    return pypi_deps, entry_file


def get_fallback_gitignore() -> str:
    return '''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distr / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Envs
.env
.envrc
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# VS Code & JetBrains
.vscode/
.idea/
'''


def main():
    parser : argparse.ArgumentParser = argparse.ArgumentParser(
        description='PremiumPythonAutomationTool: Package any Python folder as a std local/cloud GitHub repo & publish 2PyPI.'
    )
    parser.add_argument(
        'src_dir',
        type=str,
        help='Path 2the directory containing the .py files 2package'
    )
    parser.add_argument(
        '-n', '--name',
        type=str,
        default=None,
        help='Custom package / repo name (defaults 2the src directory name)'
    )
    parser.add_argument(
        '-v', '--version',
        type=str,
        default='0.1.0',
        help='Initial package version (default: 0.1.0)'
    )
    parser.add_argument(
        '-d', '--description',
        type=str,
        default=None,
        help='Package description (defaults 2folder-based description)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output folder where the new repo will be created (defaults 2./generated_repos/<name>)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only generate the fs locally; skip git init, gh repo create, & publish_pypi.sh'
    )
    parser.add_argument(
        '--skip-publish',
        action='store_true',
        help='Generate local fs, init Git, & create GitHub repo, but skip running publish_pypi.sh'
    )
    parser.add_argument(
        '--private',
        action='store_true',
        help='Create the GitHub cloud repo as private (default is public)'
    )

    args = parser.parse_args()

    # Resolve src directory
    src_path = Path(args.src_dir).resolve()
    if not src_path.is_dir():
        print(f'Error: Src directory does not exist: {src_path}')
        sys.exit(1)

    # Resolve package name from folder
    package_name = args.name or src_path.name
    # Standardize package name: swap spaces w hyphens, lowercase
    package_name : str = package_name.strip().replace(' ', '-').lower()
    
    # Description default
    description = args.description or f'cast from {package_name} src 2pypi'

    print(f'============================================================')
    print(f'🚀 InitializingRepo & PackageGeneration')
    print(f'   - PackageName:  {package_name}')
    print(f'   - Version:       {args.version}')
    print(f'   - SrcFolder: {src_path}')
    print(f'============================================================')

    # Resolve output directory
    if args.output:
        out_path = Path(args.output).resolve()
    else:
        out_path = Path.home() / 'Documentos' / 'GitHub' / package_name

    # Check if output directory already exists
    if out_path.exists():
        print(f'Warning: Output folder already exists: {out_path}')
        confirm : str = input('Overwrite entire directory? (y/N): ').strip().lower()
        if confirm != 'y':
            print('Canceled.')
            sys.exit(0)
        shutil.rmtree(out_path)

    # 1. AST scan 2find external dependencies & entrypoint
    print('\n🔍 Scanning python fs 4dependencies & main entry point...')
    dependencies, entry_file = parse_dependencies_and_entrypoint(src_path)
    print(f"   Detected dependencies: {sorted(list(dependencies)) if dependencies else 'None'}")
    print(f"   Detected entrypoint:   {entry_file or 'None'}")

    # Create directory struct
    out_path.mkdir(parents=True, exist_ok=True)
    pkg_subfolder = out_path / package_name
    pkg_subfolder.mkdir(parents=True, exist_ok=True)

    # Copy all fs from src_dir to the pkg_subfolder
    print(f'\n📂 Copying src python fs 2{pkg_subfolder}...')
    for item in src_path.iterdir():
        # Avoid copying output directory recursively if running on itself
        if item.resolve() == out_path.resolve():
            continue
        if item.is_file():
            shutil.copy2(item, pkg_subfolder / item.name)
        elif item.is_dir() and item.name not in [".git", "build", "dist", "generated_repos"]:
            shutil.copytree(item, pkg_subfolder / item.name, symlinks=True, ignore=shutil.ignore_patterns(".git", "build", "dist"))

    # Create empty __init__.py & py.typed if not exists
    (pkg_subfolder / '__init__.py').touch(exist_ok=True)
    (pkg_subfolder / 'py.typed').touch(exist_ok=True)

    # 2. Generate CONFIG FILES from templates
    print("\n✨ Generating repository configuration files...")

    # A. pyproject.toml
    deps_list = ',\n    '.join([f'"{d}"' for d in sorted(list(dependencies))])
    pyproject_content: str = f'''[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "{package_name}"
version = "{args.version}"
description = "{description}"
readme = "README.md"
requires-python = ">=3.8"
dependencies = [
    {deps_list}
]

[tool.setuptools]
packages = ["src/{package_name}"]
'''
    (out_path / 'pyproject.toml').write_text(pyproject_content, encoding='utf-8')

    # B. .gitignore
    # Try 2copy gitignore from curr workspace, fallback 2template
    curr_gitignore = Path.cwd() / '.gitignore'
    if curr_gitignore.is_file():
        shutil.copy2(curr_gitignore, out_path / '.gitignore')
    else:
        (out_path / '.gitignore').write_text(get_fallback_gitignore(), encoding='utf-8')

    # C. README.md
    readme_content = f'''# {package_name}

{description}

## Installation

```bash
pip install {package_name}
```

## Running local env

Use the provided MkF 2manage the env:
```bash
cd Envs/MkFs
mkc
mkr
```
'''
    (out_path / 'README.md').write_text(readme_content, encoding='utf-8')

    # D. publish_pypi.sh
    publish_sh_content = f'''#!/usr/bin/env bash

# Exit immediately if a cmd exits w a non-0 status
set -e

# Define colors 4output
GREEN='\\033[0;32m'
BLUE='\\033[0;34m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
NC='\\033[0m' # No Color

echo -e "${{BLUE}}===============================================${{NC}}"
echo -e "${{BLUE}}      {package_name} PyPI Release Assistant${{NC}}"
echo -e "${{BLUE}}===============================================${{NC}}"

# Navigate 2the script's directory 2ensure relative paths work
cd "$(dirname "$0")"

# 1. CheckPythonInstallation (Targeting 'pypi' mm env)
echo -e "\\n${{BLUE}}[1/5] Checking MM 'pypi' env...${{NC}}"

# Check if the 'pypi' env is already active in the currShell
if [[ "$MAMBA_PREFIX" == *"/envs/pypi" ]]; then
    PYTHON_BIN="$MAMBA_PREFIX/bin/python"
else
    # If not active, look 4the binary in the std mm location
    MAMBA_PYPI_BIN="$HOME/micromamba/envs/pypi/bin/python"
    if [ ! -f "$MAMBA_PYPI_BIN" ]; then
        MAMBA_PYPI_BIN="$HOME/.local/share/mamba/envs/pypi/bin/python"
    fi
    
    if [ -f "$MAMBA_PYPI_BIN" ]; then
        PYTHON_BIN="$MAMBA_PYPI_BIN"
    else
        echo -e "${{RED}}Error: The MMenv 'pypi' does not exist.${{NC}}"
        echo -e "${{YELLOW}}Please create it first by running:${{NC}}"
        echo -e "  micromamba create -n pypi python=3.11 -y"
        exit 1
    fi
fi

echo -e "Using Python: ${{GREEN}}$($PYTHON_BIN --version) ($PYTHON_BIN)${{NC}}"

# 2. Install/Upgrade packaging tools inside the env
echo -e "\\n${{BLUE}}[2/5] Installing/Upgrading build and twine...${{NC}}"
$PYTHON_BIN -m pip install --upgrade pip
$PYTHON_BIN -m pip install --upgrade build twine
echo -e "${{GREEN}}Packaging tools installed successfully!${{NC}}"

# 3. Clean up old builds
echo -e "\\n${{BLUE}}[3/5] Cleaning old build files...${{NC}}"
rm -rf dist/ build/ *.egg-info/
echo -e "Cleaned old build artifacts."

# 4. BuildPackage
echo -e "\\n${{BLUE}}[4/5] Building package (sdist and wheel)...${{NC}}"
$PYTHON_BIN -m build
echo -e "${{GREEN}}Build completed successfully! Here are the generated files:${{NC}}"
ls -lh dist/

# 5. CheckPackageValidity
echo -e "\\n${{BLUE}}[5/5] Checking package metadata with twine check...${{NC}}"
$PYTHON_BIN -m twine check dist/*
echo -e "${{GREEN}}Twine checks passed! Package is structurally valid.${{NC}}"

# 6. PublishSection
echo -e "\\n${{YELLOW}}===============================================${{NC}}"
echo -e "${{YELLOW}}           Ready 2Publish 2PyPI!            ${{NC}}"
echo -e "${{YELLOW}}===============================================${{NC}}"
echo -e "2upload, you will need your PyPI API Token."
echo -e "  - Username: ${{GREEN}}__token__${{NC}}"
echo -e "  - Password: ${{GREEN}}pypi-your-api-token-val${{NC}}"
echo -e "==============================================="

echo -e "\\nWhere would you like 2publish?"
echo -e "1) ${{BLUE}}TestPyPI${{NC}} (Safe test upload - requires account at test.pypi.org)"
echo -e "2) ${{GREEN}}PyPI${{NC}} (Official release - requires account at pypi.org)"
echo -e "3) ${{YELLOW}}Do not publish${{NC}} (Keep build files local)"

read -rp "Select 1 option [1-3]: " option

case $option in
    1)
        echo -e "\\n${{BLUE}}Uploading to TestPyPI...${{NC}}"
        $PYTHON_BIN -m twine upload --repository testpypi dist/*
        echo -e "${{GREEN}}Successfully uploaded to TestPyPI!${{NC}}"
        echo -e "You can try installing it using:"
        echo -e "  ${{YELLOW}}pip install --index-url https://pypi.org --extra-index-url https://pypi.org {package_name}${{NC}}"
        ;;
    2)
        echo -e "\\n${{GREEN}}Uploading to PyPI (Official Release)...${{NC}}"
        $PYTHON_BIN -m twine upload --verbose dist/*
        echo -e "${{GREEN}}Successfully published to PyPI!${{NC}}"
        echo -e "You and anyone else can now install it using:"
        echo -e "  ${{YELLOW}}pip install {package_name}${{NC}}"
        ;;
    *)
        echo -e "\\n${{YELLOW}}Publishing canceled. The build files remain in the dist/ folder.${{NC}}"
        ;;
esac

echo -e "\\n${{BLUE}}Done!${{NC}}"
'''
    (out_path / 'publish_pypi.sh').write_text(publish_sh_content, encoding='utf-8')
    # Make executable
    try:
        os.chmod(out_path / 'publish_pypi.sh', 0o755)
    except Exception as e:
        print(f'Warning: Failed 2set executable permissions on publish_pypi.sh: {e}')

    # E. .github/workflows/update_mamba.yml
    workflow_path = out_path / '.github' / 'workflows'
    workflow_path.mkdir(parents=True, exist_ok=True)
    workflow_content : str = f'''name: Update Env MM Local

on:
  push:
    branches:
      - master

jobs:
  update-env:
    runs-on: self-hosted

    steps:
      - name: Download changes of repo
        uses: actions/checkout@v4

      - name: Update package in Micromamba local
        run: |
          export MAMBA_EXE="$HOME/.local/bin/micromamba"
          eval "$($MAMBA_EXE shell hook --shell bash)"
          
          micromamba activate {package_name}
          pip install -e .
'''
    (workflow_path / 'update_mamba.yml').write_text(workflow_content, encoding='utf-8')

    # F. Envs/YMLs/<package_name>.yml
    envs_yml_path = out_path / 'Envs' / 'YMLs'
    envs_yml_path.mkdir(parents=True, exist_ok=True)
    
    yml_deps : str = '\n  - '.join(sorted(list(dependencies))) if dependencies else ''
    if yml_deps:
        yml_deps = '\n  - ' + yml_deps
        
    yml_content : str = f'''name: {package_name}
channels:
  - conda-forge

dependencies:
  - python=3.11
  - pip
  - numpy
  - requests{yml_deps}
'''
    (envs_yml_path / f'{package_name}.yml').write_text(yml_content, encoding='utf-8')

    # G. Envs/MkFs/Makefile
    envs_mk_path = out_path / 'Envs' / 'MkFs'
    envs_mk_path.mkdir(parents=True, exist_ok=True)
    
    entry_run_cmd : str = f'python ../../{package_name}/{entry_file} \"$(TARGET)\"' if entry_file else 'python -m ' + package_name
    
    makefile_content : str = f'''SHELL := /bin/bash

ENV_NAME := {package_name}
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
	@eval "$$(micromamba shell hook --shell bash)" && \\
	micromamba activate $(ENV_NAME) && \\
	{entry_run_cmd}

debug:
	@echo "ENV_NAME=$(ENV_NAME)"
	@echo "YML_FILE=$(YML_FILE)"
	@echo "TARGET=$(TARGET)"
	@echo "PWD=$$(pwd)"

test:
	@eval "$$(micromamba shell hook --shell bash)" && \\
	micromamba activate $(ENV_NAME) && \\
	python -c "import {package_name.replace('-', '_')}; print('{package_name} import OK')"

info:
	@micromamba env list

list:
	@eval "$$(micromamba shell hook --shell bash)" && \\
	micromamba activate $(ENV_NAME) && \\
	pip list

clean:
	@echo "Nothing to clean"

deep-clean:
	-micromamba env remove -n $(ENV_NAME) -y
	@micromamba clean --all -y
'''
    (envs_mk_path / 'Makefile').write_text(makefile_content, encoding='utf-8')

    # H. Code workspace
    workspace_content = f'''{{
	"folders": [
		{{
			"path": ".."
		}}
	],
	"settings": {{}}
}}
'''
    (pkg_subfolder / f'{package_name}.code-workspace').write_text(workspace_content, encoding='utf-8')

    print(f'🎉 Successfully generated all template fs in: {out_path}')

    if args.dry_run:
        print(f'\n⚠️ Dry-run enabled. Skipping Git, GitHub, PyPI publishing.')
        print(f'Done!')
        sys.exit(0)

    # 3. Initialize Git Repo
    print('\n🐙 Initializing Git Repo...')
    try:
        subprocess.run(['git', 'init'], cwd=out_path, check=True)
        # Configure branch name 2master
        subprocess.run(['git', 'checkout', '-b', 'master'], cwd=out_path, check=True)
        subprocess.run(['git', 'add', '.'], cwd=out_path, check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit by repo-generator'], cwd=out_path, check=True)
        print('🐙 Git repo initialized and first commit created.')
    except Exception as e:
        print(f'Error: GitRepoInitializationFailed: {e}')
        sys.exit(1)

    # 4. Create Cloud GitHub Repo
    print("\n☁️ Creating cloud GitHub repo using 'gh' CLI...")
    visibility_flag = '--private' if args.private else '--public'
    
    # Detect the authenticated GitHub user
    owner = 'Santt997'
    try:
        user_res = subprocess.run(['gh', 'api', 'user', '--jq', '.login'], capture_output=True, text=True, cwd=out_path)
        if user_res.returncode == 0 and user_res.stdout.strip():
            owner = user_res.stdout.strip()
    except Exception:
        pass

    # Check if repo already exists on GitHub
    repo_exists = False
    try:
        check_res = subprocess.run(['gh', 'repo', 'view', f'{owner}/{package_name}'], capture_output=True, cwd=out_path)
        if check_res.returncode == 0:
            repo_exists = True
            print(f"☁️ Remote repo '{owner}/{package_name}' already exists on GitHub.")
    except Exception:
        pass

    if not repo_exists:
        try:
            # Create EMPTY remote repo (no --src, no --push) to avoid auto-push
            subprocess.run(
                ['gh', 'repo', 'create', package_name, visibility_flag],
                cwd=out_path,
                check=True
            )
            print(f"☁️ RemoteRepo '{package_name}' successfullyCreatedOnGitHub.")
        except Exception as e:
            print(f'Error: GitHub repo creation failed: {e}')
            print("Make sure you are logged in using 'gh auth login' | have internet connection.")
            sys.exit(1)

    # Add remote origin manually
    remote_url = f'https://github.com/{owner}/{package_name}.git'
    subprocess.run(['git', 'remote', 'remove', 'origin'], cwd=out_path, capture_output=True)  # remove if exists
    subprocess.run(['git', 'remote', 'add', 'origin', remote_url], cwd=out_path, check=True)
    print(f'☁️ Remote set 2: {remote_url}')

    # Try 2push 2remote
    print('☁️ Pushing local commits 2GitHub...')
    push_result = subprocess.run(['git', 'push', '-u', 'origin', 'master'], cwd=out_path, capture_output=True, text=True)

    if push_result.returncode == 0:
        print(f"☁️ Cloud GitHub repo '{package_name}' successfully pushed!")
    else:
        push_stderr = push_result.stderr or ''
        # Check if it failed because of workflow scope limitation
        if 'workflow' in push_stderr.lower():
            print("\n⚠️ Push rejected due to missing 'workflow' scope on GitHub token.")
            print('💡 Retrying push !w workflow files...')

            # 1. Back up .github directory
            workflow_dir = out_path / '.github'
            backup_dir = out_path / '.github_backup'
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.move(workflow_dir, backup_dir)

            try:
                # 2. Rm .github from the commit
                subprocess.run(['git', 'rm', '-rf', '--cached', '.github'], cwd=out_path, capture_output=True)
                subprocess.run(['git', 'commit', '--amend', '-m', 'Initial commit by repo-generator'], cwd=out_path, check=True)

                # 3. Retry push
                subprocess.run(['git', 'push', '-u', 'origin', 'master'], cwd=out_path, check=True)
                print('☁️ Repo code successfully pushed 2GitHub (!w workflows)!')
            except Exception as retry_err:
                print(f'Error: Retried push also failed: {retry_err}')
                # Restore .github before exiting
                shutil.move(backup_dir, workflow_dir)
                sys.exit(1)

            # 4. Restore .github directory locally
            shutil.move(backup_dir, workflow_dir)

            print('\n' + '='*80)
            print('⚠️  IMPORTANT: GITHUB ACTIONS WORKFLOWS NOT PUSHED')
            print("Your GitHub token does not have the 'workflow' scope.")
            print('All code was pushed successfully, but workflow files remain local only.')
            print('2push them later, run in your terminal:')
            print('  1. gh auth refresh -s workflow')
            print(f'  2. cd {out_path}')
            print('  3. git add .github/')
            print('  4. git commit -m \"Add GitHub Actions workflows\"')
            print('  5. git push')
            print('='*80 + '\n')
        else:
            print(f'Error: Git push failed:\n{push_stderr}')
            sys.exit(1)

    if args.skip_publish:
        print('\n⚠️ Skipping publishing 2PyPI as requested.')
        print('Done!')
        sys.exit(0)

    # 5. Execute publish_pypi.sh immediately
    print('\n📦 Launching PyPI Release Assistant...')
    try:
        # Run bash publish_pypi.sh interactively (sharing stdin/stdout)
        subprocess.run(['bash', 'publish_pypi.sh'], cwd=out_path, check=True)
    except Exception as e:
        print(f'Error during package publishing execution: {e}')
        sys.exit(1)

    print('\n💎 Perfect! All operations finished successfully.')


if __name__ == '__main__':
    main()
