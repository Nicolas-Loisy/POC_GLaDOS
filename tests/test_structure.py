"""
Tests de validation de la structure du projet
Tests qui ne nécessitent pas les dépendances externes
"""

import pytest
from pathlib import Path
import importlib.util
import ast


def test_project_structure():
    """Vérifie que la structure du projet est correcte"""
    project_root = Path(__file__).parent.parent
    
    # Répertoires principaux
    assert (project_root / "glados").exists()
    assert (project_root / "glados" / "core").exists()
    assert (project_root / "glados" / "config").exists()
    assert (project_root / "glados" / "inputs").exists()
    assert (project_root / "glados" / "outputs").exists()
    assert (project_root / "glados" / "tools").exists()
    
    # Fichiers de configuration
    assert (project_root / "config.yaml").exists()
    assert (project_root / ".env.example").exists()
    assert (project_root / "requirements.txt").exists()
    assert (project_root / "README.md").exists()
    
    # Point d'entrée
    assert (project_root / "run_glados.py").exists()
    assert (project_root / "glados" / "main.py").exists()


def test_python_files_syntax():
    """Vérifie que tous les fichiers Python ont une syntaxe valide"""
    project_root = Path(__file__).parent.parent
    python_files = list(project_root.glob("**/*.py"))
    
    errors = []
    for py_file in python_files:
        if "test_" in py_file.name:
            continue  # Skip test files pour éviter la récursion
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            errors.append(f"{py_file}: {e}")
        except Exception as e:
            errors.append(f"{py_file}: {e}")
    
    if errors:
        pytest.fail(f"Erreurs de syntaxe trouvées:\\n" + "\\n".join(errors))


def test_init_files_present():
    """Vérifie que tous les packages ont des fichiers __init__.py"""
    project_root = Path(__file__).parent.parent
    
    # Répertoires qui doivent être des packages Python
    package_dirs = [
        "glados",
        "glados/core", 
        "glados/config",
        "glados/inputs",
        "glados/inputs/wake_word",
        "glados/inputs/terminal",
        "glados/outputs",
        "glados/outputs/tts",
        "glados/outputs/terminal",
        "glados/tools",
        "glados/tools/tapo",
        "glados/tools/adapters"
    ]
    
    missing_init = []
    for pkg_dir in package_dirs:
        init_file = project_root / pkg_dir / "__init__.py"
        if not init_file.exists():
            missing_init.append(str(init_file))
    
    if missing_init:
        pytest.fail(f"Fichiers __init__.py manquants:\\n" + "\\n".join(missing_init))


def test_config_file_structure():
    """Vérifie la structure du fichier de configuration"""
    import yaml
    
    project_root = Path(__file__).parent.parent
    config_file = project_root / "config.yaml"
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Sections principales
    assert 'core' in config
    assert 'inputs' in config
    assert 'outputs' in config
    assert 'tools' in config
    
    # Configuration du core
    assert 'model_name' in config['core']
    assert 'max_iterations' in config['core']
    
    # Au moins un input et un output activé
    assert config['inputs'].get('enabled', False) is True
    assert config['outputs'].get('enabled', False) is True


def test_requirements_file():
    """Vérifie que le fichier requirements.txt est bien formé"""
    project_root = Path(__file__).parent.parent
    requirements_file = project_root / "requirements.txt"
    
    with open(requirements_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Supprimer les commentaires et lignes vides
    packages = [line.strip() for line in lines 
                if line.strip() and not line.strip().startswith('#')]
    
    # Vérifications basiques
    assert len(packages) > 0, "Le fichier requirements.txt est vide"
    
    # Packages essentiels
    essential_packages = ['llama-index', 'pyyaml', 'click']
    for pkg in essential_packages:
        found = any(pkg in line for line in packages)
        assert found, f"Package essentiel manquant: {pkg}"


def test_documentation_files():
    """Vérifie que les fichiers de documentation existent et ne sont pas vides"""
    project_root = Path(__file__).parent.parent
    
    docs = [
        ("README.md", 1000),  # Au moins 1000 caractères
        ("ARCHITECTURE.md", 2000),  # Au moins 2000 caractères
    ]
    
    for doc_file, min_size in docs:
        doc_path = project_root / doc_file
        assert doc_path.exists(), f"Fichier de documentation manquant: {doc_file}"
        
        content = doc_path.read_text(encoding='utf-8')
        assert len(content) >= min_size, f"Fichier {doc_file} trop court ({len(content)} < {min_size} caractères)"


if __name__ == '__main__':
    pytest.main([__file__])