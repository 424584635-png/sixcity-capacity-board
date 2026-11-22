@echo off
setlocal EnableExtensions
title Capacity Board Pipeline
REM NOTE: keep this file ASCII-only (cmd.exe reads .bat as ANSI).
set "ROOT=C:\Users\luansha\WorkBuddy\2026-11-07-23-44-13"
set "AGG=%ROOT%\agg_board_1122"
set "CDDP=%ROOT%\cddp_1122"
set "PIPE=%AGG%\pipeline"
set "PY=C:\Users\luansha\.workbuddy\binaries\python\versions\3.13.12\python.exe"
set "NODE=C:\Users\luansha\.workbuddy\binaries\node\versions\22.22.2-6\node.exe"
set "LOG=%PIPE%\pipeline.log"

cd /d "%ROOT%"
if not exist "%LOG%" echo [%date% %time%] pipeline log created>"%LOG%"
for %%F in ("%LOG%") do if %%~zF GTR 2097152 move /Y "%LOG%" "%LOG%.old">nul 2>&1

call :log "===== PIPELINE START ====="

call :log "[1/11] Check Edge CDP 9223"
curl -s -m 5 http://127.0.0.1:9223/json/version>nul 2>&1
if errorlevel 1 goto e_cdp

call :log "[2/11] Auth health check (fs/xy)"
"%NODE%" "%AGG%\check_auth.mjs">>"%LOG%" 2>&1
if errorlevel 2 goto e_xy
if errorlevel 1 goto relogin
goto crawl

:relogin
call :log "WARN: fs session expired, auto relogin"
"%NODE%" "%AGG%\relogin_aeolus.mjs">>"%LOG%" 2>&1
"%NODE%" "%AGG%\check_auth.mjs">>"%LOG%" 2>&1
if errorlevel 1 goto e_fs

:crawl
call :log "[3/11] Crawl cddp site table (26 areas)"
"%NODE%" "%CDDP%\crawl_all.mjs">>"%LOG%" 2>&1
if errorlevel 1 goto e_crawl_all

call :log "[4/11] Crawl cddp bd lines"
"%NODE%" "%CDDP%\crawl_bd_tms.mjs">>"%LOG%" 2>&1
if errorlevel 1 goto e_crawl_bd

call :log "[5/11] Crawl fengshen + xuanyuan attendance"
"%NODE%" "%AGG%\collect.mjs">>"%LOG%" 2>&1
if errorlevel 1 goto e_collect

call :log "[6/11] Crawl current period detail"
"%NODE%" "%AGG%\collect_fs_period.mjs">>"%LOG%" 2>&1
if errorlevel 1 goto e_period

call :log "[7/11] Build board html"
"%PY%" "%AGG%\build_board.py">>"%LOG%" 2>&1
if errorlevel 1 goto e_build

call :log "[8/11] Screenshot 3 sections"
"%NODE%" "%AGG%\shot_sections.mjs">>"%LOG%" 2>&1
if errorlevel 1 goto e_shot

call :log "[9/11] Upload screenshots to GitHub"
"%PY%" "%PIPE%\publish_shots.py">>"%LOG%" 2>&1
if errorlevel 1 goto e_upload

call :log "[10/11] Push DingTalk"
"%PY%" "%PIPE%\push_dingtalk.py">>"%LOG%" 2>&1
if errorlevel 1 goto e_push

call :log "[11/11] Mirror screenshots to local public dir"
copy /Y "%AGG%\shots\1_city.png" "%AGG%\shots\public\1_city.png">nul 2>&1
copy /Y "%AGG%\shots\2_team.png" "%AGG%\shots\public\2_team.png">nul 2>&1
copy /Y "%AGG%\shots\3_squad.png" "%AGG%\shots\public\3_squad.png">nul 2>&1

call :log "===== PIPELINE DONE ====="
exit /b 0

:e_cdp
call :log "ERROR: CDP 9223 unavailable (Edge not running / not logged in)"
call :alert cdp
exit /b 2
:e_xy
call :log "ERROR: xy (xuanyuan) session invalid, manual login needed"
call :alert xy
exit /b 3
:e_fs
call :log "ERROR: fengshen relogin failed"
call :alert fs
exit /b 4
:e_crawl_all
call :log "ERROR: crawl_all failed"
call :alert crawl_all
exit /b 5
:e_crawl_bd
call :log "ERROR: crawl_bd_tms failed"
call :alert crawl_bd
exit /b 6
:e_collect
call :log "ERROR: collect failed"
call :alert collect
exit /b 7
:e_period
call :log "ERROR: collect_fs_period failed"
call :alert period
exit /b 8
:e_build
call :log "ERROR: build_board failed"
call :alert build
exit /b 9
:e_shot
call :log "ERROR: screenshot failed"
call :alert shot
exit /b 10
:e_upload
call :log "ERROR: upload failed, skip push"
call :alert upload
exit /b 11
:e_push
call :log "ERROR: dingtalk push failed"
call :alert push
exit /b 12

:log
echo [%date% %time%] %~1>>"%LOG%"
echo [%time%] %~1
exit /b 0

:alert
"%PY%" "%PIPE%\push_alert.py" "%~1">>"%LOG%" 2>&1
exit /b 0
