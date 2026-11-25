$ErrorActionPreference = 'Stop'
Write-Host 'LEO Shield environment verification'
python --version
node --version
npm --version
git --version
python -c "import fastapi,uvicorn,pydantic,httpx,PIL,multipart; print('FastAPI',fastapi.__version__,'Uvicorn',uvicorn.__version__,'Pydantic',pydantic.__version__,'HTTPX',httpx.__version__,'Pillow',PIL.__version__,'python-multipart',multipart.__version__)"
Write-Host 'Frontend uses local static files in this first slice; npm packages are not required.'
Write-Host 'The startup script securely prompts for the first owner password when no account exists.'
