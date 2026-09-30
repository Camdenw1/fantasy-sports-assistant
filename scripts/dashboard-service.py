#!/usr/bin/env python3
"""Manage the personal macOS dashboard service (localhost only, no credentials)."""
import os
import pathlib
import plistlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = 'com.camden.fantasy-sports-assistant'
PLIST = pathlib.Path.home() / 'Library' / 'LaunchAgents' / (LABEL + '.plist')
DOMAIN = 'gui/' + str(os.getuid())
TARGET = DOMAIN + '/' + LABEL


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This service helper supports macOS. Run python3 app/server.py on other systems.')
    command = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if command == 'status':
        result = subprocess.run(['launchctl', 'print', TARGET], capture_output=True, text=True)
        print('Dashboard service is installed.' if result.returncode == 0 else 'Dashboard service is not running.')
        if result.returncode == 0:
            print('Open http://127.0.0.1:8765/')
        return
    if command == 'uninstall':
        subprocess.run(['launchctl', 'bootout', TARGET], capture_output=True)
        if PLIST.exists(): PLIST.unlink()
        print('Automatic dashboard startup removed. Your data is unchanged.')
        return
    if command != 'install': raise SystemExit('Use install, status, or uninstall.')
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    logs = ROOT / 'app' / '.cache'
    logs.mkdir(parents=True, exist_ok=True)
    spec = {'Label': LABEL, 'ProgramArguments': [sys.executable, '-u', str(ROOT / 'app' / 'server.py')],
            'WorkingDirectory': str(ROOT), 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 5, 'StandardOutPath': str(logs / 'server.log'),
            'StandardErrorPath': str(logs / 'server-error.log')}
    PLIST.write_bytes(plistlib.dumps(spec))
    subprocess.run(['launchctl', 'bootout', TARGET], capture_output=True)
    subprocess.run(['launchctl', 'bootstrap', DOMAIN, str(PLIST)], check=True)
    print('Dashboard starts at login and restarts after a crash. It listens only on 127.0.0.1:8765.')
    print('Remove automatic startup: python3 scripts/dashboard-service.py uninstall')

if __name__ == '__main__': main()
