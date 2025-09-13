"""
Script de validation de la structure du projet GLaDOS
Ne nécessite aucune dépendance externe
"""

import ast
import yaml
from pathlib import Path


def validate_project_structure():
    """Vérifie que la structure du projet est correcte"""
    print("🔍 Validation de la structure du projet...")
    
    project_root = Path(__file__).parent
    errors = []
    
    # Répertoires principaux
    required_dirs = [
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
        "glados/tools/adapters",
        "tests"
    ]
    
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        if not full_path.exists():
            errors.append(f"❌ Répertoire manquant: {dir_path}")
        else:
            print(f"✅ Répertoire présent: {dir_path}")
    
    # Fichiers essentiels
    required_files = [
        "config.yaml",
        ".env.example", 
        "requirements.txt",
        "README.md",
        "ARCHITECTURE.md",
        "run_glados.py",
        "setup.py",
        "glados/main.py",
        "glados/__init__.py"
    ]
    
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            errors.append(f"❌ Fichier manquant: {file_path}")
        else:
            print(f"✅ Fichier présent: {file_path}")
    
    return errors


def validate_python_syntax():
    """Vérifie que tous les fichiers Python ont une syntaxe valide"""
    print("\\n🐍 Validation de la syntaxe Python...")
    
    project_root = Path(__file__).parent
    python_files = list(project_root.glob("**/*.py"))
    errors = []
    
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
            print(f"✅ Syntaxe valide: {py_file.relative_to(project_root)}")
        except SyntaxError as e:
            errors.append(f"❌ Erreur syntaxe {py_file.relative_to(project_root)}: {e}")
        except Exception as e:
            errors.append(f"❌ Erreur lecture {py_file.relative_to(project_root)}: {e}")
    
    return errors


def validate_config_file():
    """Vérifie la structure du fichier de configuration"""
    print("\\n⚙️ Validation du fichier de configuration...")
    
    project_root = Path(__file__).parent
    config_file = project_root / "config.yaml"
    errors = []
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Sections principales
        required_sections = ['core', 'inputs', 'outputs', 'tools']
        for section in required_sections:
            if section not in config:
                errors.append(f"❌ Section manquante dans config.yaml: {section}")
            else:
                print(f"✅ Section présente: {section}")
        
        # Vérifications spécifiques
        if 'core' in config:
            if 'model_name' not in config['core']:
                errors.append("❌ model_name manquant dans core")
            else:
                print(f"✅ Model configuré: {config['core']['model_name']}")
        
    except Exception as e:
        errors.append(f"❌ Erreur lecture config.yaml: {e}")
    
    return errors


def validate_requirements():
    """Vérifie le fichier requirements.txt"""
    print("\\n📦 Validation des dépendances...")
    
    project_root = Path(__file__).parent
    requirements_file = project_root / "requirements.txt"
    errors = []
    
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        packages = [line.strip() for line in lines 
                   if line.strip() and not line.strip().startswith('#')]
        
        essential_packages = ['llama-index', 'pyyaml', 'sounddevice', 'vosk']
        for pkg in essential_packages:
            found = any(pkg in line for line in packages)
            if found:
                print(f"✅ Package essentiel présent: {pkg}")
            else:
                errors.append(f"❌ Package essentiel manquant: {pkg}")
                
    except Exception as e:
        errors.append(f"❌ Erreur lecture requirements.txt: {e}")
    
    return errors


def main():
    """Fonction principale de validation"""
    print("=" * 60)
    print("🤖 GLaDOS - Validation de la structure du projet")
    print("=" * 60)
    
    all_errors = []
    
    # Validation de la structure
    all_errors.extend(validate_project_structure())
    
    # Validation syntaxe Python
    all_errors.extend(validate_python_syntax())
    
    # Validation configuration
    all_errors.extend(validate_config_file())
    
    # Validation dépendances
    all_errors.extend(validate_requirements())
    
    # Résumé
    print("\\n" + "=" * 60)
    print("📊 RÉSUMÉ DE LA VALIDATION")
    print("=" * 60)
    
    if all_errors:
        print(f"❌ {len(all_errors)} erreur(s) trouvée(s):")
        for error in all_errors:
            print(f"   {error}")
        print("\\n🔧 Veuillez corriger ces erreurs avant de continuer.")
        return False
    else:
        print("🎉 Toutes les validations ont réussi!")
        print("✅ La structure du projet GLaDOS est correcte")
        print("✅ Tous les fichiers Python ont une syntaxe valide")
        print("✅ La configuration est bien formée")
        print("✅ Les dépendances essentielles sont listées")
        print("\\n🚀 Le projet est prêt pour l'installation et les tests!")
        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)