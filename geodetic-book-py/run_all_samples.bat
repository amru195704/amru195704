@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

if defined PYTHON (
  set "PYTHON_CMD=%PYTHON%"
) else (
  py -3 --version >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
  ) else (
    python --version >nul 2>&1
    if not errorlevel 1 (
      set "PYTHON_CMD=python"
    ) else (
      echo Python interpreter not found. Set PYTHON or install Python 3.
      exit /b 1
    )
  )
)

echo Using Python: %PYTHON_CMD%
echo Base directory: %SCRIPT_DIR%

call :run "ch03\ch03_make_test_par.py" || exit /b 1
call :run "ch01\ch01_degree_length.py" || exit /b 1
call :run "ch01\ch01_ellipsoid.py" || exit /b 1
call :run "ch01\ch01_gauss_krueger.py" || exit /b 1
call :run "ch01\ch01_meridian_arc.py" || exit /b 1
call :run "ch02\ch02_helmert.py" || exit /b 1
call :run "ch02\ch02_xyz_blh.py" || exit /b 1
call :run "ch03\ch03_par_reader.py" || exit /b 1
call :run "ch03\ch03_bilinear.py" || exit /b 1
call :run "ch04\ch04_inverse_iter.py" || exit /b 1
call :run "ch05\ch05_geoid.py" || exit /b 1
call :run "ch05\ch05_height.py" || exit /b 1
call :run "ch06\ch06_sequential.py" || exit /b 1
call :run "ch07\ch07_boundary.py" || exit /b 1
call :run "ch08\ch08_verify.py" || exit /b 1
call :run "ch09\ch09_par2sqlite.py" || exit /b 1
call :run "ch10\ch10_heatmap.py" || exit /b 1

echo.
echo Completed all scripts successfully.
exit /b 0

:run
echo.
echo ^>^>^> Running %~1
%PYTHON_CMD% "%SCRIPT_DIR%%~1"
exit /b %errorlevel%