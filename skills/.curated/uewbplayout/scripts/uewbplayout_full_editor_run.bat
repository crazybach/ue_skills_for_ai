@echo off
setlocal
if "%UE_EDITOR_EXE%"=="" (
  echo UE_EDITOR_EXE is not set.
  exit /b 1
)
if "%UE_PROJECT%"=="" (
  echo UE_PROJECT is not set.
  exit /b 1
)
if "%UEWBPLAYOUT_SCRIPT%"=="" (
  echo UEWBPLAYOUT_SCRIPT is not set. Point it to uewbplayout_editor_commandline.py or uewbplayout_export_folder.py copied into the project.
  exit /b 1
)
"%UE_EDITOR_EXE%" "%UE_PROJECT%" -ExecutePythonScript="%UEWBPLAYOUT_SCRIPT%" -nop4 -nosplash
