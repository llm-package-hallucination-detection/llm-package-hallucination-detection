const fs = require('fs');
const { execSync } = require('child_process');

console.log('=== 1. .gitignore 최종 설정 ===\n');

const gitignore = `# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Large files - Available in GitHub Releases
data/prompts/paper_prompts_expanded_v2.csv
data/reference/npm_package_names.csv
data/results/gemma/*.csv
data/results/gpt_oss/*.csv
data/results/marin/*.csv
data/results/mistral/*.csv
data/results/ollama/*.csv
data/results/qwen/*.csv

# Temporary files
*.zip
check.js
fixgit.js
recover.js
`;

fs.writeFileSync('.gitignore', gitignore, 'utf-8');
console.log('✓ .gitignore 설정 완료\n');

console.log('=== 2. 파일 추가 ===\n');
execSync('git add .', { stdio: 'inherit' });

console.log('\n=== 3. 상태 확인 ===\n');
execSync('git status', { stdio: 'inherit' });

console.log('\n=== 4. 커밋 ===\n');
execSync('git commit -m "Add data folders (analysis, prompts, reference - excluding large files)"', { stdio: 'inherit' });

console.log('\n=== 5. 푸시 ===\n');
console.log('이제 실행하세요: git push origin main');